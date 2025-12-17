"""
DNO management routes (authenticated).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, User as AuthUser
from app.core.models import APIResponse, CrawlJob, CrawlJobCreate, DataType
from app.db import CrawlJobModel, DNOModel, get_db

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


@router.post("/")
async def create_dno(
    request: CreateDNORequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> APIResponse:
    """
    Create a new DNO.
    
    If slug is not provided, it will be auto-generated from the name.
    """
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
    
    # Create DNO
    dno = DNOModel(
        name=request.name,
        slug=slug,
        official_name=request.official_name,
        description=request.description,
        region=request.region,
        website=request.website,
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
            "description": dno.description,
            "region": dno.region,
            "website": dno.website,
            "created_at": dno.created_at.isoformat() if dno.created_at else None,
        },
    )


@router.get("/")
async def list_dnos_detailed(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    include_stats: bool = Query(False),
) -> APIResponse:
    """
    List all DNOs with detailed information.
    
    Status is computed dynamically from active jobs:
    - running: at least one running job
    - pending: at least one pending job (none running)
    - crawled: has data points and no active jobs
    - uncrawled: no data points and no active jobs
    """
    query = select(DNOModel).order_by(DNOModel.name)
    result = await db.execute(query)
    dnos = result.scalars().all()
    
    data = []
    for dno in dnos:
        # Get total data points count (Netzentgelte + HLZF)
        netz_count_result = await db.execute(
            text("SELECT COUNT(*) FROM netzentgelte WHERE dno_id = :dno_id"),
            {"dno_id": dno.id}
        )
        netzentgelte_count = netz_count_result.scalar() or 0
        
        hlzf_count_result = await db.execute(
            text("SELECT COUNT(*) FROM hlzf WHERE dno_id = :dno_id"),
            {"dno_id": dno.id}
        )
        hlzf_count = hlzf_count_result.scalar() or 0
        
        data_points_count = netzentgelte_count + hlzf_count
        
        # Compute live status from jobs
        running_count_result = await db.execute(
            text("SELECT COUNT(*) FROM crawl_jobs WHERE dno_id = :dno_id AND status = 'running'"),
            {"dno_id": dno.id}
        )
        running_count = running_count_result.scalar() or 0
        
        pending_count_result = await db.execute(
            text("SELECT COUNT(*) FROM crawl_jobs WHERE dno_id = :dno_id AND status = 'pending'"),
            {"dno_id": dno.id}
        )
        pending_count = pending_count_result.scalar() or 0
        
        # Determine status
        if running_count > 0:
            live_status = "running"
        elif pending_count > 0:
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
            "created_at": dno.created_at.isoformat() if dno.created_at else None,
            "updated_at": dno.updated_at.isoformat() if dno.updated_at else None,
        }
        
        if include_stats:
            dno_data["stats"] = {
                "netzentgelte_count": netzentgelte_count,
                "hlzf_count": hlzf_count,
                "years_available": [],
                "last_crawl": None,
            }
        
        data.append(dno_data)
    
    return APIResponse(success=True, data=data)


@router.get("/{dno_id}")
async def get_dno_details(
    dno_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> APIResponse:
    """Get detailed information about a specific DNO by ID or slug."""
    # Try to find by numeric ID first, then by slug
    dno = None
    if dno_id.isdigit():
        query = select(DNOModel).where(DNOModel.id == int(dno_id))
        result = await db.execute(query)
        dno = result.scalar_one_or_none()
    
    if not dno:
        query = select(DNOModel).where(DNOModel.slug == dno_id.lower())
        result = await db.execute(query)
        dno = result.scalar_one_or_none()
    
    if not dno:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DNO not found",
        )
    
    return APIResponse(
        success=True,
        data={
            "id": str(dno.id),
            "slug": dno.slug,
            "name": dno.name,
            "official_name": dno.official_name,
            "vnb_id": dno.vnb_id,
            "status": getattr(dno, 'status', 'uncrawled'),
            "description": dno.description,
            "region": dno.region,
            "website": dno.website,
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
    
    # Create crawl job in database
    job = CrawlJobModel(
        user_id=None,
        dno_id=dno.id,
        year=request.year,
        data_type=request.data_type.value,
        priority=request.priority,
        current_step=f"Triggered by {current_user.email}",
        triggered_by=current_user.email,
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
        SELECT id, voltage_level, year, leistung, arbeit, leistung_unter_2500h, arbeit_unter_2500h, verification_status
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
        })
    
    # Query HLZF data
    hlzf_query = text("""
        SELECT id, voltage_level, year, winter, fruehling, sommer, herbst, verification_status
        FROM hlzf
        WHERE dno_id = :dno_id
        ORDER BY year DESC, voltage_level
    """)
    result = await db.execute(hlzf_query, {"dno_id": dno_id})
    hlzf_rows = result.fetchall()
    
    hlzf = []
    for row in hlzf_rows:
        hlzf.append({
            "id": row[0],
            "voltage_level": row[1],
            "year": row[2],
            "winter": row[3],
            "fruehling": row[4],
            "sommer": row[5],
            "herbst": row[6],
            "verification_status": row[7],
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
    """List available PDF files for a DNO."""
    import os
    from pathlib import Path
    
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
    
    # Check old path (data/downloads/)
    old_path = Path(storage_path) / "downloads"
    if old_path.exists():
        for f in old_path.glob(f"{dno.slug}-*.pdf"):
            files.append({
                "name": f.name,
                "size": f.stat().st_size,
                "path": f"/files/downloads/{f.name}",
            })
    
    # Check new path (data/downloads/<slug>/)
    new_path = Path(storage_path) / "downloads" / dno.slug
    if new_path.exists():
        for f in new_path.glob("*.pdf"):
            files.append({
                "name": f.name,
                "size": f.stat().st_size,
                "path": f"/files/downloads/{dno.slug}/{f.name}",
            })
    
    return APIResponse(
        success=True,
        data=files,
    )
