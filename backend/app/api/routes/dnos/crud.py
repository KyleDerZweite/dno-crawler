"""
CRUD operations for DNO management.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, delete, exists, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import User as AuthUser
from app.core.auth import get_current_user
from app.core.config import settings
from app.core.models import APIResponse
from app.db import CrawlJobModel, DNOModel, HLZFModel, NetzentgelteModel, get_db
from app.services.completeness import build_completeness_payload, connection_points_from_mastr

from .schemas import CreateDNORequest, UpdateDNORequest
from .utils import slugify

router = APIRouter()


def _build_mastr_stats_payload(dno: DNOModel) -> dict | None:
    """Build MaStR statistics payload for API responses."""
    mastr = dno.mastr_data
    if not mastr:
        return None

    has_stats = any(
        value is not None
        for value in (
            mastr.connection_points_total,
            mastr.networks_count,
            mastr.total_capacity_mw,
            mastr.solar_units,
            mastr.wind_units,
            mastr.storage_units,
            mastr.stats_data_quality,
            mastr.stats_computed_at,
        )
    )
    if not has_stats:
        return None

    return {
        "connection_points": {
            "total": mastr.connection_points_total,
            "by_canonical_level": mastr.connection_points_by_level,
            "by_voltage": {
                "ns": mastr.connection_points_ns,
                "ms": mastr.connection_points_ms,
                "hs": mastr.connection_points_hs,
                "hoe": mastr.connection_points_hoe,
            },
        },
        "networks": {
            "count": mastr.networks_count,
            "has_customers": mastr.has_customers,
            "closed_distribution_network": mastr.closed_distribution_network,
        },
        "installed_capacity_mw": {
            "total": float(mastr.total_capacity_mw)
            if mastr.total_capacity_mw is not None
            else None,
            "solar": float(mastr.solar_capacity_mw)
            if mastr.solar_capacity_mw is not None
            else None,
            "wind": float(mastr.wind_capacity_mw) if mastr.wind_capacity_mw is not None else None,
            "storage": float(mastr.storage_capacity_mw)
            if mastr.storage_capacity_mw is not None
            else None,
            "biomass": float(mastr.biomass_capacity_mw)
            if mastr.biomass_capacity_mw is not None
            else None,
            "hydro": float(mastr.hydro_capacity_mw)
            if mastr.hydro_capacity_mw is not None
            else None,
        },
        "unit_counts": {
            "solar": mastr.solar_units,
            "wind": mastr.wind_units,
            "storage": mastr.storage_units,
        },
        "data_quality": mastr.stats_data_quality,
        "computed_at": mastr.stats_computed_at.isoformat() if mastr.stats_computed_at else None,
    }


async def _build_completeness_payload(
    db: AsyncSession,
    dno: DNOModel,
) -> dict:
    """Build completeness score payload for a single DNO.

    Queries distinct voltage levels from Netzentgelte/HLZF tables
    and delegates scoring to the completeness service.
    """
    # Query distinct voltage levels that have data for this DNO
    netz_result = await db.execute(
        select(NetzentgelteModel.voltage_level.distinct()).where(NetzentgelteModel.dno_id == dno.id)
    )
    hlzf_result = await db.execute(
        select(HLZFModel.voltage_level.distinct()).where(HLZFModel.dno_id == dno.id)
    )

    actual_netz = {row[0] for row in netz_result.fetchall()}
    actual_hlzf = {row[0] for row in hlzf_result.fetchall()}

    return build_completeness_payload(
        connection_points=connection_points_from_mastr(dno.mastr_data),
        actual_netz_levels=actual_netz,
        actual_hlzf_levels=actual_hlzf,
        include_levels=True,
    )


def _compute_similarity_threshold(query_length: int) -> float:
    """Return tuned trigram threshold by query length.

    These thresholds were chosen to reduce false negatives for short German city names
    (e.g. "Ulm", "Bonn") where trigram similarity naturally under-scores exact intent.
    """
    if query_length <= 3:
        return 0.08
    if query_length <= 6:
        return 0.12
    return 0.2


def _calculate_dno_live_status(
    *,
    crawlable: bool,
    data_points_count: int,
    running_jobs: int,
    pending_jobs: int,
) -> str:
    """Calculate DNO live status from preloaded counters."""
    if running_jobs > 0:
        return "running"
    if pending_jobs > 0:
        return "pending"
    if data_points_count > 0:
        return "crawled"
    if not crawlable:
        return "protected"
    return "uncrawled"


def _serialize_dno_list_item(
    *,
    dno: DNOModel,
    netzentgelte_count: int,
    hlzf_count: int,
    include_stats: bool,
    live_status: str,
) -> dict:
    """Serialize one DNO list item payload."""
    data_points_count = netzentgelte_count + hlzf_count
    score = min(round((data_points_count / 50) * 100), 100) if data_points_count > 0 else 0

    dno_data = {
        "id": str(dno.id),
        "slug": dno.slug,
        "name": dno.name,
        "official_name": dno.official_name,
        "vnb_id": dno.vnb_id,
        "status": live_status,
        "description": dno.description,
        "region": dno.region,
        "website": dno.website,
        "crawlable": dno.crawlable,
        "crawl_blocked_reason": dno.crawl_blocked_reason,
        "data_points_count": data_points_count,
        "netzentgelte_count": netzentgelte_count,
        "hlzf_count": hlzf_count,
        "score": score,
        "created_at": dno.created_at.isoformat() if dno.created_at else None,
        "updated_at": dno.updated_at.isoformat() if dno.updated_at else None,
    }

    if include_stats:
        dno_data["stats"] = {
            "years_available": [],
            "last_crawl": None,
            "mastr": _build_mastr_stats_payload(dno),
        }

    return dno_data


def _serialize_mastr_data(dno: DNOModel) -> dict | None:
    """Serialize MaStR source payload for detail endpoint."""
    if not dno.mastr_data:
        return None

    m = dno.mastr_data
    return {
        "mastr_nr": m.mastr_nr,
        "download_url": m.download_url,
        "federal_state": m.federal_state,
        "operator_name": m.operator_name,
        "operator_legal_form": m.operator_legal_form,
        "operator_address": m.operator_address,
        "operator_city": m.operator_city,
        "operator_zip": m.operator_zip,
        "operator_country": m.operator_country,
        "connection_points_ns": m.connection_points_ns,
        "connection_points_ms": m.connection_points_ms,
        "connection_points_hs": m.connection_points_hs,
        "connection_points_hoe": m.connection_points_hoe,
        "connection_points_total": m.connection_points_total,
        "connection_points_by_level": m.connection_points_by_level,
        "networks_count": m.networks_count,
        "has_customers": m.has_customers,
        "closed_distribution_network": m.closed_distribution_network,
        "solar_units": m.solar_units,
        "solar_capacity_mw": float(m.solar_capacity_mw)
        if m.solar_capacity_mw is not None
        else None,
        "wind_units": m.wind_units,
        "wind_capacity_mw": float(m.wind_capacity_mw) if m.wind_capacity_mw is not None else None,
        "storage_units": m.storage_units,
        "storage_capacity_mw": float(m.storage_capacity_mw)
        if m.storage_capacity_mw is not None
        else None,
        "biomass_units": m.biomass_units,
        "biomass_capacity_mw": float(m.biomass_capacity_mw)
        if m.biomass_capacity_mw is not None
        else None,
        "hydro_units": m.hydro_units,
        "hydro_capacity_mw": float(m.hydro_capacity_mw)
        if m.hydro_capacity_mw is not None
        else None,
        "total_capacity_mw": float(m.total_capacity_mw)
        if m.total_capacity_mw is not None
        else None,
        "stats_data_quality": m.stats_data_quality,
        "stats_computed_at": m.stats_computed_at.isoformat() if m.stats_computed_at else None,
        "mastr_last_updated": m.mastr_last_updated.isoformat() if m.mastr_last_updated else None,
        "last_synced_at": m.last_synced_at.isoformat() if m.last_synced_at else None,
    }


def _serialize_vnb_data(dno: DNOModel) -> dict | None:
    """Serialize VNB source payload for detail endpoint."""
    if not dno.vnb_data:
        return None

    v = dno.vnb_data
    return {
        "vnb_id": v.vnb_id,
        "name": v.name,
        "official_name": v.official_name,
        "homepage_url": v.homepage_url,
        "phone": v.phone,
        "email": v.email,
        "address": v.address,
        "types": v.types,
        "voltage_types": v.voltage_types,
        "logo_url": v.logo_url,
        "is_electricity": v.is_electricity,
        "last_synced_at": v.last_synced_at.isoformat() if v.last_synced_at else None,
    }


def _serialize_bdew_data_list(dno: DNOModel) -> list[dict]:
    """Serialize BDEW source records for detail endpoint."""
    if not dno.bdew_data:
        return []

    return [
        {
            "bdew_code": b.bdew_code,
            "bdew_internal_id": b.bdew_internal_id,
            "bdew_company_uid": b.bdew_company_uid,
            "company_name": b.company_name,
            "market_function": b.market_function,
            "contact_name": b.contact_name,
            "contact_phone": b.contact_phone,
            "contact_email": b.contact_email,
            "street": b.street,
            "zip_code": b.zip_code,
            "city": b.city,
            "website": b.website,
            "is_grid_operator": b.is_grid_operator,
            "last_synced_at": b.last_synced_at.isoformat() if b.last_synced_at else None,
        }
        for b in dno.bdew_data
    ]


@router.get("/search-vnb")
async def search_vnb(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    q: str = Query(..., min_length=2, max_length=100, description="Search term for DNO name"),
) -> APIResponse:
    """
    Search VNB Digital for DNO names for autocomplete/validation.

    Returns matching VNBs with indicator if they already exist in our database.
    """
    from app.services.vnb import VNBDigitalClient

    vnb_client = VNBDigitalClient(request_delay=0.5)
    try:
        vnb_results = await vnb_client.search_vnb(q)

        # Check which VNBs already exist in our database
        suggestions = []
        for vnb in vnb_results:
            # Check if this VNB already exists by vnb_id
            existing_query = select(DNOModel).where(DNOModel.vnb_id == vnb.vnb_id)
            result = await db.execute(existing_query)
            existing_dno = result.scalar_one_or_none()

            suggestions.append(
                {
                    "vnb_id": vnb.vnb_id,
                    "name": vnb.name,
                    "subtitle": vnb.subtitle,
                    "logo_url": vnb.logo_url,
                    "exists": existing_dno is not None,
                    "existing_dno_id": str(existing_dno.id) if existing_dno else None,
                    "existing_dno_slug": existing_dno.slug if existing_dno else None,
                }
            )

        return APIResponse(
            success=True,
            data={
                "suggestions": suggestions,
                "count": len(suggestions),
            },
        )
    finally:
        await vnb_client.close()


@router.get("/search-vnb/{vnb_id}/details")
async def get_vnb_details(
    vnb_id: str,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> APIResponse:
    """
    Get extended details for a specific VNB (website, phone, email, address).

    Used when user selects a suggestion to auto-fill the form.
    """
    from app.services.vnb import VNBDigitalClient

    vnb_client = VNBDigitalClient(request_delay=0.5)
    try:
        details = await vnb_client.get_vnb_details(vnb_id)
    finally:
        await vnb_client.close()

    if not details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"VNB with ID '{vnb_id}' not found",
        )

    # Try to enrich address with postal code + city from Impressum
    enriched_address = details.address
    if details.homepage_url and details.address:
        from app.services.impressum_extractor import impressum_extractor

        full_addr = await impressum_extractor.extract_full_address(
            details.homepage_url,
            details.address,
        )
        if full_addr:
            enriched_address = full_addr.formatted

    return APIResponse(
        success=True,
        data={
            "vnb_id": details.vnb_id,
            "name": details.name,
            "website": details.homepage_url,
            "phone": details.phone,
            "email": details.email,
            "address": enriched_address,
        },
    )


@router.post("/")
async def create_dno(
    request: CreateDNORequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> APIResponse:
    """
    Create a new DNO.

    If slug is not provided, it will be auto-generated from the name.
    If vnb_id is provided, validates against VNB Digital and fetches missing details.
    """
    from app.services.dno_creation import resolve_dno_creation_data

    # Generate slug if not provided
    slug = request.slug if request.slug else slugify(request.name)

    # Check for duplicate slug
    existing_query = select(DNOModel).where(DNOModel.slug == slug)
    result = await db.execute(existing_query)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A DNO with slug '{slug}' already exists",
        )

    # Check for duplicate vnb_id if provided
    if request.vnb_id:
        existing_vnb_query = select(DNOModel).where(DNOModel.vnb_id == request.vnb_id)
        result = await db.execute(existing_vnb_query)
        existing_dno = result.scalar_one_or_none()
        if existing_dno:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A DNO with VNB ID '{request.vnb_id}' already exists: {existing_dno.name}",
            )

    resolved = await resolve_dno_creation_data(
        vnb_id=request.vnb_id,
        official_name=request.official_name,
        website=request.website,
        phone=request.phone,
        email=request.email,
        contact_address=request.contact_address,
    )

    # Create DNO
    dno = DNOModel(
        name=request.name,
        slug=slug,
        official_name=resolved.official_name,
        description=request.description,
        region=request.region,
        website=resolved.website,
        vnb_id=request.vnb_id,
        phone=resolved.phone,
        email=resolved.email,
        contact_address=resolved.contact_address,
        # Crawlability info
        crawlable=resolved.crawlable,
        crawl_blocked_reason=resolved.crawl_blocked_reason,
        robots_txt=resolved.robots_txt,
        sitemap_urls=resolved.sitemap_urls,
        disallow_paths=resolved.disallow_paths,
        # Tech Info
        cms_system=resolved.tech_info.get("cms") if resolved.tech_info else None,
        tech_stack_details=resolved.tech_info,
    )
    db.add(dno)
    await db.commit()
    await db.refresh(dno)

    return APIResponse(
        success=True,
        message=f"DNO '{dno.name}' created successfully",
        data={
            "id": str(dno.id),
            "slug": dno.slug,
            "name": dno.name,
            "official_name": dno.official_name,
            "vnb_id": dno.vnb_id,
            "description": dno.description,
            "region": dno.region,
            "website": dno.website,
            "phone": dno.phone,
            "email": dno.email,
            "contact_address": dno.contact_address,
            "crawlable": dno.crawlable,
            "crawl_blocked_reason": dno.crawl_blocked_reason,
            "created_at": dno.created_at.isoformat() if dno.created_at else None,
        },
    )


@router.get("/stats")
async def get_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> APIResponse:
    """
    Get dashboard statistics for authenticated users.

    Returns counts for DNOs, data points, and active jobs.
    """
    # Count DNOs
    dno_count = await db.scalar(select(func.count(DNOModel.id)))

    # Count data points
    netzentgelte_count = await db.scalar(select(func.count(NetzentgelteModel.id)))
    hlzf_count = await db.scalar(select(func.count(HLZFModel.id)))

    # Count active jobs
    pending_jobs = await db.scalar(
        select(func.count(CrawlJobModel.id)).where(CrawlJobModel.status == "pending")
    )
    running_jobs = await db.scalar(
        select(func.count(CrawlJobModel.id)).where(CrawlJobModel.status == "running")
    )

    return APIResponse(
        success=True,
        data={
            "total_dnos": dno_count or 0,
            "netzentgelte_count": netzentgelte_count or 0,
            "hlzf_count": hlzf_count or 0,
            "total_data_points": (netzentgelte_count or 0) + (hlzf_count or 0),
            "active_crawls": (pending_jobs or 0) + (running_jobs or 0),
        },
    )


@router.get("/")
async def list_dnos_detailed(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    include_stats: bool = Query(False),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, description="Items per page (25, 50, 100, 250)"),
    q: str | None = Query(None, description="Search term"),
    status_filter: str | None = Query(
        None,
        alias="status",
        description="Filter by status: uncrawled, crawled, running, pending, protected",
    ),
    sort_by: str = Query(
        "name_asc", description="Sort by: name_asc, name_desc, score_asc, score_desc, region_asc"
    ),
) -> APIResponse:
    """
    List all DNOs with detailed information (paginated).

    Status is computed dynamically from active jobs:
    - running: at least one running job
    - pending: at least one pending job (none running)
    - crawled: has data points and no active jobs
    - uncrawled: no data points and no active jobs
    - protected: crawlable=False (blocked by robots.txt, Cloudflare, etc.)
    """
    # Validate per_page
    allowed_per_page = [25, 50, 100, 250]
    if per_page not in allowed_per_page:
        per_page = 50  # Default to 50 if invalid

    # Base query
    query = select(DNOModel).options(selectinload(DNOModel.mastr_data))

    # Apply search filter if provided
    if q:
        # =======================================================================
        # HYBRID SEARCH: Combines multiple strategies for robust matching
        # =======================================================================
        # Strategy 1: ILIKE contains - catches exact substrings like "Ulm"
        # Strategy 2: Trigram similarity - fuzzy matching for typos
        # Strategy 3: Region matching - search in region field too
        # =======================================================================

        q_normalized = q.strip().lower()
        q_len = len(q_normalized)

        similarity_threshold = _compute_similarity_threshold(q_len)

        # Trigram similarity score
        similarity = func.similarity(DNOModel.name, q)

        # ILIKE pattern for contains matching (case-insensitive)
        # Escape ILIKE wildcards to prevent wildcard injection
        q_escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        ilike_pattern = f"%{q_escaped}%"
        contains_match = DNOModel.name.ilike(ilike_pattern)
        region_match = DNOModel.region.ilike(ilike_pattern)

        # Combined filter: Match if ANY strategy succeeds
        # This ensures short queries like "Ulm" work via ILIKE even if trigram fails
        combined_filter = or_(
            similarity > similarity_threshold,  # Fuzzy match
            contains_match,  # Exact substring in name
            region_match,  # Match in region
        )

        # Scoring: Prioritize exact matches, then fuzzy matches
        # CASE expression to boost exact substring matches
        exact_boost = case(
            (contains_match, 2.0),  # Boost for exact substring match
            else_=0.0,
        )
        region_boost = case(
            (region_match, 0.5),  # Small boost for region match
            else_=0.0,
        )

        # Combined score: trigram similarity + bonuses for exact matches
        combined_score = similarity + exact_boost + region_boost

        # Don't apply default sort for search - use relevance
        query = query.filter(combined_filter)
        search_order = combined_score.desc()

        # Count with combined filter
        count_query = select(func.count()).select_from(DNOModel).where(combined_filter)
    else:
        search_order = None
        # Total count without filter
        count_query = select(func.count()).select_from(DNOModel)

    # Apply status filter at SQL level using EXISTS subqueries
    if status_filter:
        _running_exists = exists(
            select(CrawlJobModel.id).where(
                CrawlJobModel.dno_id == DNOModel.id,
                CrawlJobModel.status == "running",
            )
        )
        _pending_exists = exists(
            select(CrawlJobModel.id).where(
                CrawlJobModel.dno_id == DNOModel.id,
                CrawlJobModel.status == "pending",
            )
        )
        _netz_exists = exists(
            select(NetzentgelteModel.id).where(
                NetzentgelteModel.dno_id == DNOModel.id,
            )
        )
        _hlzf_exists = exists(
            select(HLZFModel.id).where(
                HLZFModel.dno_id == DNOModel.id,
            )
        )

        if status_filter == "protected":
            status_clause = DNOModel.crawlable == False  # noqa: E712
        elif status_filter == "running":
            status_clause = _running_exists
        elif status_filter == "pending":
            status_clause = ~_running_exists & _pending_exists
        elif status_filter == "crawled":
            status_clause = ~_running_exists & ~_pending_exists & (_netz_exists | _hlzf_exists)
        elif status_filter == "uncrawled":
            status_clause = (
                ~_running_exists
                & ~_pending_exists
                & ~_netz_exists
                & ~_hlzf_exists
                & (DNOModel.crawlable == True)  # noqa: E712
            )
        else:
            status_clause = None

        if status_clause is not None:
            query = query.filter(status_clause)
            count_query = count_query.where(status_clause)

    # Apply sorting (unless searching - then relevance takes priority)
    if q and search_order is not None:
        # For search, use relevance score as primary sort
        query = query.order_by(search_order, DNOModel.name)
    # Apply explicit sort
    elif sort_by == "name_desc":
        query = query.order_by(DNOModel.name.desc())
    elif sort_by == "region_asc":
        query = query.order_by(DNOModel.region.asc().nullslast(), DNOModel.name)
    elif sort_by == "region_desc":
        query = query.order_by(DNOModel.region.desc().nullslast(), DNOModel.name)
    else:  # Default: name_asc
        query = query.order_by(DNOModel.name)

    total_count_result = await db.execute(count_query)
    total = total_count_result.scalar() or 0
    total_pages = (total + per_page - 1) // per_page  # Ceiling division

    # Clamp page to valid range
    if page > total_pages > 0:
        page = total_pages
    elif total_pages == 0:
        page = 1

    # Calculate offset
    offset = (page - 1) * per_page

    # Paginated query
    query = query.offset(offset).limit(per_page)
    result = await db.execute(query)
    dnos = result.scalars().all()

    if not dnos:
        return APIResponse(
            success=True,
            data=[],
            meta={"total": total, "page": page, "per_page": per_page, "total_pages": total_pages},
        )

    # Get DNO IDs for batch queries
    dno_ids = [dno.id for dno in dnos]

    # Batch query for netzentgelte counts
    netz_counts_result = await db.execute(
        text("""
            SELECT dno_id, COUNT(*) as count
            FROM netzentgelte
            WHERE dno_id = ANY(:dno_ids)
            GROUP BY dno_id
        """),
        {"dno_ids": dno_ids},
    )
    netz_counts = {row[0]: row[1] for row in netz_counts_result.fetchall()}

    # Batch query for HLZF counts
    hlzf_counts_result = await db.execute(
        text("""
            SELECT dno_id, COUNT(*) as count
            FROM hlzf
            WHERE dno_id = ANY(:dno_ids)
            GROUP BY dno_id
        """),
        {"dno_ids": dno_ids},
    )
    hlzf_counts = {row[0]: row[1] for row in hlzf_counts_result.fetchall()}

    # Batch query for job statuses
    job_status_result = await db.execute(
        text("""
            SELECT dno_id, status, COUNT(*) as count
            FROM crawl_jobs
            WHERE dno_id = ANY(:dno_ids) AND status IN ('running', 'pending')
            GROUP BY dno_id, status
        """),
        {"dno_ids": dno_ids},
    )
    job_statuses = {}
    for row in job_status_result.fetchall():
        dno_id, job_status_val, count = row
        if dno_id not in job_statuses:
            job_statuses[dno_id] = {"running": 0, "pending": 0}
        job_statuses[dno_id][job_status_val] = count

    data = []
    for dno in dnos:
        netzentgelte_count = netz_counts.get(dno.id, 0)
        hlzf_count = hlzf_counts.get(dno.id, 0)
        data_points_count = netzentgelte_count + hlzf_count

        # Compute live status from batch-loaded job data
        job_status = job_statuses.get(dno.id, {"running": 0, "pending": 0})
        live_status = _calculate_dno_live_status(
            crawlable=dno.crawlable,
            data_points_count=data_points_count,
            running_jobs=job_status["running"],
            pending_jobs=job_status["pending"],
        )

        dno_data = _serialize_dno_list_item(
            dno=dno,
            netzentgelte_count=netzentgelte_count,
            hlzf_count=hlzf_count,
            include_stats=include_stats,
            live_status=live_status,
        )

        data.append(dno_data)

    # Sort by score if requested (post-fetch since score is computed)
    if sort_by == "score_desc":
        data.sort(key=lambda x: x["score"], reverse=True)
    elif sort_by == "score_asc":
        data.sort(key=lambda x: x["score"], reverse=False)

    return APIResponse(
        success=True,
        data=data,
        meta={"total": total, "page": page, "per_page": per_page, "total_pages": total_pages},
    )


@router.get("/{dno_id}")
async def get_dno_details(
    dno_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> APIResponse:
    """Get detailed information about a specific DNO by ID or slug."""
    from pathlib import Path

    # Try to find by numeric ID first, then by slug
    # Eagerly load source data
    dno = None
    if dno_id.isdigit():
        query = (
            select(DNOModel)
            .options(
                selectinload(DNOModel.mastr_data),
                selectinload(DNOModel.vnb_data),
                selectinload(DNOModel.bdew_data),
            )
            .where(DNOModel.id == int(dno_id))
        )
        result = await db.execute(query)
        dno = result.scalar_one_or_none()

    if not dno:
        query = (
            select(DNOModel)
            .options(
                selectinload(DNOModel.mastr_data),
                selectinload(DNOModel.vnb_data),
                selectinload(DNOModel.bdew_data),
            )
            .where(DNOModel.slug == dno_id.lower())
        )
        result = await db.execute(query)
        dno = result.scalar_one_or_none()

    if not dno:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DNO not found",
        )

    # Check if local files exist for this DNO
    storage_path = settings.storage_path
    dno_dir = Path(storage_path) / "downloads" / dno.slug
    has_local_files = dno_dir.exists() and any(dno_dir.iterdir())

    # -------------------------------------------------------------------------
    # Dynamic Status Computation
    # -------------------------------------------------------------------------
    # Get counts and active jobs for live status
    stats_query = text("""
        SELECT
            (SELECT COUNT(*) FROM netzentgelte WHERE dno_id = :dno_id) as netz_count,
            (SELECT COUNT(*) FROM hlzf WHERE dno_id = :dno_id) as hlzf_count,
            (SELECT COUNT(*) FROM crawl_jobs WHERE dno_id = :dno_id AND status = 'running') as running_jobs,
            (SELECT COUNT(*) FROM crawl_jobs WHERE dno_id = :dno_id AND status = 'pending') as pending_jobs
    """)
    stats_res = await db.execute(stats_query, {"dno_id": dno.id})
    netz_c, hlzf_c, running_j, pending_j = stats_res.fetchone()

    mastr_data = _serialize_mastr_data(dno)
    vnb_data = _serialize_vnb_data(dno)
    bdew_data = _serialize_bdew_data_list(dno)

    if running_j > 0:
        live_status = "running"
    elif pending_j > 0:
        live_status = "pending"
    elif (netz_c + hlzf_c) > 0:
        live_status = "crawled"
    elif not dno.crawlable:
        live_status = "protected"
    else:
        live_status = "uncrawled"

    return APIResponse(
        success=True,
        data={
            "id": str(dno.id),
            "slug": dno.slug,
            "name": dno.name,
            "official_name": dno.official_name,
            "vnb_id": dno.vnb_id,
            "mastr_nr": dno.mastr_nr,
            "primary_bdew_code": dno.primary_bdew_code,
            "status": live_status,
            "description": dno.description,
            "region": dno.region,
            "website": dno.website,
            "phone": dno.phone,
            "email": dno.email,
            "display_name": dno.display_name,
            "display_website": dno.display_website,
            "display_phone": dno.display_phone,
            "display_email": dno.display_email,
            "contact_address": dno.contact_address,
            "address_components": dno.address_components,
            "marktrollen": dno.marktrollen,
            "acer_code": dno.acer_code,
            "grid_operator_bdew_code": dno.grid_operator_bdew_code,
            "crawlable": dno.crawlable,
            "crawl_blocked_reason": dno.crawl_blocked_reason,
            "has_local_files": has_local_files,
            "robots_txt": dno.robots_txt,
            "sitemap_urls": dno.sitemap_urls,
            "cms_system": dno.cms_system,
            "tech_stack_details": dno.tech_stack_details,
            "has_mastr": dno.has_mastr,
            "has_vnb": dno.has_vnb,
            "has_bdew": dno.has_bdew,
            "enrichment_sources": dno.enrichment_sources,
            "mastr_data": mastr_data,
            "vnb_data": vnb_data,
            "bdew_data": bdew_data,
            "stats": _build_mastr_stats_payload(dno),
            "completeness": await _build_completeness_payload(db, dno),
            "created_at": dno.created_at.isoformat() if dno.created_at else None,
            "updated_at": dno.updated_at.isoformat() if dno.updated_at else None,
        },
    )


@router.patch("/{dno_id}")
async def update_dno(
    dno_id: int,
    request: UpdateDNORequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> APIResponse:
    """Update DNO metadata (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    dno = await db.get(DNOModel, dno_id)
    if not dno:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DNO not found")

    # Update only provided fields
    if request.name is not None:
        dno.name = request.name
    if request.official_name is not None:
        dno.official_name = request.official_name
    if request.description is not None:
        dno.description = request.description
    if request.region is not None:
        dno.region = request.region
    if request.website is not None:
        dno.website = request.website
    if request.phone is not None:
        dno.phone = request.phone
    if request.email is not None:
        dno.email = request.email
    if request.contact_address is not None:
        dno.contact_address = request.contact_address

    await db.commit()
    await db.refresh(dno)

    return APIResponse(
        success=True,
        message=f"DNO '{dno.name}' updated successfully",
        data={"id": str(dno.id)},
    )


@router.delete("/{dno_id}")
async def delete_dno(
    dno_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> APIResponse:
    """Delete DNO and all associated data (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    dno = await db.get(DNOModel, dno_id)
    if not dno:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DNO not found")

    dno_name = dno.name

    # Delete associated data (cascade should handle this, but being explicit)
    from app.db.models import LocationModel

    # Delete locations
    await db.execute(delete(LocationModel).where(LocationModel.dno_id == dno_id))
    # Delete netzentgelte
    await db.execute(delete(NetzentgelteModel).where(NetzentgelteModel.dno_id == dno_id))
    # Delete HLZF
    await db.execute(delete(HLZFModel).where(HLZFModel.dno_id == dno_id))
    # Delete crawl jobs
    await db.execute(delete(CrawlJobModel).where(CrawlJobModel.dno_id == dno_id))

    # Delete the DNO itself
    await db.delete(dno)
    await db.commit()

    return APIResponse(
        success=True,
        message=f"DNO '{dno_name}' and all associated data deleted successfully",
        data={"id": str(dno_id)},
    )
