"""
CRUD operations for DNO management.
"""

import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select, text, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user, User as AuthUser
from app.core.models import APIResponse
from app.db import CrawlJobModel, DNOModel, get_db

from .schemas import CreateDNORequest, UpdateDNORequest
from .utils import slugify


router = APIRouter()


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


@router.get("/stats")
async def get_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> APIResponse:
    """
    Get dashboard statistics for authenticated users.
    
    Returns counts for DNOs, data points, and active jobs.
    """
    from app.db.models import NetzentgelteModel, HLZFModel
    
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
