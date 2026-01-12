"""
Extract Job - Steps 4-6: Extract, Validate, Finalize.

This job handles the CPU/API-bound extraction portion:
1. Step 04: Extract - Parse document with regex, then AI fallback
2. Step 05: Validate - Check data quality and plausibility
3. Step 06: Finalize - Save to database, update learning profiles

This job is typically created automatically by a completed crawl job,
but can also be triggered directly when a file already exists locally.

Can run on dedicated worker(s) - safe to parallelize since no external
crawling is performed.
"""

from datetime import datetime

import structlog
from sqlalchemy import select

from app.db import get_db_session
from app.db.models import CrawlJobModel

logger = structlog.get_logger()

# Steps for extract job (steps 4-6)
EXTRACT_STEPS = None  # Lazy loaded to avoid circular imports


def get_extract_steps():
    """Lazy load extract steps to avoid circular imports."""
    global EXTRACT_STEPS
    if EXTRACT_STEPS is None:
        from app.jobs.steps.step_04_extract import ExtractStep
        from app.jobs.steps.step_05_validate import ValidateStep
        from app.jobs.steps.step_06_finalize import FinalizeStep

        EXTRACT_STEPS = [
            ExtractStep(),
            ValidateStep(),
            FinalizeStep(),
        ]
    return EXTRACT_STEPS


async def process_extract(
    ctx: dict,
    job_id: int,
) -> dict:
    """
    Execute extract job (steps 4-6: extract, validate, finalize).

    Args:
        ctx: ARQ context
        job_id: ID of the CrawlJobModel to process

    Returns:
        Result dict with status
    """
    log = logger.bind(job_id=job_id, job_type="extract")
    log.info("🔬 Extract job received, starting execution")

    async with get_db_session() as db:
        result = await db.execute(
            select(CrawlJobModel).where(CrawlJobModel.id == job_id)
        )
        job = result.scalar_one_or_none()

        if not job:
            log.error("Job not found", job_id=job_id)
            return {"status": "error", "message": "Job not found"}

        # Verify this is an extract job or we have a file to process
        job_ctx = job.context or {}
        file_path = job_ctx.get("downloaded_file") or job_ctx.get("file_to_process")

        if not file_path:
            log.error("No file to extract from", job_id=job_id)
            job.status = "failed"
            job.error_message = "No file path in job context"
            await db.commit()
            return {"status": "failed", "message": "No file to extract from"}

        # Mark job as running
        job.status = "running"
        job.started_at = datetime.utcnow()
        await db.commit()

        steps = get_extract_steps()
        total_steps = len(steps)

        try:
            for i, step in enumerate(steps, 1):
                await step.execute(db, job, i, total_steps)

            # Extract steps completed successfully
            job.status = "completed"
            job.progress = 100
            job.current_step = "Extraction Complete"
            job.completed_at = datetime.utcnow()
            await db.commit()

            # Release DNO lock
            await _release_dno_lock(db, job.dno_id, log)

            log.info("✅ Extract job completed successfully")
            return {
                "status": "completed",
                "message": "Extraction completed",
            }

        except Exception as e:
            log.error("❌ Extract job failed", error=str(e))
            # Step base class handles job status update on failure

            # Release DNO lock even on failure
            await _release_dno_lock(db, job.dno_id, log)

            return {"status": "failed", "message": str(e)}


async def _release_dno_lock(db, dno_id: int, log):
    """Release the crawl lock on the DNO."""
    from app.db.models import DNOModel

    try:
        result = await db.execute(
            select(DNOModel).where(DNOModel.id == dno_id)
        )
        dno = result.scalar_one_or_none()

        if dno and dno.status == "crawling":
            dno.status = "crawled"
            dno.crawl_locked_at = None
            await db.commit()
            log.debug("Released DNO crawl lock", dno_id=dno_id)
    except Exception as e:
        log.warning("Failed to release DNO lock", dno_id=dno_id, error=str(e))
