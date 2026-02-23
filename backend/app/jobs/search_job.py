"""
TEMPORARY WORKER for queue and status update testing.

This simplified worker:
1. Accepts the job from the queue
2. Updates status/steps every 5 seconds
3. Simulates processing without actual complex logic

Replace with actual implementation once queue mechanism is verified.
"""

import contextlib

import structlog

from app.db import get_db_session
from app.jobs.common import ensure_job_failure_timestamp, mark_job_completed, mark_job_running

logger = structlog.get_logger()


async def process_dno_crawl(
    ctx: dict,
    job_id: int,
) -> dict:
    """
    Orchestrates the DNO crawl process using modular steps.
    """
    from sqlalchemy import select

    from app.db.models import CrawlJobModel
    from app.jobs.steps import CRAWL_JOB_STEPS

    log = logger.bind(job_id=job_id)
    log.info("🚀 Job received, starting execution")

    async with get_db_session() as db:
        result = await db.execute(select(CrawlJobModel).where(CrawlJobModel.id == job_id))
        job = result.scalar_one_or_none()

        if not job:
            log.error("Job not found", job_id=job_id)
            return {"status": "error", "message": "Job not found"}

        should_run = await mark_job_running(job, db)
        if not should_run:
            log.info("Search job already finalized; skipping re-execution")
            return {"status": job.status, "message": "Job already finalized"}

        total_steps = len(CRAWL_JOB_STEPS)

        try:
            for i, step in enumerate(CRAWL_JOB_STEPS, 1):
                # execute() handles commit for status and progress
                await step.execute(db, job, i, total_steps)

            # Finalize Job status
            await mark_job_completed(job, db, current_step="Completed")

            log.info("✅ Job completed successfully")
            return {"status": "completed", "message": "Workflow completed"}

        except Exception as e:
            log.error("❌ Job failed", error=str(e))
            # BaseStep sets job.status/completed_at on step failures,
            # but ensure completed_at is set even for non-step errors
            with contextlib.suppress(Exception):
                await ensure_job_failure_timestamp(job, db)
            return {"status": "failed", "message": str(e)}


# Note: _update_step is now handled by Step classes, but we keep it for now if needed elsewhere
async def _update_step(
    job_id: int,
    step_num: int,
    label: str,
    status: str,
    detail: str,
) -> None:
    """Legacy helper, now handled by step classes."""
    pass
