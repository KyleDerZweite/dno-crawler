"""
Crawl and job-related endpoints for DNO management.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import User as AuthUser
from app.core.auth import get_current_user
from app.core.models import APIResponse
from app.core.rate_limiter import get_client_ip
from app.db import CrawlJobModel, DNOModel, get_db

from .schemas import TriggerCrawlRequest

router = APIRouter()


@router.post("/{dno_id}/crawl")
async def trigger_crawl(
    dno_id: str,
    request: TriggerCrawlRequest,
    http_request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> APIResponse:
    """
    Trigger a job for a specific DNO.

    Job types:
    - full: Full pipeline (crawl steps 0-3, then extract steps 4-6)
    - crawl: Crawl only (discover + download, steps 0-3)
    - extract: Extract only from existing file (steps 4-6)

    Creates a new job that will be picked up by the appropriate worker.
    Any authenticated user (member or admin) can trigger this.
    Accepts either numeric ID or slug.
    """
    import structlog
    from arq import create_pool
    from arq.connections import RedisSettings

    from app.core.config import settings

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

    job_type = request.job_type.value

    # For extract-only jobs, verify a file exists
    if job_type == "extract":
        downloads_dir = Path(settings.downloads_path) / dno.slug
        file_pattern = f"{dno.slug}-{request.data_type.value}-{request.year}.*"
        existing_files = list(downloads_dir.glob(file_pattern)) if downloads_dir.exists() else []

        if not existing_files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No downloaded file found for {dno.name} {request.data_type.value} {request.year}. "
                f"Use 'full' or 'crawl' job type to download first.",
            )
        # Use the first matching file
        file_path = str(existing_files[0])
    else:
        file_path = None

    # For crawl and full jobs, check DNO lock status
    if job_type in ("full", "crawl"):
        dno_status = getattr(dno, "status", "uncrawled")
        if dno_status == "crawling":
            locked_at = getattr(dno, "crawl_locked_at", None)
            now = datetime.now(UTC)
            threshold = now - timedelta(hours=1)
            if locked_at:
                if locked_at.tzinfo is None:
                    locked_at = locked_at.replace(tzinfo=UTC)
                if locked_at < threshold:
                    logger.warning("Force-releasing stuck crawl", dno_id=dno_id)
                else:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"A crawl is already in progress for {dno.name}",
                    )
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
            detail="A job for this DNO, year, and data type is already in progress",
        )

    # Update DNO status for crawl/full jobs
    if job_type in ("full", "crawl"):
        dno.status = "crawling"
        dno.crawl_locked_at = datetime.now(UTC)

    # Build job context
    initiator_ip = get_client_ip(http_request)
    job_context = {"initiator_ip": initiator_ip}

    # For extract jobs, add file path to context
    if job_type == "extract" and file_path:
        job_context["downloaded_file"] = file_path
        job_context["file_to_process"] = file_path
        job_context["dno_slug"] = dno.slug
        job_context["dno_name"] = dno.name
        job_context["dno_website"] = dno.website
        job_context["strategy"] = "use_cache"  # Indicate we're using existing file

    # Create job in database
    job = CrawlJobModel(
        dno_id=dno.id,
        year=request.year,
        data_type=request.data_type.value,
        job_type=job_type,
        priority=request.priority,
        current_step=f"Triggered by {current_user.email}",
        triggered_by=current_user.email,
        context=job_context,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Determine which queue and function to use
    # "full" and "crawl" both use process_crawl on crawl queue
    # process_crawl handles steps 0-3, then chains to extract job automatically
    if job_type in ("full", "crawl"):
        queue_name = "crawl"
        job_function = "process_crawl"
    else:  # extract
        queue_name = "extract"
        job_function = "process_extract"

    # Enqueue job to appropriate worker queue
    try:
        redis_pool = await create_pool(RedisSettings.from_dsn(str(settings.redis_url)))
        await redis_pool.enqueue_job(
            job_function,
            job.id,
            _job_id=f"{job_type}_{job.id}",
            _queue_name=queue_name,
        )
        await redis_pool.close()

        logger.info("Job enqueued", job_id=job.id, job_type=job_type, queue=queue_name)
    except Exception as e:
        logger.error("Failed to enqueue job to worker", job_id=job.id, error=str(e))

    return APIResponse(
        success=True,
        message=f"{job_type.capitalize()} job created for {dno.name} ({request.year})",
        data={
            "job_id": str(job.id),
            "dno_id": str(dno.id),
            "dno_name": dno.name,
            "dno_status": dno.status,
            "year": request.year,
            "data_type": request.data_type.value,
            "job_type": job_type,
            "status": job.status,
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
