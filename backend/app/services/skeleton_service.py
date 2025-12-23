"""
Skeleton Service for Decoupled Search with Lazy Registration.

Provides light-write operations for creating DNO skeletons and locations
without triggering heavy crawl jobs. All methods are idempotent and race-safe.
"""

import hashlib
import re
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

import structlog
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DNOModel, LocationModel

logger = structlog.get_logger()


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class NormalizedAddress:
    """Normalized address with clean components and hash for deduplication."""
    street_clean: str       # For storage/API calls: "An der Ronne"
    number_clean: str | None  # For storage/API calls: "160"
    zip_code: str
    city: str
    address_hash: str       # For DB uniqueness: hash("anderronne|160|12345")


# =============================================================================
# Normalization Functions
# =============================================================================


# Aggressive replacements for German street abbreviations
STREET_REPLACEMENTS = {
    r'straße': 'str',
    r'strasse': 'str',
    r'str\.': 'str',
    r'\.': '',        # Remove dots
    r'\s+': '',       # Remove ALL spaces
    r'-': '',         # Remove hyphens
}


def normalize_address(street_input: str, zip_code: str, city: str) -> NormalizedAddress:
    """
    Aggressive normalization for uniqueness, gentle cleaning for storage.
    
    The "mashed" string is used for hash generation (deduplication).
    The "clean" components are stored for API calls to VNB Digital.
    
    Examples:
        "Musterstraße 5" → hash("musterstr|5|12345")
        "An der Ronne 160" → hash("anderronne|160|12345")
    """
    # 1. Clean basic inputs
    street_input = street_input.strip()
    zip_code = zip_code.strip()
    city = city.strip()

    # 2. Extract House Number (Regex looks for number at end of string)
    # Matches "Musterstr. 12" or "Musterstr 12a"
    match = re.search(r'^(.+?)\s+(\d+\s*[a-z]?)$', street_input, re.IGNORECASE)
    if match:
        street_clean = match.group(1).strip()
        number_clean = match.group(2).strip()
    else:
        street_clean = street_input
        number_clean = None

    # 3. Create "Mashed" String for Hashing
    mashed_street = street_clean.lower()
    
    for pattern, repl in STREET_REPLACEMENTS.items():
        mashed_street = re.sub(pattern, repl, mashed_street)
    
    # 4. Generate Hash
    canonical_string = f"{mashed_street}|{number_clean or ''}|{zip_code}"
    address_hash = hashlib.sha256(canonical_string.encode()).hexdigest()

    return NormalizedAddress(
        street_clean=street_clean,
        number_clean=number_clean,
        zip_code=zip_code,
        city=city,
        address_hash=address_hash,
    )


def snap_coordinate(value: float) -> Decimal:
    """
    Snap coordinate to 6 decimal places for exact DB matching.
    
    6 decimal places = ~11cm precision.
    Using Decimal avoids floating point comparison issues.
    """
    return Decimal(str(value)).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)


def generate_slug(name: str) -> str:
    """Generate URL-safe slug from DNO name."""
    slug = name.lower()
    slug = re.sub(r'\s+', '-', slug)
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')


# =============================================================================
# Skeleton Service
# =============================================================================


class SkeletonService:
    """
    Service for creating skeleton records with race-condition safety.
    
    All methods are idempotent - safe to call multiple times with same input.
    Never triggers heavy crawl jobs.
    """
    
    def __init__(self):
        self.log = logger.bind(service="SkeletonService")
    
    async def get_or_create_dno(
        self,
        db: AsyncSession,
        name: str,
        vnb_id: str,
        official_name: str | None = None,
        website: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        contact_address: str | None = None,
    ) -> tuple[DNOModel, bool]:
        """
        Get existing or create new DNO skeleton.
        
        Returns: (dno, created) - created=True if new record
        
        Race-condition safe: uses IntegrityError fallback for concurrent creates.
        """
        log = self.log.bind(name=name, vnb_id=vnb_id)
        
        # First, try to find existing by vnb_id
        result = await db.execute(
            select(DNOModel).where(DNOModel.vnb_id == vnb_id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            log.debug("DNO already exists", dno_id=existing.id)
            return existing, False
        
        # Create new skeleton with contact info
        slug = generate_slug(name)
        dno = DNOModel(
            slug=slug,
            name=name,
            official_name=official_name,
            vnb_id=vnb_id,
            status="uncrawled",
            website=website,
            phone=phone,
            email=email,
            contact_address=contact_address,
        )
        
        try:
            db.add(dno)
            await db.commit()
            await db.refresh(dno)
            log.info("Created DNO skeleton", dno_id=dno.id, slug=slug, has_website=bool(website))
            return dno, True
        except IntegrityError as e:
            # Race condition: another request created it first
            await db.rollback()
            log.warning("Race condition on DNO create, fetching existing", error=str(e))
            
            # Fetch the existing record (try by vnb_id, then by slug)
            result = await db.execute(
                select(DNOModel).where(
                    (DNOModel.vnb_id == vnb_id) | (DNOModel.slug == slug)
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                return existing, False
            
            # If still not found, re-raise the error
            raise
    
    async def find_location_by_hash(
        self,
        db: AsyncSession,
        address_hash: str,
    ) -> LocationModel | None:
        """Find location by pre-computed address hash."""
        result = await db.execute(
            select(LocationModel).where(LocationModel.address_hash == address_hash)
        )
        return result.scalar_one_or_none()
    
    async def find_location_by_geocoord(
        self,
        db: AsyncSession,
        lat: float,
        lon: float,
        tolerance: float = 0.0001,
    ) -> LocationModel | None:
        """
        Find location by coordinates with spatial tolerance.
        
        Tolerance 0.0001° ≈ 11 meters at equator.
        Uses ABS comparison to avoid float precision issues.
        """
        snapped_lat = snap_coordinate(lat)
        snapped_lon = snap_coordinate(lon)
        
        result = await db.execute(
            select(LocationModel).where(
                func.abs(LocationModel.latitude - snapped_lat) < tolerance,
                func.abs(LocationModel.longitude - snapped_lon) < tolerance,
            )
        )
        return result.scalar_one_or_none()
    
    async def get_or_create_location(
        self,
        db: AsyncSession,
        dno_id: int,
        address: NormalizedAddress,
        lat: float,
        lon: float,
    ) -> tuple[LocationModel, bool]:
        """
        Get existing or create new location.
        
        Returns: (location, created) - created=True if new record
        
        Race-condition safe: uses IntegrityError fallback.
        """
        log = self.log.bind(address_hash=address.address_hash[:16], dno_id=dno_id)
        
        # First, try to find existing by hash
        existing = await self.find_location_by_hash(db, address.address_hash)
        if existing:
            log.debug("Location already exists", location_id=existing.id)
            return existing, False
        
        # Create new location
        location = LocationModel(
            dno_id=dno_id,
            address_hash=address.address_hash,
            street_clean=address.street_clean,
            number_clean=address.number_clean,
            zip_code=address.zip_code,
            city=address.city,
            latitude=snap_coordinate(lat),
            longitude=snap_coordinate(lon),
            source="vnb_digital",
        )
        
        try:
            db.add(location)
            await db.commit()
            await db.refresh(location)
            log.info("Created location", location_id=location.id)
            return location, True
        except IntegrityError as e:
            # Race condition
            await db.rollback()
            log.warning("Race condition on location create, fetching existing", error=str(e))
            existing = await self.find_location_by_hash(db, address.address_hash)
            if existing:
                return existing, False
            raise


# Singleton instance for easy import
skeleton_service = SkeletonService()
