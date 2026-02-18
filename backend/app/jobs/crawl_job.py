"""
Crawl Job - Steps 0-3: Gather Context, Discover, Download, Classify.

This job handles the I/O-bound crawling portion:
1. Step 00: Gather Context - Load DNO info, pre-flight checks
2. Step 01: Discover - Data-type agnostic URL discovery
3. Step 02: Download - Bulk download candidates
4. Step 03: Classify - Post-download classification via regex extractors

After successful completion, automatically enqueues extract job(s)
for each classified data type.

Supports crawl deepening: if classify finds nothing on first pass,
re-runs steps 1-3 with increased depth/pages (max one deepening pass).

Designed to run on a single dedicated worker to ensure polite crawling
(no parallel requests to the same domain).
"""

import contextlib
from datetime import UTC, datetime

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
        from app.jobs.steps.step_03_classify import ClassifyStep

        CRAWL_STEPS = [
            GatherContextStep(),
            DiscoverStep(),
            DownloadStep(),
            ClassifyStep(),
        ]
    return CRAWL_STEPS


async def process_crawl(
    ctx: dict,
    job_id: int,
) -> dict:
    """
    Execute crawl job (steps 0-3: gather, discover, download, classify).

    After successful completion, enqueues extract job(s) for each
    classified data type. Supports one deepening pass if classify
    finds nothing on the first attempt.

    Args:
        ctx: ARQ context
        job_id: ID of the CrawlJobModel to process

    Returns:
        Result dict with status and any spawned extract job IDs
    """
    log = logger.bind(job_id=job_id, job_type="crawl")
    log.info("Crawl job received, starting execution")

    async with get_db_session() as db:
        result = await db.execute(select(CrawlJobModel).where(CrawlJobModel.id == job_id))
        job = result.scalar_one_or_none()

        if not job:
            log.error("Job not found", job_id=job_id)
            return {"status": "error", "message": "Job not found"}

        # Mark job as running
        job.status = "running"
        job.started_at = datetime.now(UTC)
        await db.commit()

        steps = get_crawl_steps()
        total_steps = len(steps)

        try:
            # Run all steps (gather, discover, download, classify)
            for i, step in enumerate(steps, 1):
                await step.execute(db, job, i, total_steps)

            # Check if classify requested a deeper crawl
            job_ctx = job.context or {}
            if job_ctx.get("deepen_crawl") and job_ctx.get("crawl_pass", 1) == 1:
                log.info("Deepening crawl: re-running discover/download/classify")

                # Update context for deeper pass
                job_ctx["crawl_pass"] = 2
                job_ctx["max_depth"] = 5
                job_ctx["max_pages"] = 150
                job_ctx["deepen_crawl"] = False
                job.context = job_ctx
                await db.commit()

                # Re-run steps 1-3 (discover, download, classify) with deeper settings
                # Steps are 0-indexed in the list: [0]=gather, [1]=discover, [2]=download, [3]=classify
                deeper_steps = steps[1:]  # discover, download, classify
                for i, step in enumerate(deeper_steps, total_steps + 1):
                    await step.execute(db, job, i, total_steps + len(deeper_steps))

            # Crawl steps completed successfully
            job.status = "completed"
            job.progress = 100
            job.current_step = "Crawl Completed - Queuing Extract"
            job.completed_at = datetime.now(UTC)
            await db.commit()

            # Enqueue extract job(s) for each classified data type
            extract_job_ids = []
            if not job.context.get("skip_extract"):
                extract_job_ids = await _enqueue_extract_jobs(db, job, log)

            if extract_job_ids:
                # Store first child ID for backwards compat
                job.child_job_id = extract_job_ids[0]
                job.current_step = f"Completed - {len(extract_job_ids)} extract job(s) queued"
                job.context = {
                    **(job.context or {}),
                    "child_job_ids": extract_job_ids,
                }
                await db.commit()

                log.info(
                    "Crawl job completed, extract jobs enqueued",
                    extract_job_ids=extract_job_ids,
                )
                return {
                    "status": "completed",
                    "message": f"Crawl completed, {len(extract_job_ids)} extract job(s) queued",
                    "extract_job_ids": extract_job_ids,
                }
            else:
                classified = (job.context or {}).get("classified_files", {})
                if not classified:
                    job.current_step = "Completed - No extractable data found"
                    await db.commit()
                    log.warning("Crawl completed but no data classified")
                else:
                    log.warning("Crawl completed but no extract jobs created")
                return {
                    "status": "completed",
                    "message": "Crawl completed (no extract jobs spawned)",
                }

        except Exception as e:
            log.error("Crawl job failed", error=str(e))
            # BaseStep sets job.status/completed_at on step failures,
            # but ensure completed_at is set even for non-step errors
            if not job.completed_at:
                job.completed_at = datetime.now(UTC)
                with contextlib.suppress(Exception):
                    await db.commit()
            return {"status": "failed", "message": str(e)}


async def _enqueue_extract_jobs(db, parent_job: CrawlJobModel, log) -> list[int]:
    """
    Create and enqueue extract jobs for each classified data type.

    Returns list of new extract job IDs.
    """
    from arq import create_pool
    from arq.connections import RedisSettings

    from app.core.config import settings

    job_ctx = parent_job.context or {}
    classified_files = job_ctx.get("classified_files", {})

    if not classified_files:
        log.info("No classified files, skipping extract jobs")
        return []

    extract_job_ids = []
    redis_pool = None

    try:
        redis_pool = await create_pool(RedisSettings.from_dsn(str(settings.redis_url)))

        for data_type, file_info in classified_files.items():
            # Build extract job context with the classified file info
            extract_ctx = {
                "dno_id": job_ctx.get("dno_id"),
                "dno_slug": job_ctx.get("dno_slug"),
                "dno_name": job_ctx.get("dno_name"),
                "dno_website": job_ctx.get("dno_website"),
                "initiator_ip": job_ctx.get("initiator_ip"),
                "downloaded_file": file_info["path"],
                "file_to_process": file_info["path"],
                "file_format": file_info["format"],
                "strategy": "classified",
                "source_url": file_info.get("source_url"),
                "found_url": file_info.get("source_url"),  # Compat with finalize step
            }

            extract_job = CrawlJobModel(
                dno_id=parent_job.dno_id,
                year=parent_job.year,
                data_type=data_type,  # Specific type, never "all"
                job_type="extract",
                parent_job_id=parent_job.id,
                triggered_by=parent_job.triggered_by,
                priority=parent_job.priority,
                current_step="Queued for extraction",
                context=extract_ctx,
            )
            db.add(extract_job)
            await db.commit()
            await db.refresh(extract_job)

            await redis_pool.enqueue_job(
                "process_extract",
                extract_job.id,
                _job_id=f"extract_{extract_job.id}",
                _queue_name="extract",
            )

            extract_job_ids.append(extract_job.id)
            log.info(
                "Extract job enqueued",
                extract_job_id=extract_job.id,
                data_type=data_type,
                file=file_info["path"],
            )

    except Exception as e:
        log.error("Failed to enqueue extract jobs", error=str(e))
    finally:
        if redis_pool:
            await redis_pool.close()

    return extract_job_ids
