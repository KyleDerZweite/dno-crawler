"""
Public Search API with Lazy Registration.

Decoupled from heavy crawl jobs. Returns existing data or registers
skeleton DNO/Location records via VNB Digital API.

Rate limited: 60 req/min per IP, 50 req/min global VNB quota.
"""


import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limiter import RateLimiter, get_client_ip, get_rate_limiter
from app.db import DNOModel, HLZFModel, LocationModel, NetzentgelteModel, get_db
from app.services.vnb import (
    NormalizedAddress,
    VNBDigitalClient,
    normalize_address,
    skeleton_service,
)

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
    dno_id: str | None = Field(None, max_length=100, pattern=r"^[a-zA-Z0-9_-]*$")
    dno_name: str | None = Field(None, max_length=200)


class PublicSearchRequest(BaseModel):
    """Public search request - one of three input types."""
    address: AddressSearchInput | None = None
    coordinates: CoordinatesSearchInput | None = None
    dno: DNOSearchInput | None = None
    year: int | None = Field(None, ge=2000, le=2100)  # Single year (backward compat)
    years: list[int] | None = Field(None, description="Multiple years filter")


class DNOMetadata(BaseModel):
    """Lightweight DNO info."""
    id: int
    slug: str
    name: str
    official_name: str | None = None
    vnb_id: str | None = None
    status: str


class LocationInfo(BaseModel):
    """Location info."""
    street: str
    number: str | None = None
    zip_code: str
    city: str
    latitude: float
    longitude: float


class NetzentgelteData(BaseModel):
    """Netzentgelte data."""
    year: int
    voltage_level: str
    leistung: float | None = None
    arbeit: float | None = None
    leistung_unter_2500h: float | None = None
    arbeit_unter_2500h: float | None = None
    verification_status: str | None = None


class HLZFTimeRange(BaseModel):
    """Parsed time range with start and end times."""
    start: str  # e.g., "12:15:00"
    end: str    # e.g., "13:15:00"


def _parse_hlzf_times(value: str | None) -> list[HLZFTimeRange] | None:
    """
    Parse HLZF time string into structured time ranges.

    Handles various formats:
    - "12:15-13:15, 16:45-19:45" (comma-separated, hyphen)
    - "12:15-13:15\n16:45-19:45" (newline-separated)
    - "08:00 – 12:00" (en-dash with spaces)
    - "18:00 20:00" (space instead of hyphen - AI error)
    - "entfällt" or "-" (no data)

    Returns list of HLZFTimeRange or None if no valid ranges.
    """
    import re

    if not value or value.strip() == "-" or value.strip().lower() == "entfällt":
        return None

    ranges = []

    # Normalize time helper
    def normalize_time(t: str) -> str:
        parts = t.split(':')
        hour = parts[0].zfill(2)
        minute = parts[1] if len(parts) > 1 else "00"
        second = parts[2] if len(parts) > 2 else "00"
        return f"{hour}:{minute}:{second}"

    # Split by comma OR newline to get individual periods
    # This handles both "12:15-13:15, 16:45-19:45" and "12:15-13:15\n16:45-19:45"
    periods = re.split(r'[,\n]', value)

    for period in periods:
        period = period.strip()
        if not period:
            continue

        # Match any dash type: hyphen (-), en-dash (–), em-dash (—)
        # Allow optional spaces around the dash
        match = re.match(
            r'^(\d{1,2}:\d{2}(?::\d{2})?)\s*[-–—]\s*(\d{1,2}:\d{2}(?::\d{2})?)$',
            period
        )

        if match:
            start_time = normalize_time(match.group(1))
            end_time = normalize_time(match.group(2))
            ranges.append(HLZFTimeRange(start=start_time, end=end_time))
            continue

        # Handle AI error: "18:00 20:00" (space instead of hyphen between two times)
        space_match = re.match(
            r'^(\d{1,2}:\d{2}(?::\d{2})?)\s+(\d{1,2}:\d{2}(?::\d{2})?)$',
            period
        )
        if space_match:
            start_time = normalize_time(space_match.group(1))
            end_time = normalize_time(space_match.group(2))
            ranges.append(HLZFTimeRange(start=start_time, end=end_time))

    return ranges if ranges else None


class HLZFData(BaseModel):
    """HLZF data with both raw strings and parsed time ranges."""
    year: int
    voltage_level: str
    # Raw string values (for display fallback)
    winter: str | None = None
    fruehling: str | None = None
    sommer: str | None = None
    herbst: str | None = None
    # Parsed time ranges (for structured display)
    winter_ranges: list[HLZFTimeRange] | None = None
    fruehling_ranges: list[HLZFTimeRange] | None = None
    sommer_ranges: list[HLZFTimeRange] | None = None
    herbst_ranges: list[HLZFTimeRange] | None = None
    # Verification status
    verification_status: str | None = None


class PublicSearchResponse(BaseModel):
    """Response for public search."""
    found: bool
    has_data: bool
    dno: DNOMetadata | None = None
    location: LocationInfo | None = None
    netzentgelte: list[NetzentgelteData] | None = None
    hlzf: list[HLZFData] | None = None
    message: str | None = None


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
        return await _search_by_dno(db, request.dno, filter_years, log, rate_limiter)


# =============================================================================
# Search Handlers
# =============================================================================


async def _search_by_address(
    db: AsyncSession,
    rate_limiter: RateLimiter | None,
    address_input: AddressSearchInput,
    years: list[int] | None,
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

    # Step 7: Try to enrich address with postal code + city from Impressum
    enriched_address = dno_details.address if dno_details else None
    if dno_details and dno_details.homepage_url and dno_details.address:
        from app.services.impressum_extractor import impressum_extractor
        full_addr = await impressum_extractor.extract_full_address(
            dno_details.homepage_url,
            dno_details.address,
        )
        if full_addr:
            enriched_address = full_addr.formatted

    # Step 8: Fetch robots.txt to determine crawlability
    robots_result = None
    if dno_details and dno_details.homepage_url:
        import httpx

        from app.services.robots_parser import fetch_robots_txt

        async with httpx.AsyncClient(
            headers={"User-Agent": "DNO-Crawler/1.0"},
            follow_redirects=True,
            timeout=10.0,
        ) as http_client:
            robots_result = await fetch_robots_txt(http_client, dno_details.homepage_url)

    # Step 9: Create or get DNO skeleton with contact info and crawlability
    dno, dno_created = await skeleton_service.get_or_create_dno(
        db,
        name=vnb.name,
        vnb_id=vnb.vnb_id,
        official_name=vnb.official_name,
        website=dno_details.homepage_url if dno_details else None,
        phone=dno_details.phone if dno_details else None,
        email=dno_details.email if dno_details else None,
        contact_address=enriched_address,
        # Crawlability info
        robots_txt=robots_result.raw_content if robots_result else None,
        sitemap_urls=robots_result.sitemap_urls if robots_result else None,
        disallow_paths=robots_result.disallow_paths if robots_result else None,
        crawlable=robots_result.crawlable if robots_result else True,
        crawl_blocked_reason=robots_result.blocked_reason if robots_result else None,
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
    rate_limiter: RateLimiter | None,
    coords_input: CoordinatesSearchInput,
    years: list[int] | None,
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

    # Try to enrich address with postal code + city from Impressum
    enriched_address = dno_details.address if dno_details else None
    if dno_details and dno_details.homepage_url and dno_details.address:
        from app.services.impressum_extractor import impressum_extractor
        full_addr = await impressum_extractor.extract_full_address(
            dno_details.homepage_url,
            dno_details.address,
        )
        if full_addr:
            enriched_address = full_addr.formatted

    # Fetch robots.txt to determine crawlability
    robots_result = None
    if dno_details and dno_details.homepage_url:
        import httpx

        from app.services.robots_parser import fetch_robots_txt

        async with httpx.AsyncClient(
            headers={"User-Agent": "DNO-Crawler/1.0"},
            follow_redirects=True,
            timeout=10.0,
        ) as http_client:
            robots_result = await fetch_robots_txt(http_client, dno_details.homepage_url)

    dno, _ = await skeleton_service.get_or_create_dno(
        db,
        name=vnb.name,
        vnb_id=vnb.vnb_id,
        website=dno_details.homepage_url if dno_details else None,
        phone=dno_details.phone if dno_details else None,
        email=dno_details.email if dno_details else None,
        contact_address=enriched_address,
        # Crawlability info
        robots_txt=robots_result.raw_content if robots_result else None,
        sitemap_urls=robots_result.sitemap_urls if robots_result else None,
        disallow_paths=robots_result.disallow_paths if robots_result else None,
        crawlable=robots_result.crawlable if robots_result else True,
        crawl_blocked_reason=robots_result.blocked_reason if robots_result else None,
    )

    # Create simple location without full address
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
    years: list[int] | None,
    log,
    rate_limiter: "RateLimiter | None" = None,
) -> PublicSearchResponse:
    """
    Search by DNO name or ID directly.
    
    Waterfall logic:
    1. Search local DB with fuzzy matching
    2. If not found, search VNB Digital API by name
    3. If VNB returns results, create skeleton DNO
    """
    log = log.bind(dno_name=dno_input.dno_name, dno_id=dno_input.dno_id)

    # Build query for local DB search
    if dno_input.dno_id:
        query = select(DNOModel).where(DNOModel.vnb_id == dno_input.dno_id)
    elif dno_input.dno_name:
        # Fuzzy search: match name, official_name, or slug
        search_term = dno_input.dno_name.strip()
        query = select(DNOModel).where(
            (DNOModel.name.ilike(f"%{search_term}%")) |
            (DNOModel.official_name.ilike(f"%{search_term}%")) |
            (DNOModel.slug == search_term.lower().replace(" ", "-"))
        )
    else:
        raise HTTPException(400, "Either dno_id or dno_name must be provided")

    result = await db.execute(query)
    dno = result.scalars().first()

    if dno:
        log.info("Found DNO in local database", dno_id=dno.id, dno_name=dno.name)
        return await _build_response(db, dno, None, years)

    # Not found in DB - try VNB Digital API for fuzzy search
    log.info("DNO not in local DB, searching VNB Digital API")
    
    search_name = dno_input.dno_name or dno_input.dno_id
    if not search_name:
        return PublicSearchResponse(
            found=False,
            has_data=False,
            message="DNO not found. Try searching by address instead.",
        )

    if rate_limiter:
        await rate_limiter.before_vnb_call()

    vnb_client = VNBDigitalClient(request_delay=0.5)
    vnb_results = await vnb_client.search_vnb(search_name)

    if not vnb_results:
        log.warning("No VNB found for search term", search_term=search_name)
        return PublicSearchResponse(
            found=False,
            has_data=False,
            message=f"No distribution network operator found matching '{search_name}'. Try searching by address instead.",
        )

    # Use the first (best) match
    vnb = vnb_results[0]
    log.info("Found VNB via API", vnb_id=vnb.vnb_id, vnb_name=vnb.name)

    # Fetch extended details (website, contact info)
    if rate_limiter:
        await rate_limiter.before_vnb_call()

    dno_details = await vnb_client.get_vnb_details(vnb.vnb_id)

    # Try to enrich address with postal code + city from Impressum
    enriched_address = dno_details.address if dno_details else None
    if dno_details and dno_details.homepage_url and dno_details.address:
        from app.services.impressum_extractor import impressum_extractor
        full_addr = await impressum_extractor.extract_full_address(
            dno_details.homepage_url,
            dno_details.address,
        )
        if full_addr:
            enriched_address = full_addr.formatted

    # Fetch robots.txt to determine crawlability
    robots_result = None
    if dno_details and dno_details.homepage_url:
        import httpx

        from app.services.robots_parser import fetch_robots_txt

        async with httpx.AsyncClient(
            headers={"User-Agent": "DNO-Crawler/1.0"},
            follow_redirects=True,
            timeout=10.0,
        ) as http_client:
            robots_result = await fetch_robots_txt(http_client, dno_details.homepage_url)

    # Create or get DNO skeleton
    dno, dno_created = await skeleton_service.get_or_create_dno(
        db,
        name=vnb.name,
        vnb_id=vnb.vnb_id,
        official_name=vnb.subtitle,  # VNB subtitle is usually the official/legal name
        website=dno_details.homepage_url if dno_details else None,
        phone=dno_details.phone if dno_details else None,
        email=dno_details.email if dno_details else None,
        contact_address=enriched_address,
        # Crawlability info
        robots_txt=robots_result.raw_content if robots_result else None,
        sitemap_urls=robots_result.sitemap_urls if robots_result else None,
        disallow_paths=robots_result.disallow_paths if robots_result else None,
        crawlable=robots_result.crawlable if robots_result else True,
        crawl_blocked_reason=robots_result.blocked_reason if robots_result else None,
    )

    log.info(
        "Created DNO skeleton from VNB search",
        dno_created=dno_created,
        dno_name=dno.name,
        has_website=bool(dno.website),
    )

    return await _build_response(db, dno, None, years)


async def _build_response(
    db: AsyncSession,
    dno: DNOModel,
    location: LocationModel | None,
    years: list[int] | None,
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
            leistung_unter_2500h=getattr(n, 'leistung_unter_2500h', None),
            arbeit_unter_2500h=getattr(n, 'arbeit_unter_2500h', None),
            verification_status=getattr(n, 'verification_status', None),
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
            winter_ranges=_parse_hlzf_times(h.winter),
            fruehling_ranges=_parse_hlzf_times(h.fruehling),
            sommer_ranges=_parse_hlzf_times(h.sommer),
            herbst_ranges=_parse_hlzf_times(h.herbst),
            verification_status=getattr(h, 'verification_status', None),
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
