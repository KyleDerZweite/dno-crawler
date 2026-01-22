"""
Crawl Job - Steps 0-3: Gather Context, Discover, Download.

This job handles the I/O-bound crawling portion:
1. Step 00: Gather Context - Load DNO info, check cache
2. Step 01: Discover - Find data source via BFS crawl or patterns
3. Step 03: Download - Download file to local storage

After successful completion, automatically enqueues an extract job
to process the downloaded file.

Designed to run on a single dedicated worker to ensure polite crawling
(no parallel requests to the same domain).
"""

from datetime import datetime

import structlog
from sqlalchemy import select

from app.db import get_db_session
from app.db.models import CrawlJobModel

logger = structlog.get_logger()

# Steps for crawl job (steps 0-3)
CRAWL_STEPS = None  # Lazy loaded to avoid circular imports


def get_crawl_steps():
    """Lazy load crawl steps to avoid circular imports."""
    global CRAWL_STEPS
    if CRAWL_STEPS is None:
        from app.jobs.steps.step_00_gather_context import GatherContextStep
        from app.jobs.steps.step_01_discover import DiscoverStep
        from app.jobs.steps.step_02_download import DownloadStep

        CRAWL_STEPS = [
            GatherContextStep(),
            DiscoverStep(),
            DownloadStep(),
        ]
    return CRAWL_STEPS


async def process_crawl(
    ctx: dict,
    job_id: int,
) -> dict:
    """
    Execute crawl job (steps 0-3: gather, discover, download).

    After successful completion, enqueues an extract job to continue processing.

    Args:
        ctx: ARQ context
        job_id: ID of the CrawlJobModel to process

    Returns:
        Result dict with status and any spawned extract job ID
    """
    log = logger.bind(job_id=job_id, job_type="crawl")
    log.info("🚀 Crawl job received, starting execution")

    async with get_db_session() as db:
        result = await db.execute(
            select(CrawlJobModel).where(CrawlJobModel.id == job_id)
        )
        job = result.scalar_one_or_none()

        if not job:
            log.error("Job not found", job_id=job_id)
            return {"status": "error", "message": "Job not found"}

        # Mark job as running
        job.status = "running"
        job.started_at = datetime.utcnow()
        await db.commit()

        steps = get_crawl_steps()
        total_steps = len(steps)

        try:
            for i, step in enumerate(steps, 1):
                await step.execute(db, job, i, total_steps)

            # Crawl steps completed successfully
            job.status = "completed"
            job.progress = 100
            job.current_step = "Crawl Completed - Queuing Extract"
            job.completed_at = datetime.utcnow()
            await db.commit()

            # Now enqueue the extract job (unless skip_extract is set)
            extract_job_id = None
            if not job.context.get("skip_extract"):
                extract_job_id = await _enqueue_extract_job(db, job, log)

            if extract_job_id:
                # Update this job with the child reference
                job.child_job_id = extract_job_id
                job.current_step = f"Completed - Extract job #{extract_job_id} queued"
                await db.commit()

                log.info("✅ Crawl job completed, extract job enqueued",
                        extract_job_id=extract_job_id)
                return {
                    "status": "completed",
                    "message": "Crawl completed, extract job queued",
                    "extract_job_id": extract_job_id,
                }
            else:
                log.warning("Crawl completed but no extract job created")
                return {
                    "status": "completed",
                    "message": "Crawl completed (no extract needed or failed to queue)",
                }

        except Exception as e:
            log.error("❌ Crawl job failed", error=str(e))
            # Step base class handles job status update on failure
            return {"status": "failed", "message": str(e)}


async def _enqueue_extract_job(db, parent_job: CrawlJobModel, log) -> int | None:
    """
    Create and enqueue an extract job to continue processing.

    Returns the new extract job ID, or None if extraction isn't needed.
    """
    from arq import create_pool
    from arq.connections import RedisSettings

    from app.core.config import settings

    ctx = parent_job.context or {}

    # Check if we have a file to extract
    downloaded_file = ctx.get("downloaded_file") or ctx.get("file_to_process")
    if not downloaded_file:
        log.info("No file to extract, skipping extract job")
        return None

    # Create the extract job record
    extract_job = CrawlJobModel(
        dno_id=parent_job.dno_id,
        year=parent_job.year,
        data_type=parent_job.data_type,
        job_type="extract",
        parent_job_id=parent_job.id,
        triggered_by=parent_job.triggered_by,
        priority=parent_job.priority,
        current_step="Queued for extraction",
        # Copy context from crawl job so extract has all the info
        context=ctx,
    )
    db.add(extract_job)
    await db.commit()
    await db.refresh(extract_job)

    log.info("Created extract job", extract_job_id=extract_job.id)

    # Enqueue to the extract queue
    try:
        redis_pool = await create_pool(
            RedisSettings.from_dsn(str(settings.redis_url))
        )
        await redis_pool.enqueue_job(
            "process_extract",
            extract_job.id,
            _job_id=f"extract_{extract_job.id}",
            _queue_name="extract",  # Different queue for extract jobs
        )
        await redis_pool.close()

        log.info("Extract job enqueued to Redis", extract_job_id=extract_job.id)
        return extract_job.id

    except Exception as e:
        log.error("Failed to enqueue extract job",
                 extract_job_id=extract_job.id, error=str(e))
        # Mark the extract job as failed since we couldn't queue it
        extract_job.status = "failed"
        extract_job.error_message = f"Failed to enqueue: {e!s}"
        await db.commit()
        return None
