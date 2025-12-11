"""
Admin routes - requires admin role.

User management has been moved to Zitadel.
This module only contains job management and data normalization routes.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_admin, User as AuthUser
from app.core.models import APIResponse
from app.core.config import settings
from app.db import (
    CrawlJobModel,
    DNOModel,
    NetzentgelteModel,
    get_db,
)
from arq import create_pool
from arq.connections import RedisSettings
import structlog

logger = structlog.get_logger()

router = APIRouter()


@router.get("/dashboard")
async def admin_dashboard(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Get admin dashboard statistics."""
    # Count DNOs
    dno_count = await db.scalar(select(func.count(DNOModel.id)))
    
    # Count pending jobs
    pending_jobs = await db.scalar(
        select(func.count(CrawlJobModel.id)).where(CrawlJobModel.status == "pending")
    )
    running_jobs = await db.scalar(
        select(func.count(CrawlJobModel.id)).where(CrawlJobModel.status == "running")
    )
    
    return APIResponse(
        success=True,
        data={
            "dnos": {
                "total": dno_count or 0,
            },
            "jobs": {
                "pending": pending_jobs or 0,
                "running": running_jobs or 0,
            },
        },
    )


@router.get("/jobs")
async def list_all_jobs(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AuthUser, Depends(require_admin)],
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> APIResponse:
    """List all crawl jobs."""
    query = select(CrawlJobModel)
    
    if status_filter:
        query = query.where(CrawlJobModel.status == status_filter)
    
    # Get total count
    count_query = select(func.count(CrawlJobModel.id))
    if status_filter:
        count_query = count_query.where(CrawlJobModel.status == status_filter)
    total = await db.scalar(count_query) or 0
    
    query = query.order_by(CrawlJobModel.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    # Fetch DNO names for display
    dno_ids = list(set(job.dno_id for job in jobs))
    dno_query = select(DNOModel).where(DNOModel.id.in_(dno_ids))
    dno_result = await db.execute(dno_query)
    dnos = {dno.id: dno for dno in dno_result.scalars().all()}
    
    return APIResponse(
        success=True,
        data=[
            {
                "id": str(job.id),
                "dno_id": str(job.dno_id),
                "dno_name": dnos.get(job.dno_id).name if dnos.get(job.dno_id) else None,
                "user_id": str(job.user_id) if job.user_id else None,
                "year": job.year,
                "data_type": job.data_type,
                "status": job.status,
                "progress": job.progress,
                "current_step": job.current_step,
                "error_message": job.error_message,
                "priority": job.priority,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "created_at": job.created_at.isoformat() if job.created_at else None,
            }
            for job in jobs
        ],
        meta={
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page,
        },
    )


@router.get("/jobs/{job_id}")
async def get_job_details(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Get detailed information about a specific job including steps."""
    from sqlalchemy.orm import selectinload
    
    query = select(CrawlJobModel).where(CrawlJobModel.id == job_id).options(
        selectinload(CrawlJobModel.steps)
    )
    result = await db.execute(query)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    
    # Get DNO info
    dno_query = select(DNOModel).where(DNOModel.id == job.dno_id)
    dno_result = await db.execute(dno_query)
    dno = dno_result.scalar_one_or_none()
    
    return APIResponse(
        success=True,
        data={
            "id": str(job.id),
            "dno_id": str(job.dno_id),
            "dno_name": dno.name if dno else None,
            "dno_slug": dno.slug if dno else None,
            "user_id": str(job.user_id) if job.user_id else None,
            "year": job.year,
            "data_type": job.data_type,
            "status": job.status,
            "progress": job.progress,
            "current_step": job.current_step,
            "error_message": job.error_message,
            "priority": job.priority,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
            "steps": [
                {
                    "id": str(step.id),
                    "step_name": step.step_name,
                    "status": step.status,
                    "started_at": step.started_at.isoformat() if step.started_at else None,
                    "completed_at": step.completed_at.isoformat() if step.completed_at else None,
                    "duration_seconds": step.duration_seconds,
                    "details": step.details,
                }
                for step in sorted(job.steps, key=lambda s: s.created_at or s.id)
            ],
        },
    )


class CreateJobRequest(BaseModel):
    """Request to create a standalone job."""
    dno_id: int
    year: int
    data_type: str = "all"
    priority: int = 5
    job_type: str = "crawl"  # crawl, rescan_pdf, rerun_extraction
    target_file_id: int | None = None  # For rescan_pdf jobs


@router.post("/jobs")
async def create_standalone_job(
    request: CreateJobRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Create a standalone job (admin only)."""
    # Verify DNO exists
    dno_query = select(DNOModel).where(DNOModel.id == request.dno_id)
    dno_result = await db.execute(dno_query)
    dno = dno_result.scalar_one_or_none()
    
    if not dno:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DNO not found",
        )
    
    # Create job based on type
    # Note: user_id is None since Zitadel admin isn't a local user
    job = CrawlJobModel(
        user_id=None,
        dno_id=request.dno_id,
        year=request.year,
        data_type=request.data_type,
        priority=request.priority,
        current_step=f"Created by {admin.email} ({request.job_type})",
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
            "crawl_dno_job",
            job.id,
            _job_id=f"crawl_{job.id}",
        )
        await redis_pool.aclose()
        logger.info("Job enqueued to worker", job_id=job.id)
    except Exception as e:
        logger.error("Failed to enqueue job to worker", job_id=job.id, error=str(e))
    
    return APIResponse(
        success=True,
        message=f"Job created for {dno.name} ({request.year})",
        data={
            "job_id": str(job.id),
            "dno_id": str(request.dno_id),
            "dno_name": dno.name,
            "year": request.year,
            "data_type": request.data_type,
            "job_type": request.job_type,
            "status": job.status,
        },
    )


@router.post("/jobs/{job_id}/rerun")
async def rerun_job(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Rerun a failed or completed job."""
    query = select(CrawlJobModel).where(CrawlJobModel.id == job_id)
    result = await db.execute(query)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    
    if job.status in ["pending", "running"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot rerun a job that is still pending or running",
        )
    
    # Create a new job based on the old one
    # Note: user_id is None since Zitadel admin isn't a local user
    new_job = CrawlJobModel(
        user_id=None,
        dno_id=job.dno_id,
        year=job.year,
        data_type=job.data_type,
        priority=job.priority,
        current_step=f"Rerun of job {job_id} by {admin.email}",
    )
    db.add(new_job)
    await db.commit()
    await db.refresh(new_job)
    
    # Enqueue job to arq worker queue
    try:
        redis_pool = await create_pool(
            RedisSettings.from_dsn(str(settings.redis_url))
        )
        await redis_pool.enqueue_job(
            "crawl_dno_job",
            new_job.id,
            _job_id=f"crawl_{new_job.id}",
        )
        await redis_pool.aclose()
        logger.info("Rerun job enqueued to worker", job_id=new_job.id, original_id=job_id)
    except Exception as e:
        logger.error("Failed to enqueue rerun job to worker", job_id=new_job.id, error=str(e))
    
    return APIResponse(
        success=True,
        message=f"Job rerun created",
        data={
            "job_id": str(new_job.id),
            "original_job_id": str(job_id),
            "status": new_job.status,
        },
    )


@router.delete("/jobs/{job_id}")
async def cancel_job(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Cancel a pending job or mark a running job for cancellation."""
    query = select(CrawlJobModel).where(CrawlJobModel.id == job_id)
    result = await db.execute(query)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    
    if job.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel a completed job",
        )
    
    job.status = "cancelled"
    job.error_message = f"Cancelled by admin {admin.email}"
    await db.commit()
    
    return APIResponse(
        success=True,
        message="Job cancelled",
    )


@router.post("/normalize-voltage-levels")
async def normalize_voltage_levels(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Normalize voltage level names across Netzentgelte and HLZF tables."""
    from app.db import HLZFModel
    
    # Standard voltage level mapping - same as in crawl_job.py
    VOLTAGE_LEVEL_MAPPING = {
        # Hochspannung variants
        "hochspannung": "Hochspannung",
        "hochspannungsnetz": "Hochspannung",
        "hs": "Hochspannung",
        # Mittelspannung variants
        "mittelspannung": "Mittelspannung",
        "mittelspannungsnetz": "Mittelspannung",
        "ms": "Mittelspannung",
        # Niederspannung variants
        "niederspannung": "Niederspannung",
        "niederspannungsnetz": "Niederspannung",
        "ns": "Niederspannung",
        # Umspannung HS/MS variants
        "umspannung hoch-/mittelspannung": "Umspannung HS/MS",
        "umspannung hoch-mittelspannung": "Umspannung HS/MS",
        "umspannung hochspannung/mittelspannung": "Umspannung HS/MS",
        "hoch-/mittelspannung": "Umspannung HS/MS",
        "hs/ms": "Umspannung HS/MS",
        "umspannung zur mittelspannung": "Umspannung HS/MS",
        "umspg. zur mittelspannung": "Umspannung HS/MS",
        "umsp. zur ms": "Umspannung HS/MS",
        # Umspannung MS/NS variants
        "umspannung mittel-/niederspannung": "Umspannung MS/NS",
        "umspannung mittel-niederspannung": "Umspannung MS/NS",
        "umspannung mittelspannung/niederspannung": "Umspannung MS/NS",
        "mittel-/niederspannung": "Umspannung MS/NS",
        "ms/ns": "Umspannung MS/NS",
        "umspannung zur niederspannung": "Umspannung MS/NS",
        "umspg. zur niederspannung": "Umspannung MS/NS",
        "umsp. zur ns": "Umspannung MS/NS",
    }
    
    netzentgelte_updated = 0
    hlzf_updated = 0
    
    # Update Netzentgelte
    result = await db.execute(select(NetzentgelteModel))
    records = result.scalars().all()
    for record in records:
        if record.voltage_level:
            cleaned = " ".join(record.voltage_level.replace("\n", " ").split())
            normalized = VOLTAGE_LEVEL_MAPPING.get(cleaned.lower(), cleaned)
            if normalized != record.voltage_level:
                record.voltage_level = normalized
                netzentgelte_updated += 1
    
    # Update HLZF
    result = await db.execute(select(HLZFModel))
    records = result.scalars().all()
    for record in records:
        if record.voltage_level:
            cleaned = " ".join(record.voltage_level.replace("\n", " ").split())
            normalized = VOLTAGE_LEVEL_MAPPING.get(cleaned.lower(), cleaned)
            if normalized != record.voltage_level:
                record.voltage_level = normalized
                hlzf_updated += 1
    
    await db.commit()
    
    return APIResponse(
        success=True,
        message=f"Normalized {netzentgelte_updated} Netzentgelte and {hlzf_updated} HLZF records",
        data={"netzentgelte_updated": netzentgelte_updated, "hlzf_updated": hlzf_updated},
    )
