"""
Jobs API - Dedicated endpoint for job management.

Accessible to all authenticated users (not admin-only).
Provides a unified interface for viewing and managing crawl jobs.
"""

from typing import Annotated, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user, User as AuthUser
from app.core.models import APIResponse
from app.db import CrawlJobModel, DNOModel, get_db

logger = structlog.get_logger()
router = APIRouter()


@router.get("/")
async def list_jobs(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
) -> dict:
    """
    List all crawl jobs with optional filtering.
    
    Returns jobs with DNO names and queue position for pending jobs.
    Accessible to any authenticated user.
    """
    query = select(CrawlJobModel)
    
    if status_filter:
        query = query.where(CrawlJobModel.status == status_filter)
    
    # Get total count
    count_query = select(func.count(CrawlJobModel.id))
    if status_filter:
        count_query = count_query.where(CrawlJobModel.status == status_filter)
    total = await db.scalar(count_query) or 0
    
    # Get pending count for queue length
    pending_count = await db.scalar(
        select(func.count(CrawlJobModel.id)).where(CrawlJobModel.status == "pending")
    ) or 0
    
    # Order by created_at desc, paginate
    query = query.order_by(CrawlJobModel.created_at.desc())
    query = query.offset((page - 1) * limit).limit(limit)
    
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    # Fetch DNO names for display
    dno_ids = list(set(job.dno_id for job in jobs))
    if dno_ids:
        dno_query = select(DNOModel).where(DNOModel.id.in_(dno_ids))
        dno_result = await db.execute(dno_query)
        dnos = {dno.id: dno for dno in dno_result.scalars().all()}
    else:
        dnos = {}
    
    # Calculate queue position for pending jobs
    pending_jobs_query = (
        select(CrawlJobModel.id)
        .where(CrawlJobModel.status == "pending")
        .order_by(CrawlJobModel.created_at.asc())
    )
    pending_result = await db.execute(pending_jobs_query)
    pending_order = {job_id: idx + 1 for idx, job_id in enumerate(pending_result.scalars().all())}
    
    return {
        "jobs": [
            {
                "job_id": str(job.id),
                "dno_id": str(job.dno_id),
                "dno_name": dnos.get(job.dno_id).name if dnos.get(job.dno_id) else None,
                "year": job.year,
                "data_type": job.data_type,
                "status": job.status,
                "progress": job.progress,
                "current_step": job.current_step,
                "error_message": job.error_message,
                "queue_position": pending_order.get(job.id) if job.status == "pending" else None,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "created_at": job.created_at.isoformat() if job.created_at else None,
            }
            for job in jobs
        ],
        "queue_length": pending_count,
        "meta": {
            "total": total,
            "page": page,
            "per_page": limit,
            "total_pages": (total + limit - 1) // limit if total > 0 else 0,
        },
    }


@router.get("/{job_id}")
async def get_job(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> APIResponse:
    """Get detailed information about a specific job including steps."""
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
    dno = await db.get(DNOModel, job.dno_id)
    
    return APIResponse(
        success=True,
        data={
            "id": str(job.id),
            "dno_id": str(job.dno_id),
            "dno_name": dno.name if dno else None,
            "dno_slug": dno.slug if dno else None,
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


@router.delete("/{job_id}")
async def cancel_job(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> APIResponse:
    """Cancel a pending or running job."""
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
    
    if job.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job is already cancelled",
        )
    
    job.status = "cancelled"
    job.error_message = f"Cancelled by {current_user.email}"
    await db.commit()
    
    logger.info("Job cancelled", job_id=job_id, user=current_user.email)
    
    return APIResponse(
        success=True,
        message="Job cancelled",
        data={"job_id": str(job_id)},
    )


@router.post("/{job_id}/rerun")
async def rerun_job(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> APIResponse:
    """Rerun a failed, completed, or cancelled job."""
    from arq import create_pool
    from arq.connections import RedisSettings
    from app.core.config import settings
    
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
    new_job = CrawlJobModel(
        user_id=None,
        dno_id=job.dno_id,
        year=job.year,
        data_type=job.data_type,
        priority=job.priority,
        current_step=f"Rerun of job {job_id} by {current_user.email}",
    )
    db.add(new_job)
    await db.commit()
    await db.refresh(new_job)
    
    # Enqueue to arq worker
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
        logger.info("Rerun job enqueued", job_id=new_job.id, original_id=job_id)
    except Exception as e:
        logger.error("Failed to enqueue rerun job", job_id=new_job.id, error=str(e))
    
    return APIResponse(
        success=True,
        message="Job rerun created",
        data={
            "job_id": str(new_job.id),
            "original_job_id": str(job_id),
            "status": new_job.status,
        },
    )
