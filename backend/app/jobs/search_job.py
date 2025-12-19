"""
TEMPORARY WORKER for queue and status update testing.

This simplified worker:
1. Accepts the job from the queue
2. Updates status/steps every 5 seconds
3. Simulates processing without actual complex logic

Replace with actual implementation once queue mechanism is verified.
"""

import asyncio
from datetime import datetime

import structlog

from app.db import get_db_session

logger = structlog.get_logger()


async def process_dno_crawl(
    ctx: dict,
    job_id: int,
) -> dict:
    """
    Orchestrates the DNO crawl process using modular steps.
    """
    from app.jobs.steps import CRAWL_JOB_STEPS
    from app.db.models import CrawlJobModel
    from sqlalchemy import select

    log = logger.bind(job_id=job_id)
    log.info("🚀 Job received, starting execution")
    
    async with get_db_session() as db:
        result = await db.execute(
            select(CrawlJobModel).where(CrawlJobModel.id == job_id)
        )
        job = result.scalar_one_or_none()
        
        if not job:
            log.error("Job not found", job_id=job_id)
            return {"status": "error", "message": "Job not found"}
        
        job.status = "running"
        job.started_at = datetime.utcnow()
        await db.commit()
        
        total_steps = len(CRAWL_JOB_STEPS)
        
        try:
            for i, step in enumerate(CRAWL_JOB_STEPS, 1):
                # execute() handles commit for status and progress
                await step.execute(db, job, i, total_steps)
            
            # Finalize Job status
            job.status = "completed"
            job.progress = 100
            job.current_step = "Completed"
            job.completed_at = datetime.utcnow()
            await db.commit()
            
            log.info("✅ Job completed successfully")
            return {"status": "completed", "message": "Workflow completed"}
            
        except Exception as e:
            log.error("❌ Job failed", error=str(e))
            # Step base class handles job status update on failure
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
