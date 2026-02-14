"""
Jobs API - Dedicated endpoint for job management.

Accessible to all authenticated users (not admin-only).
Provides a unified interface for viewing and managing crawl jobs.
"""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import User as AuthUser
from app.core.auth import get_current_user
from app.core.models import APIResponse
from app.db import CrawlJobModel, DNOModel, get_db

logger = structlog.get_logger()
router = APIRouter()


@router.get("/")
async def list_jobs(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
) -> APIResponse:
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
    pending_count = (
        await db.scalar(
            select(func.count(CrawlJobModel.id)).where(CrawlJobModel.status == "pending")
        )
        or 0
    )

    # Order by created_at desc, paginate
    query = query.order_by(CrawlJobModel.created_at.desc())
    query = query.offset((page - 1) * limit).limit(limit)

    result = await db.execute(query)
    jobs = result.scalars().all()

    # Fetch DNO names for display
    dno_ids = list({job.dno_id for job in jobs})
    if dno_ids:
        dno_query = select(DNOModel).where(DNOModel.id.in_(dno_ids))
        dno_result = await db.execute(dno_query)
        dnos = {dno.id: dno for dno in dno_result.scalars().all()}
    else:
        dnos = {}

    # Calculate queue position for pending jobs (separate for crawl and extract queues)
    pending_jobs_query = (
        select(CrawlJobModel.id, CrawlJobModel.job_type)
        .where(CrawlJobModel.status == "pending")
        .order_by(CrawlJobModel.created_at.asc())
    )
    pending_result = await db.execute(pending_jobs_query)
    pending_order = {}
    crawl_position = 0
    extract_position = 0
    for job_id, job_type in pending_result.fetchall():
        if job_type in ("crawl", "full"):
            crawl_position += 1
            pending_order[job_id] = crawl_position
        else:  # extract
            extract_position += 1
            pending_order[job_id] = extract_position

    return APIResponse(
        success=True,
        data={
            "jobs": [
                {
                    "job_id": str(job.id),
                    "dno_id": str(job.dno_id),
                    "dno_name": dnos.get(job.dno_id).name if dnos.get(job.dno_id) else None,
                    "year": job.year,
                    "data_type": job.data_type,
                    "job_type": getattr(job, "job_type", "full"),
                    "status": job.status,
                    "progress": job.progress,
                    "current_step": job.current_step,
                    "error_message": job.error_message,
                    "triggered_by": job.triggered_by,
                    "queue_position": pending_order.get(job.id)
                    if job.status == "pending"
                    else None,
                    "parent_job_id": str(job.parent_job_id)
                    if getattr(job, "parent_job_id", None)
                    else None,
                    "child_job_id": str(job.child_job_id)
                    if getattr(job, "child_job_id", None)
                    else None,
                    "started_at": job.started_at.isoformat() if job.started_at else None,
                    "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                    "created_at": job.created_at.isoformat() if job.created_at else None,
                }
                for job in jobs
            ],
            "queue_length": pending_count,
        },
        meta={
            "total": total,
            "page": page,
            "per_page": limit,
            "total_pages": (total + limit - 1) // limit if total > 0 else 0,
        },
    )


@router.get("/{job_id}")
async def get_job(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> APIResponse:
    """Get detailed information about a specific job including steps."""
    query = (
        select(CrawlJobModel)
        .where(CrawlJobModel.id == job_id)
        .options(selectinload(CrawlJobModel.steps))
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

    # Get linked jobs info
    parent_job_info = None
    child_job_info = None

    if getattr(job, "parent_job_id", None):
        parent = await db.get(CrawlJobModel, job.parent_job_id)
        if parent:
            parent_job_info = {
                "id": str(parent.id),
                "job_type": getattr(parent, "job_type", "full"),
                "status": parent.status,
            }

    if getattr(job, "child_job_id", None):
        child = await db.get(CrawlJobModel, job.child_job_id)
        if child:
            child_job_info = {
                "id": str(child.id),
                "job_type": getattr(child, "job_type", "full"),
                "status": child.status,
            }

    return APIResponse(
        success=True,
        data={
            "id": str(job.id),
            "dno_id": str(job.dno_id),
            "dno_name": dno.name if dno else None,
            "dno_slug": dno.slug if dno else None,
            "year": job.year,
            "data_type": job.data_type,
            "job_type": getattr(job, "job_type", "full"),
            "status": job.status,
            "progress": job.progress,
            "current_step": job.current_step,
            "error_message": job.error_message,
            "triggered_by": job.triggered_by,
            "priority": job.priority,
            "parent_job": parent_job_info,
            "child_job": child_job_info,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "extraction_log": (job.context or {}).get("extraction_log"),
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
async def delete_job(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> APIResponse:
    """Delete a job permanently.

    Permission: Admins can delete any job, creators can delete their own.
    """
    query = select(CrawlJobModel).where(CrawlJobModel.id == job_id)
    result = await db.execute(query)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    # Permission check: admin OR creator
    is_creator = job.triggered_by == current_user.email
    if not current_user.is_admin and not is_creator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete jobs you created",
        )

    await db.delete(job)
    await db.commit()

    logger.info("Job deleted", job_id=job_id, user=current_user.email)

    return APIResponse(
        success=True,
        message="Job deleted",
        data={"job_id": str(job_id)},
    )
