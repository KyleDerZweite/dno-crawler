"""
DNO management routes (authenticated).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, select, text, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user, User as AuthUser
from app.core.models import APIResponse, CrawlJob, CrawlJobCreate, DataType
from app.core.rate_limiter import get_client_ip
from app.db import CrawlJobModel, DNOModel, get_db
from app.db.source_models import DNOMastrData, DNOVnbData, DNOBdewData

router = APIRouter()


class TriggerCrawlRequest(BaseModel):
    year: int
    data_type: DataType = DataType.ALL
    priority: int = 5


class CreateDNORequest(BaseModel):
    """Request model for creating a new DNO."""
    name: str
    slug: str | None = None  # Auto-generate if not provided
    official_name: str | None = None
    description: str | None = None
    region: str | None = None
    website: str | None = None
    vnb_id: str | None = None  # VNB Digital ID for validation/deduplication
    phone: str | None = None
    email: str | None = None
    contact_address: str | None = None


def _slugify(name: str) -> str:
    """Generate a URL-friendly slug from a name."""
    import re
    # Convert to lowercase
    slug = name.lower()
    # Replace spaces and special chars with hyphens
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    # Remove leading/trailing hyphens
    slug = slug.strip('-')
    # Collapse multiple hyphens
    slug = re.sub(r'-+', '-', slug)
    return slug


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
    vnb_results = await vnb_client.search_vnb(q)
    
    # Check which VNBs already exist in our database
    suggestions = []
    for vnb in vnb_results:
        # Check if this VNB already exists by vnb_id
        existing_query = select(DNOModel).where(DNOModel.vnb_id == vnb.vnb_id)
        result = await db.execute(existing_query)
        existing_dno = result.scalar_one_or_none()
        
        suggestions.append({
            "vnb_id": vnb.vnb_id,
            "name": vnb.name,
            "subtitle": vnb.subtitle,
            "logo_url": vnb.logo_url,
            "exists": existing_dno is not None,
            "existing_dno_id": str(existing_dno.id) if existing_dno else None,
            "existing_dno_slug": existing_dno.slug if existing_dno else None,
        })
    
    return APIResponse(
        success=True,
        data={
            "suggestions": suggestions,
            "count": len(suggestions),
        },
    )


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
    details = await vnb_client.get_vnb_details(vnb_id)
    
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
    from app.services.vnb import VNBDigitalClient
    
    # Generate slug if not provided
    slug = request.slug if request.slug else _slugify(request.name)
    
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
    
    # Fetch VNB details if vnb_id provided and some fields are missing
    website = request.website
    phone = request.phone
    email = request.email
    contact_address = request.contact_address
    official_name = request.official_name
    
    if request.vnb_id and not all([website, phone, email]):
        vnb_client = VNBDigitalClient(request_delay=0.5)
        vnb_details = await vnb_client.get_vnb_details(request.vnb_id)
        if vnb_details:
            website = website or vnb_details.homepage_url
            phone = phone or vnb_details.phone
            email = email or vnb_details.email
            
            # Try to enrich address with postal code + city from Impressum
            if not contact_address and vnb_details.address and vnb_details.homepage_url:
                from app.services.impressum_extractor import impressum_extractor
                full_addr = await impressum_extractor.extract_full_address(
                    vnb_details.homepage_url,
                    vnb_details.address,
                )
                if full_addr:
                    contact_address = full_addr.formatted
                else:
                    contact_address = vnb_details.address
            elif not contact_address:
                contact_address = vnb_details.address
    
    # Check robots.txt for Cloudflare/JS protection if we have a website
    crawlable = True
    crawl_blocked_reason = None
    robots_txt = None
    sitemap_urls = None
    disallow_paths = None
    
    if website:
        from app.services.robots_parser import fetch_robots_txt
        import httpx
        
        async with httpx.AsyncClient(
            headers={"User-Agent": "DNO-Crawler/1.0"},
            follow_redirects=True,
            timeout=10.0,
        ) as http_client:
            robots_result = await fetch_robots_txt(http_client, website)
            if robots_result:
                crawlable = robots_result.crawlable
                crawl_blocked_reason = robots_result.blocked_reason
                robots_txt = robots_result.raw_content
                sitemap_urls = robots_result.sitemap_urls
                disallow_paths = robots_result.disallow_paths
    
    # Create DNO
    dno = DNOModel(
        name=request.name,
        slug=slug,
        official_name=official_name,
        description=request.description,
        region=request.region,
        website=website,
        vnb_id=request.vnb_id,
        phone=phone,
        email=email,
        contact_address=contact_address,
        # Crawlability info from robots.txt check
        crawlable=crawlable,
        crawl_blocked_reason=crawl_blocked_reason,
        robots_txt=robots_txt,
        sitemap_urls=sitemap_urls,
        disallow_paths=disallow_paths,
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


@router.get("/")
async def list_dnos_detailed(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    include_stats: bool = Query(False),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, description="Items per page (25, 50, 100, 250)"),
    q: str | None = Query(None, description="Search term"),
) -> APIResponse:
    """
    List all DNOs with detailed information (paginated).
    
    Status is computed dynamically from active jobs:
    - running: at least one running job
    - pending: at least one pending job (none running)
    - crawled: has data points and no active jobs
    - uncrawled: no data points and no active jobs
    """
    # Validate per_page
    allowed_per_page = [25, 50, 100, 250]
    if per_page not in allowed_per_page:
        per_page = 50  # Default to 50 if invalid
    
    # Base query
    query = select(DNOModel)
    
    # Apply search filter if provided
    if q:
        search_filter = or_(
            DNOModel.name.ilike(f"%{q}%"),
            DNOModel.official_name.ilike(f"%{q}%"),
            DNOModel.region.ilike(f"%{q}%"),
            DNOModel.vnb_id.ilike(f"%{q}%")
        )
        query = query.where(search_filter)
        
        # Count with filter
        count_query = select(func.count()).select_from(DNOModel).where(search_filter)
    else:
        # Total count without filter
        count_query = select(func.count()).select_from(DNOModel)

    total_count_result = await db.execute(count_query)
    total = total_count_result.scalar() or 0
    total_pages = (total + per_page - 1) // per_page  # Ceiling division
    
    # Clamp page to valid range
    if page > total_pages and total_pages > 0:
        page = total_pages
    elif total_pages == 0:
        page = 1
    
    # Calculate offset
    offset = (page - 1) * per_page
    
    # Paginated query
    query = query.order_by(DNOModel.name).offset(offset).limit(per_page)
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
        {"dno_ids": dno_ids}
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
        {"dno_ids": dno_ids}
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
        {"dno_ids": dno_ids}
    )
    job_statuses = {}
    for row in job_status_result.fetchall():
        dno_id, status, count = row
        if dno_id not in job_statuses:
            job_statuses[dno_id] = {"running": 0, "pending": 0}
        job_statuses[dno_id][status] = count
    
    data = []
    for dno in dnos:
        netzentgelte_count = netz_counts.get(dno.id, 0)
        hlzf_count = hlzf_counts.get(dno.id, 0)
        data_points_count = netzentgelte_count + hlzf_count
        
        # Compute live status from batch-loaded job data
        job_status = job_statuses.get(dno.id, {"running": 0, "pending": 0})
        if job_status["running"] > 0:
            live_status = "running"
        elif job_status["pending"] > 0:
            live_status = "pending"
        elif data_points_count > 0:
            live_status = "crawled"
        else:
            live_status = "uncrawled"
        
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
            "data_points_count": data_points_count,
            "netzentgelte_count": netzentgelte_count,
            "hlzf_count": hlzf_count,
            "created_at": dno.created_at.isoformat() if dno.created_at else None,
            "updated_at": dno.updated_at.isoformat() if dno.updated_at else None,
        }
        
        if include_stats:
            dno_data["stats"] = {
                "years_available": [],
                "last_crawl": None,
            }
        
        data.append(dno_data)
    
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
    import os
    from pathlib import Path
    storage_path = os.environ.get("STORAGE_PATH", "/data")
    dno_dir = Path(storage_path) / "downloads" / dno.slug
    has_local_files = dno_dir.exists() and any(dno_dir.iterdir())
    
    # Build MaStR source data
    mastr_data = None
    if dno.mastr_data:
        m = dno.mastr_data
        mastr_data = {
            "mastr_nr": m.mastr_nr,
            "acer_code": m.acer_code,
            "registered_name": m.registered_name,
            "region": m.region,
            "address_components": m.address_components,
            "contact_address": m.contact_address,
            "marktrollen": m.marktrollen,
            "is_active": m.is_active,
            "closed_network": m.closed_network,
            "activity_start": m.activity_start.isoformat() if m.activity_start else None,
            "activity_end": m.activity_end.isoformat() if m.activity_end else None,
            "registration_date": m.registration_date.isoformat() if m.registration_date else None,
            "mastr_last_updated": m.mastr_last_updated.isoformat() if m.mastr_last_updated else None,
            "last_synced_at": m.last_synced_at.isoformat() if m.last_synced_at else None,
        }
    
    # Build VNB source data
    vnb_data = None
    if dno.vnb_data:
        v = dno.vnb_data
        vnb_data = {
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
    
    # Build BDEW source data (one-to-many)
    bdew_data = []
    if dno.bdew_data:
        for b in dno.bdew_data:
            bdew_data.append({
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
            })
        
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
            "status": getattr(dno, 'status', 'uncrawled'),
            "description": dno.description,
            "region": dno.region,
            "website": dno.website,
            "phone": dno.phone,
            "email": dno.email,
            # Computed display fields
            "display_name": dno.display_name,
            "display_website": dno.display_website,
            "display_phone": dno.display_phone,
            "display_email": dno.display_email,
            "contact_address": dno.contact_address,
            "address_components": dno.address_components,
            "marktrollen": dno.marktrollen,
            "acer_code": dno.acer_code,
            "grid_operator_bdew_code": dno.grid_operator_bdew_code,
            # Crawlability info
            "crawlable": getattr(dno, 'crawlable', True),
            "crawl_blocked_reason": getattr(dno, 'crawl_blocked_reason', None),
            "has_local_files": has_local_files,
            # Source data availability
            "has_mastr": dno.has_mastr,
            "has_vnb": dno.has_vnb,
            "has_bdew": dno.has_bdew,
            "enrichment_sources": dno.enrichment_sources,
            # Source data objects
            "mastr_data": mastr_data,
            "vnb_data": vnb_data,
            "bdew_data": bdew_data,
            "created_at": dno.created_at.isoformat() if dno.created_at else None,
            "updated_at": dno.updated_at.isoformat() if dno.updated_at else None,
        },
    )


class UpdateDNORequest(BaseModel):
    """Request model for updating DNO metadata."""
    name: str | None = None
    official_name: str | None = None
    description: str | None = None
    region: str | None = None
    website: str | None = None
    phone: str | None = None
    email: str | None = None
    contact_address: str | None = None


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
    from sqlalchemy import delete
    from app.db.models import NetzentgelteModel, HLZFModel, CrawlJobModel, LocationModel
    
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


@router.post("/{dno_id}/crawl")
async def trigger_crawl(
    dno_id: str,
    request: TriggerCrawlRequest,
    http_request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> APIResponse:
    """
    Trigger a crawl job for a specific DNO.
    
    Creates a new crawl job that will be picked up by the worker.
    Any authenticated user (member or admin) can trigger this.
    Accepts either numeric ID or slug.
    """
    from datetime import datetime, timedelta, timezone
    from arq import create_pool
    from arq.connections import RedisSettings
    from app.core.config import settings
    import structlog
    logger = structlog.get_logger()
    
    # Verify DNO exists - support both ID and slug
    if dno_id.isdigit():
        query = select(DNOModel).where(DNOModel.id == int(dno_id))
    else:
        query = select(DNOModel).where(DNOModel.slug == dno_id)
    result = await db.execute(query)
    dno = result.scalar_one_or_none()
    
    if not dno:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DNO not found",
        )
    
    # Check DNO status for stuck jobs (locked > 1 hour)
    dno_status = getattr(dno, 'status', 'uncrawled')
    if dno_status == "crawling":
        locked_at = getattr(dno, 'crawl_locked_at', None)
        # Use timezone-aware comparison
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(hours=1)
        # Make locked_at timezone-aware if it's naive
        if locked_at:
            if locked_at.tzinfo is None:
                locked_at = locked_at.replace(tzinfo=timezone.utc)
            if locked_at < threshold:
                logger.warning("Force-releasing stuck crawl", dno_id=dno_id)
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A crawl is already in progress for {dno.name}",
            )
    
    # Check for existing pending/running job for this year AND data_type
    existing_query = select(CrawlJobModel).where(
        CrawlJobModel.dno_id == dno.id,
        CrawlJobModel.year == request.year,
        CrawlJobModel.data_type == request.data_type.value,
        CrawlJobModel.status.in_(["pending", "running"]),
    )
    result = await db.execute(existing_query)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A crawl job for this DNO, year, and data type is already in progress",
        )
    
    # Update DNO status
    dno.status = "crawling"
    dno.crawl_locked_at = datetime.utcnow()
    
    # Create crawl job in database with initiator IP for User-Agent
    initiator_ip = get_client_ip(http_request)
    job = CrawlJobModel(
        dno_id=dno.id,
        year=request.year,
        data_type=request.data_type.value,
        priority=request.priority,
        current_step=f"Triggered by {current_user.email}",
        triggered_by=current_user.email,
        context={"initiator_ip": initiator_ip},
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # Enqueue job to arq worker queue
    try:
        redis_pool = await create_pool(
            RedisSettings.from_dsn(str(settings.redis_url))
        )
        await redis_pool.enqueue_job(
            "process_dno_crawl",
            job.id,
            _job_id=f"crawl_{job.id}",
        )
        await redis_pool.close()
    except Exception as e:
        logger.error("Failed to enqueue job to worker", job_id=job.id, error=str(e))
    
    return APIResponse(
        success=True,
        message=f"Crawl job created for {dno.name} ({request.year})",
        data={
            "job_id": str(job.id),
            "dno_id": str(dno_id),
            "dno_name": dno.name,
            "dno_status": "crawling",
            "year": request.year,
            "data_type": request.data_type.value,
            "status": job.status,
        },
    )


@router.get("/{dno_id}/data")
async def get_dno_data(
    dno_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    year: int | None = Query(None),
    data_type: DataType | None = Query(None),
) -> APIResponse:
    """Get all data for a specific DNO."""
    # Verify DNO exists
    query = select(DNOModel).where(DNOModel.id == dno_id)
    result = await db.execute(query)
    dno = result.scalar_one_or_none()
    
    if not dno:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DNO not found",
        )
    
    # Query netzentgelte data
    netzentgelte_query = text("""
        SELECT id, voltage_level, year, leistung, arbeit, leistung_unter_2500h, arbeit_unter_2500h, 
               verification_status, extraction_source, extraction_model, extraction_source_format,
               last_edited_by, last_edited_at
        FROM netzentgelte
        WHERE dno_id = :dno_id
        ORDER BY year DESC, voltage_level
    """)
    result = await db.execute(netzentgelte_query, {"dno_id": dno_id})
    netzentgelte_rows = result.fetchall()
    
    netzentgelte = []
    for row in netzentgelte_rows:
        netzentgelte.append({
            "id": row[0],
            "voltage_level": row[1],
            "year": row[2],
            "leistung": row[3],  # T >= 2500 h/a
            "arbeit": row[4],    # T >= 2500 h/a
            "leistung_unter_2500h": row[5],  # T < 2500 h/a
            "arbeit_unter_2500h": row[6],
            "verification_status": row[7],
            # Extraction source fields
            "extraction_source": row[8],
            "extraction_model": row[9],
            "extraction_source_format": row[10],
            "last_edited_by": row[11],
            "last_edited_at": row[12].isoformat() if row[12] else None,
        })
    
    # Query HLZF data
    hlzf_query = text("""
        SELECT id, voltage_level, year, winter, fruehling, sommer, herbst, 
               verification_status, extraction_source, extraction_model, extraction_source_format,
               last_edited_by, last_edited_at
        FROM hlzf
        WHERE dno_id = :dno_id
        ORDER BY year DESC, voltage_level
    """)
    result = await db.execute(hlzf_query, {"dno_id": dno_id})
    hlzf_rows = result.fetchall()
    
    # Import time parsing function from search module
    from app.api.routes.search import _parse_hlzf_times
    
    hlzf = []
    for row in hlzf_rows:
        winter_val = row[3]
        fruehling_val = row[4]
        sommer_val = row[5]
        herbst_val = row[6]
        
        hlzf.append({
            "id": row[0],
            "voltage_level": row[1],
            "year": row[2],
            "winter": winter_val,
            "fruehling": fruehling_val,
            "sommer": sommer_val,
            "herbst": herbst_val,
            # Parsed time ranges
            "winter_ranges": [{"start": r.start, "end": r.end} for r in (_parse_hlzf_times(winter_val) or [])],
            "fruehling_ranges": [{"start": r.start, "end": r.end} for r in (_parse_hlzf_times(fruehling_val) or [])],
            "sommer_ranges": [{"start": r.start, "end": r.end} for r in (_parse_hlzf_times(sommer_val) or [])],
            "herbst_ranges": [{"start": r.start, "end": r.end} for r in (_parse_hlzf_times(herbst_val) or [])],
            "verification_status": row[7],
            # Extraction source fields
            "extraction_source": row[8],
            "extraction_model": row[9],
            "extraction_source_format": row[10],
            "last_edited_by": row[11],
            "last_edited_at": row[12].isoformat() if row[12] else None,
        })
    
    return APIResponse(
        success=True,
        data={
            "dno": {
                "id": str(dno.id),
                "name": dno.name,
            },
            "netzentgelte": netzentgelte,
            "hlzf": hlzf,
        },
    )


@router.get("/{dno_id}/jobs")
async def get_dno_crawl_jobs(
    dno_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    limit: int = Query(10, ge=1, le=50),
) -> APIResponse:
    """Get recent crawl jobs for a DNO."""
    query = (
        select(CrawlJobModel)
        .where(CrawlJobModel.dno_id == dno_id)
        .order_by(CrawlJobModel.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    return APIResponse(
        success=True,
        data=[
            {
                "id": str(job.id),
                "year": job.year,
                "data_type": job.data_type,
                "status": job.status,
                "progress": job.progress,
                "current_step": job.current_step,
                "error_message": job.error_message,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "created_at": job.created_at.isoformat() if job.created_at else None,
            }
            for job in jobs
        ],
    )


class UpdateNetzentgelteRequest(BaseModel):
    """Request model for updating Netzentgelte."""
    leistung: float | None = None
    arbeit: float | None = None
    leistung_unter_2500h: float | None = None
    arbeit_unter_2500h: float | None = None


@router.patch("/{dno_id}/netzentgelte/{record_id}")
async def update_netzentgelte(
    dno_id: int,
    record_id: int,
    request: UpdateNetzentgelteRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> APIResponse:
    """Update a Netzentgelte record (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    
    from app.db import NetzentgelteModel
    
    query = select(NetzentgelteModel).where(
        NetzentgelteModel.id == record_id,
        NetzentgelteModel.dno_id == dno_id,
    )
    result = await db.execute(query)
    record = result.scalar_one_or_none()
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Record not found",
        )
    
    # Update only provided fields
    if request.leistung is not None:
        record.leistung = request.leistung
    if request.arbeit is not None:
        record.arbeit = request.arbeit
    if request.leistung_unter_2500h is not None:
        record.leistung_unter_2500h = request.leistung_unter_2500h
    if request.arbeit_unter_2500h is not None:
        record.arbeit_unter_2500h = request.arbeit_unter_2500h
    
    # Track manual edit
    from datetime import datetime, timezone
    record.extraction_source = "manual"
    record.last_edited_by = current_user.sub or current_user.email
    record.last_edited_at = datetime.now(timezone.utc)
    
    await db.commit()
    
    return APIResponse(
        success=True,
        message="Record updated successfully",
        data={"id": str(record.id)},
    )


@router.delete("/{dno_id}/netzentgelte/{record_id}")
async def delete_netzentgelte(
    dno_id: int,
    record_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> APIResponse:
    """Delete a Netzentgelte record (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    
    from app.db import NetzentgelteModel
    
    query = select(NetzentgelteModel).where(
        NetzentgelteModel.id == record_id,
        NetzentgelteModel.dno_id == dno_id,
    )
    result = await db.execute(query)
    record = result.scalar_one_or_none()
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Record not found",
        )
    
    await db.delete(record)
    await db.commit()
    
    return APIResponse(
        success=True,
        message="Record deleted successfully",
    )


class UpdateHLZFRequest(BaseModel):
    """Request model for updating HLZF."""
    winter: str | None = None
    fruehling: str | None = None
    sommer: str | None = None
    herbst: str | None = None


@router.patch("/{dno_id}/hlzf/{record_id}")
async def update_hlzf(
    dno_id: int,
    record_id: int,
    request: UpdateHLZFRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> APIResponse:
    """Update an HLZF record (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    
    from app.db import HLZFModel
    
    query = select(HLZFModel).where(
        HLZFModel.id == record_id,
        HLZFModel.dno_id == dno_id,
    )
    result = await db.execute(query)
    record = result.scalar_one_or_none()
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Record not found",
        )
    
    # Update only provided fields
    if request.winter is not None:
        record.winter = request.winter if request.winter != "" else None
    if request.fruehling is not None:
        record.fruehling = request.fruehling if request.fruehling != "" else None
    if request.sommer is not None:
        record.sommer = request.sommer if request.sommer != "" else None
    if request.herbst is not None:
        record.herbst = request.herbst if request.herbst != "" else None
    
    # Track manual edit
    from datetime import datetime, timezone
    record.extraction_source = "manual"
    record.last_edited_by = current_user.sub or current_user.email
    record.last_edited_at = datetime.now(timezone.utc)
    
    await db.commit()
    
    return APIResponse(
        success=True,
        message="Record updated successfully",
        data={"id": str(record.id)},
    )


@router.delete("/{dno_id}/hlzf/{record_id}")
async def delete_hlzf(
    dno_id: int,
    record_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> APIResponse:
    """Delete an HLZF record (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    
    from app.db import HLZFModel
    
    query = select(HLZFModel).where(
        HLZFModel.id == record_id,
        HLZFModel.dno_id == dno_id,
    )
    result = await db.execute(query)
    record = result.scalar_one_or_none()
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Record not found",
        )
    
    await db.delete(record)
    await db.commit()
    
    return APIResponse(
        success=True,
        message="Record deleted successfully",
    )


@router.get("/{dno_id}/files")
async def list_dno_files(
    dno_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> APIResponse:
    """List available source files for a DNO (PDFs, HTMLs, etc)."""
    import os
    from pathlib import Path
    
    # Supported file extensions
    SUPPORTED_EXTENSIONS = {".pdf", ".html", ".htm", ".xlsx", ".xls", ".csv", ".docx"}
    
    # Verify DNO exists
    query = select(DNOModel).where(DNOModel.id == dno_id)
    result = await db.execute(query)
    dno = result.scalar_one_or_none()
    
    if not dno:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DNO not found",
        )
    
    # Look for files in both old path and new slug-based path
    storage_path = os.environ.get("STORAGE_PATH", "/data")
    files = []
    seen_names = set()  # Avoid duplicates
    
    # Check old path (data/downloads/)
    old_path = Path(storage_path) / "downloads"
    if old_path.exists():
        for f in old_path.glob(f"{dno.slug}-*.*"):
            if f.suffix.lower() in SUPPORTED_EXTENSIONS and f.name not in seen_names:
                seen_names.add(f.name)
                files.append({
                    "name": f.name,
                    "size": f.stat().st_size,
                    "path": f"/files/downloads/{f.name}",
                })
    
    # Check new path (data/downloads/<slug>/)
    new_path = Path(storage_path) / "downloads" / dno.slug
    if new_path.exists():
        for f in new_path.iterdir():
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS and f.name not in seen_names:
                seen_names.add(f.name)
                files.append({
                    "name": f.name,
                    "size": f.stat().st_size,
                    "path": f"/files/downloads/{dno.slug}/{f.name}",
                })
    
    # Sort by name for consistent ordering
    files.sort(key=lambda x: x["name"])
    
    return APIResponse(
        success=True,
        data=files,
    )


@router.post("/{dno_id}/upload")
async def upload_file(
    dno_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    file: UploadFile = File(...),
) -> APIResponse:
    """
    Upload a file for a DNO.
    
    Automatically detects data type and year from filename using weighted
    keyword scoring, then renames to canonical format: {data_type}-{year}.{ext}
    
    This enables extraction for protected DNOs where automated crawling fails.
    """
    import aiofiles
    import os
    from pathlib import Path
    import structlog
    
    from app.services.file_analyzer import file_analyzer
    
    logger = structlog.get_logger()
    
    # Find DNO by ID or slug
    dno = None
    if isinstance(dno_id, int) or str(dno_id).isdigit():
        query = select(DNOModel).where(DNOModel.id == int(dno_id))
        result = await db.execute(query)
        dno = result.scalar_one_or_none()
    
    if not dno:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DNO not found",
        )
    
    # Analyze filename
    original_filename = file.filename or "unknown.pdf"
    data_type, year = file_analyzer.analyze(original_filename)
    
    if not data_type or not year:
        return APIResponse(
            success=False,
            message="Could not detect data type or year from filename",
            data={
                "detected_type": data_type,
                "detected_year": year,
                "filename": original_filename,
                "hint": "Rename file to include type keywords and year (e.g., preisblaetter-2025.pdf or zeitfenster-2025.pdf)",
            },
        )
    
    # Construct canonical filename (matches existing cache discovery pattern)
    extension = Path(original_filename).suffix.lower() or ".pdf"
    target_filename = f"{dno.slug}-{data_type}-{year}{extension}"
    
    storage_path = os.environ.get("STORAGE_PATH", "/data")
    target_dir = Path(storage_path) / "downloads" / dno.slug
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / target_filename
    
    # Save file (overwrites existing - user intent takes precedence)
    async with aiofiles.open(target_path, "wb") as f:
        content = await file.read()
        await f.write(content)
    
    logger.info(
        "File uploaded",
        original=original_filename,
        target=target_filename,
        detected_type=data_type,
        detected_year=year,
        dno=dno.slug,
        user=current_user.email,
    )
    
    return APIResponse(
        success=True,
        message=f"File saved as {target_filename}",
        data={
            "filename": target_filename,
            "path": f"/files/downloads/{dno.slug}/{target_filename}",
            "detected_type": data_type,
            "detected_year": year,
            "original_filename": original_filename,
        },
    )
