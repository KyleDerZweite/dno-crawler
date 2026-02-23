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
    - extract: Extract only from existing files (steps 4-6)

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

    # For extract-only jobs, scan for existing files and create child jobs
    if job_type == "extract":
        downloads_dir = Path(settings.downloads_path) / dno.slug
        file_pattern = f"{dno.slug}-*-{request.year}.*"
        existing_files = list(downloads_dir.glob(file_pattern)) if downloads_dir.exists() else []

        if not existing_files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No downloaded files found for {dno.name} {request.year}. "
                f"Use 'full' job type to download first.",
            )

        # Parse data_type from canonical filenames: {slug}-{data_type}-{year}.ext
        # Strip known slug prefix and year suffix to extract data_type in between
        slug_prefix = f"{dno.slug}-"
        year_suffix = f"-{request.year}"
        extract_files: dict[str, str] = {}  # data_type -> file_path
        for f in existing_files:
            stem = f.stem  # filename without extension
            if stem.startswith(slug_prefix) and stem.endswith(year_suffix):
                data_type = stem[len(slug_prefix) : -len(year_suffix)]
                if data_type in ("netzentgelte", "hlzf"):
                    extract_files[data_type] = str(f)

        if not extract_files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No recognizable data files found for {dno.name} {request.year}.",
            )

    # For full jobs, release stale DNO crawl locks (but don't block —
    # the per-job duplicate check below is year-aware and handles conflicts)
    if job_type == "full":
        dno_status = getattr(dno, "status", "uncrawled")
        if dno_status == "crawling":
            locked_at = getattr(dno, "crawl_locked_at", None)
            now = datetime.now(UTC)
            threshold = now - timedelta(hours=1)
            is_stale = not locked_at  # No timestamp means stuck
            if locked_at:
                if locked_at.tzinfo is None:
                    locked_at = locked_at.replace(tzinfo=UTC)
                is_stale = locked_at < threshold

            if is_stale:
                logger.warning("Force-releasing stuck crawl lock", dno_id=dno_id)
                dno.status = "failed"
                dno.crawl_locked_at = None
                await db.flush()

    # Check for existing pending/running job for the SAME year — recover stale ones inline
    check_type = "full" if job_type == "full" else "extract"
    existing_query = select(CrawlJobModel).where(
        CrawlJobModel.dno_id == dno.id,
        CrawlJobModel.year == request.year,
        CrawlJobModel.job_type == check_type,
        CrawlJobModel.status.in_(["pending", "running"]),
    )
    result = await db.execute(existing_query)
    existing_job = result.scalar_one_or_none()

    if existing_job:
        # Check if the blocking job is stale (older than 1 hour)
        job_age_ref = existing_job.started_at or existing_job.created_at
        if job_age_ref:
            if job_age_ref.tzinfo is None:
                job_age_ref = job_age_ref.replace(tzinfo=UTC)
            stale_threshold = datetime.now(UTC) - timedelta(hours=1)
            if job_age_ref < stale_threshold:
                logger.warning(
                    "Force-failing stale blocking job",
                    stale_job_id=existing_job.id,
                    status=existing_job.status,
                )
                existing_job.status = "failed"
                existing_job.error_message = "Timed out - recovered on re-trigger"
                existing_job.completed_at = datetime.now(UTC)
                await db.flush()
            else:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A job for this DNO and year is already in progress",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A job for this DNO and year is already in progress",
            )

    # Update DNO status for full jobs
    if job_type == "full":
        dno.status = "crawling"
        dno.crawl_locked_at = datetime.now(UTC)

    # Build job context
    initiator_ip = get_client_ip(http_request)
    job_context = {"initiator_ip": initiator_ip}

    # For extract jobs, create a coordinator parent + child extract jobs per data type
    if job_type == "extract":
        # Create coordinator parent job
        job = CrawlJobModel(
            dno_id=dno.id,
            year=request.year,
            data_type="all",
            job_type=job_type,
            priority=request.priority,
            status="completed",
            progress=100,
            current_step=f"Coordinator - {len(extract_files)} extract job(s) created",
            triggered_by=current_user.email,
            context=job_context,
            completed_at=datetime.now(UTC),
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        # Create and enqueue child extract jobs per found data type
        redis_pool = await create_pool(RedisSettings.from_dsn(str(settings.redis_url)))
        child_job_ids = []
        try:
            for data_type, fpath in extract_files.items():
                child_ctx = {
                    "initiator_ip": initiator_ip,
                    "downloaded_file": fpath,
                    "file_to_process": fpath,
                    "dno_slug": dno.slug,
                    "dno_name": dno.name,
                    "dno_website": dno.website,
                    "strategy": "use_cache",
                }
                child_job = CrawlJobModel(
                    dno_id=dno.id,
                    year=request.year,
                    data_type=data_type,
                    job_type="extract",
                    parent_job_id=job.id,
                    triggered_by=current_user.email,
                    priority=request.priority,
                    current_step="Queued for extraction",
                    context=child_ctx,
                )
                db.add(child_job)
                await db.commit()
                await db.refresh(child_job)

                await redis_pool.enqueue_job(
                    "process_extract",
                    child_job.id,
                    _job_id=f"extract_{child_job.id}",
                    _queue_name="extract",
                )
                child_job_ids.append(child_job.id)
                logger.info(
                    "Extract child job enqueued",
                    parent_job_id=job.id,
                    child_job_id=child_job.id,
                    data_type=data_type,
                )
        finally:
            await redis_pool.close()

        # Link first child for backwards compat
        if child_job_ids:
            job.child_job_id = child_job_ids[0]
            job.context = {**(job.context or {}), "child_job_ids": child_job_ids}
            await db.commit()

        return APIResponse(
            success=True,
            message=f"Extract jobs created for {dno.name} ({request.year})",
            data={
                "job_id": str(job.id),
                "dno_id": str(dno.id),
                "dno_name": dno.name,
                "dno_status": dno.status,
                "year": request.year,
                "data_type": "all",
                "job_type": job_type,
                "status": job.status,
                "child_job_ids": child_job_ids,
            },
        )

    # Full pipeline job
    job = CrawlJobModel(
        dno_id=dno.id,
        year=request.year,
        data_type="all",
        job_type=job_type,
        priority=request.priority,
        current_step=f"Triggered by {current_user.email}",
        triggered_by=current_user.email,
        context=job_context,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Enqueue to crawl worker
    try:
        redis_pool = await create_pool(RedisSettings.from_dsn(str(settings.redis_url)))
        await redis_pool.enqueue_job(
            "process_crawl",
            job.id,
            _job_id=f"full_{job.id}",
            _queue_name="crawl",
        )
        await redis_pool.close()

        logger.info("Job enqueued", job_id=job.id, job_type=job_type, queue="crawl")
    except Exception as e:
        logger.error("Failed to enqueue job to worker", job_id=job.id, error=str(e))

    return APIResponse(
        success=True,
        message=f"Full job created for {dno.name} ({request.year})",
        data={
            "job_id": str(job.id),
            "dno_id": str(dno.id),
            "dno_name": dno.name,
            "dno_status": dno.status,
            "year": request.year,
            "data_type": "all",
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
