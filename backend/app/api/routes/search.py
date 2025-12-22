"""
Public Search API with Lazy Registration.

Decoupled from heavy crawl jobs. Returns existing data or registers
skeleton DNO/Location records via VNB Digital API.

Rate limited: 60 req/min per IP, 50 req/min global VNB quota.
"""

from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limiter import get_client_ip, get_rate_limiter, RateLimiter
from app.db import get_db, DNOModel, HLZFModel, NetzentgelteModel, LocationModel
from app.services.skeleton_service import (
    normalize_address,
    skeleton_service,
    NormalizedAddress,
)
from app.services.vnb_digital import VNBDigitalClient

logger = structlog.get_logger()
router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================


class AddressSearchInput(BaseModel):
    """Address search input with strict validation."""
    street: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Street with house number",
    )
    zip_code: str = Field(
        ...,
        min_length=4,
        max_length=5,
        pattern=r"^\d{4,5}$",
        description="German postal code (4-5 digits)",
    )
    city: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="City name",
    )


class CoordinatesSearchInput(BaseModel):
    """Coordinates search input."""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class DNOSearchInput(BaseModel):
    """Direct DNO search input with validation."""
    dno_id: Optional[str] = Field(None, max_length=100, pattern=r"^[a-zA-Z0-9_-]*$")
    dno_name: Optional[str] = Field(None, max_length=200)


class PublicSearchRequest(BaseModel):
    """Public search request - one of three input types."""
    address: Optional[AddressSearchInput] = None
    coordinates: Optional[CoordinatesSearchInput] = None
    dno: Optional[DNOSearchInput] = None
    year: Optional[int] = Field(None, ge=2000, le=2100)  # Single year (backward compat)
    years: Optional[list[int]] = Field(None, description="Multiple years filter")


class DNOMetadata(BaseModel):
    """Lightweight DNO info."""
    id: int
    slug: str
    name: str
    official_name: Optional[str] = None
    vnb_id: Optional[str] = None
    status: str


class LocationInfo(BaseModel):
    """Location info."""
    street: str
    number: Optional[str] = None
    zip_code: str
    city: str
    latitude: float
    longitude: float


class NetzentgelteData(BaseModel):
    """Netzentgelte data."""
    year: int
    voltage_level: str
    leistung: Optional[float] = None
    arbeit: Optional[float] = None


class HLZFData(BaseModel):
    """HLZF data."""
    year: int
    voltage_level: str
    winter: Optional[str] = None
    fruehling: Optional[str] = None
    sommer: Optional[str] = None
    herbst: Optional[str] = None


class PublicSearchResponse(BaseModel):
    """Response for public search."""
    found: bool
    has_data: bool
    dno: Optional[DNOMetadata] = None
    location: Optional[LocationInfo] = None
    netzentgelte: Optional[list[NetzentgelteData]] = None
    hlzf: Optional[list[HLZFData]] = None
    message: Optional[str] = None


# =============================================================================
# Endpoints
# =============================================================================


@router.post(
    "/",
    response_model=PublicSearchResponse,
    summary="Public Search with Lazy Registration",
    responses={
        200: {"description": "DNO found with data"},
        202: {"description": "DNO registered (skeleton), no data yet"},
        429: {"description": "Rate limit exceeded"},
        503: {"description": "External API quota exhausted"},
    },
)
async def public_search(
    request: PublicSearchRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Public Search API with Lazy Registration.
    
    Accepts address, coordinates, or DNO name.
    Returns existing data or registers skeleton for future crawling.
    
    **Rate Limits:**
    - 60 requests/minute per IP
    - 50 VNB API calls/minute globally
    """
    log = logger.bind(endpoint="public_search")
    
    # Get rate limiter and client IP
    try:
        rate_limiter = get_rate_limiter()
        client_ip = get_client_ip(http_request)
        await rate_limiter.check_ip_limit(client_ip)
    except RuntimeError:
        # Rate limiter not initialized (dev mode without Redis)
        log.warning("Rate limiter not available")
        rate_limiter = None
        client_ip = "unknown"
    
    # Validate exactly one input type provided
    inputs_provided = sum([
        request.address is not None,
        request.coordinates is not None,
        request.dno is not None,
    ])
    if inputs_provided != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exactly one of 'address', 'coordinates', or 'dno' must be provided.",
        )
    
    # Merge year/years into a single list
    filter_years = request.years if request.years else ([request.year] if request.year else None)
    
    # Route to appropriate handler
    if request.address:
        return await _search_by_address(
            db, rate_limiter, request.address, filter_years, log
        )
    elif request.coordinates:
        return await _search_by_coordinates(
            db, rate_limiter, request.coordinates, filter_years, log
        )
    else:
        return await _search_by_dno(db, request.dno, filter_years, log)


# =============================================================================
# Search Handlers
# =============================================================================


async def _search_by_address(
    db: AsyncSession,
    rate_limiter: Optional[RateLimiter],
    address_input: AddressSearchInput,
    years: Optional[list[int]],
    log,
) -> PublicSearchResponse:
    """
    Waterfall logic for address search:
    1. Normalize address → hash
    2. Check DB for existing hash → Location
    3. If found → get DNO → evaluate data
    4. If not found → call VNB API → create skeleton → evaluate data
    """
    log = log.bind(zip=address_input.zip_code, city=address_input.city)
    
    # Step 1: Normalize address
    normalized = normalize_address(
        address_input.street,
        address_input.zip_code,
        address_input.city,
    )
    log.debug("Address normalized", hash=normalized.address_hash[:16])
    
    # Step 2: Check DB for existing location by hash
    location = await skeleton_service.find_location_by_hash(db, normalized.address_hash)
    
    if location:
        log.debug("Location found in cache", location_id=location.id)
        dno = await db.get(DNOModel, location.dno_id)
        return await _build_response(db, dno, location, years)
    
    # Step 3: Not in cache - call VNB Digital API
    log.info("Cache miss, calling VNB Digital API")
    
    if rate_limiter:
        await rate_limiter.before_vnb_call()
    
    vnb_client = VNBDigitalClient(request_delay=0.5)
    
    # Get coordinates
    full_address = f"{address_input.street}, {address_input.zip_code} {address_input.city}"
    location_result = await vnb_client.search_address(full_address)
    
    if not location_result:
        log.warning("Address not found in VNB Digital")
        return PublicSearchResponse(
            found=False,
            has_data=False,
            message="Address not found. Please check the address and try again.",
        )
    
    # Parse coordinates
    lat, lon = map(float, location_result.coordinates.split(","))
    
    # Step 4: Check if we have a location for these coordinates
    if rate_limiter:
        await rate_limiter.before_vnb_call()
    
    existing_location = await skeleton_service.find_location_by_geocoord(db, lat, lon)
    
    if existing_location:
        log.debug("Location found by coordinates", location_id=existing_location.id)
        dno = await db.get(DNOModel, existing_location.dno_id)
        
        # Create location alias for this address hash
        await skeleton_service.get_or_create_location(
            db, existing_location.dno_id, normalized, lat, lon
        )
        
        return await _build_response(db, dno, existing_location, years)
    
    # Step 5: Get DNO from VNB Digital
    vnbs = await vnb_client.lookup_by_coordinates(location_result.coordinates)
    
    if not vnbs:
        log.warning("No DNO found for coordinates")
        return PublicSearchResponse(
            found=False,
            has_data=False,
            message="No distribution network operator found for this location.",
        )
    
    # Prefer electricity DNO
    vnb = next((v for v in vnbs if v.is_electricity), vnbs[0])
    
    # Step 6: Fetch extended details (homepage URL, contact info)
    if rate_limiter:
        await rate_limiter.before_vnb_call()
    
    dno_details = await vnb_client.get_vnb_details(vnb.vnb_id)
    
    # Step 7: Create or get DNO skeleton with contact info
    dno, dno_created = await skeleton_service.get_or_create_dno(
        db,
        name=vnb.name,
        vnb_id=vnb.vnb_id,
        official_name=vnb.official_name,
        website=dno_details.homepage_url if dno_details else None,
        phone=dno_details.phone if dno_details else None,
        email=dno_details.email if dno_details else None,
        contact_address=dno_details.address if dno_details else None,
    )
    
    # Step 8: Create location
    location, loc_created = await skeleton_service.get_or_create_location(
        db, dno.id, normalized, lat, lon
    )
    
    log.info(
        "Created skeleton",
        dno_created=dno_created,
        loc_created=loc_created,
        dno_name=dno.name,
        has_website=bool(dno.website),
    )
    
    return await _build_response(db, dno, location, years)


async def _search_by_coordinates(
    db: AsyncSession,
    rate_limiter: Optional[RateLimiter],
    coords_input: CoordinatesSearchInput,
    years: Optional[list[int]],
    log,
) -> PublicSearchResponse:
    """Search by coordinates - similar to address but skips geocoding."""
    log = log.bind(lat=coords_input.latitude, lon=coords_input.longitude)
    
    # Check DB first
    location = await skeleton_service.find_location_by_geocoord(
        db, coords_input.latitude, coords_input.longitude
    )
    
    if location:
        dno = await db.get(DNOModel, location.dno_id)
        return await _build_response(db, dno, location, years)
    
    # Call VNB Digital
    log.info("Calling VNB Digital for coordinates")
    
    if rate_limiter:
        await rate_limiter.before_vnb_call()
    
    vnb_client = VNBDigitalClient(request_delay=0.5)
    coords_str = f"{coords_input.latitude},{coords_input.longitude}"
    vnbs = await vnb_client.lookup_by_coordinates(coords_str)
    
    if not vnbs:
        return PublicSearchResponse(
            found=False,
            has_data=False,
            message="No distribution network operator found for these coordinates.",
        )
    
    vnb = next((v for v in vnbs if v.is_electricity), vnbs[0])
    
    # Fetch extended details
    if rate_limiter:
        await rate_limiter.before_vnb_call()
    
    dno_details = await vnb_client.get_vnb_details(vnb.vnb_id)
    
    dno, _ = await skeleton_service.get_or_create_dno(
        db,
        name=vnb.name,
        vnb_id=vnb.vnb_id,
        website=dno_details.homepage_url if dno_details else None,
        phone=dno_details.phone if dno_details else None,
        email=dno_details.email if dno_details else None,
        contact_address=dno_details.address if dno_details else None,
    )
    
    # Create simple location without full address
    from app.services.skeleton_service import NormalizedAddress
    import hashlib
    
    coords_hash = hashlib.sha256(coords_str.encode()).hexdigest()
    simple_address = NormalizedAddress(
        street_clean=f"Coordinates ({coords_input.latitude:.4f}, {coords_input.longitude:.4f})",
        number_clean=None,
        zip_code="00000",
        city="Unknown",
        address_hash=coords_hash,
    )
    
    location, _ = await skeleton_service.get_or_create_location(
        db, dno.id, simple_address, coords_input.latitude, coords_input.longitude
    )
    
    return await _build_response(db, dno, location, years)


async def _search_by_dno(
    db: AsyncSession,
    dno_input: DNOSearchInput,
    years: Optional[list[int]],
    log,
) -> PublicSearchResponse:
    """Search by DNO name or ID directly."""
    log = log.bind(dno_name=dno_input.dno_name, dno_id=dno_input.dno_id)
    
    # Build query
    if dno_input.dno_id:
        query = select(DNOModel).where(DNOModel.vnb_id == dno_input.dno_id)
    elif dno_input.dno_name:
        query = select(DNOModel).where(
            (DNOModel.name.ilike(f"%{dno_input.dno_name}%")) |
            (DNOModel.slug == dno_input.dno_name.lower())
        )
    else:
        raise HTTPException(400, "Either dno_id or dno_name must be provided")
    
    result = await db.execute(query)
    dno = result.scalar_one_or_none()
    
    if not dno:
        return PublicSearchResponse(
            found=False,
            has_data=False,
            message=f"DNO not found. Try searching by address instead.",
        )
    
    return await _build_response(db, dno, None, years)


async def _build_response(
    db: AsyncSession,
    dno: DNOModel,
    location: Optional[LocationModel],
    years: Optional[list[int]],
) -> PublicSearchResponse:
    """Build response with data evaluation."""
    
    # Build DNO metadata
    dno_meta = DNOMetadata(
        id=dno.id,
        slug=dno.slug,
        name=dno.name,
        official_name=dno.official_name,
        vnb_id=dno.vnb_id,
        status=dno.status,
    )
    
    # Build location info
    loc_info = None
    if location:
        loc_info = LocationInfo(
            street=location.street_clean,
            number=location.number_clean,
            zip_code=location.zip_code,
            city=location.city,
            latitude=float(location.latitude),
            longitude=float(location.longitude),
        )
    
    # Check for data
    netzentgelte_query = select(NetzentgelteModel).where(NetzentgelteModel.dno_id == dno.id)
    hlzf_query = select(HLZFModel).where(HLZFModel.dno_id == dno.id)
    
    if years:
        netzentgelte_query = netzentgelte_query.where(NetzentgelteModel.year.in_(years))
        hlzf_query = hlzf_query.where(HLZFModel.year.in_(years))
    
    netzentgelte_result = await db.execute(netzentgelte_query)
    hlzf_result = await db.execute(hlzf_query)
    
    netzentgelte = [
        NetzentgelteData(
            year=n.year,
            voltage_level=n.voltage_level,
            leistung=n.leistung,
            arbeit=n.arbeit,
        )
        for n in netzentgelte_result.scalars().all()
    ]
    
    hlzf = [
        HLZFData(
            year=h.year,
            voltage_level=h.voltage_level,
            winter=h.winter,
            fruehling=h.fruehling,
            sommer=h.sommer,
            herbst=h.herbst,
        )
        for h in hlzf_result.scalars().all()
    ]
    
    has_data = len(netzentgelte) > 0 or len(hlzf) > 0
    
    # Build message for skeleton DNOs
    message = None
    if not has_data:
        message = f"DNO '{dno.name}' registered. No detailed data available yet. Request crawl via dashboard."
    
    return PublicSearchResponse(
        found=True,
        has_data=has_data,
        dno=dno_meta,
        location=loc_info,
        netzentgelte=netzentgelte if netzentgelte else None,
        hlzf=hlzf if hlzf else None,
        message=message,
    )
