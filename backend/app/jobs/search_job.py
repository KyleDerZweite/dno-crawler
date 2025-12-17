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
    job_id: int,  # First positional arg after ctx - matches how API enqueues
) -> dict:
    """
    TEMPORARY: Simplified job function for testing queue mechanism.
    
    Accepts the job ID, then simulates processing with 5-second status updates.
    
    Args:
        ctx: ARQ context (contains redis connection etc)
        job_id: CrawlJobModel.id from the database
    """
    log = logger.bind(job_id=job_id)
    log.info("🧪 TEMP WORKER: Job received")
    
    # Get job from DB and mark as running
    async with get_db_session() as db:
        from sqlalchemy import select
        from app.db.models import CrawlJobModel
        
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
    
    log.info("🧪 TEMP WORKER: Job marked as running")
    
    # Simulate processing with status updates - step definitions with mock results
    # Format: step_num -> (label, running_state, complete_result)
    test_steps = {
        1: ("Analyzing Input", "Parsing the search query...", f"DNO-Id: {job.dno_id}, Type: {job.data_type}"),
        2: ("Checking Cache", "Looking up cached DNO mappings...", f"Found DNO ID: {job.dno_id}"),
        3: ("External Search", "Crawling external site's...", f"Year: {job.year}, Data type: {job.data_type}"),
        4: ("Finding PDF", "Searching for relevant documents...", "PDF found: document.pdf"),
        5: ("Downloading PDF", "Fetching document...", "Downloaded 1.2 MB"),
        6: ("Validating PDF", "Checking document contents...", "PDF validated successfully"),
        7: ("Extracting Data", "Processing document data...", "Extracted 12 data points"),
        8: ("Finalizing", "Saving results...", "Results saved to database"),
    }
    
    for step_num, (label, running_state, complete_result) in test_steps.items():
        log.info(f"🧪 TEMP WORKER: Step {step_num}/{len(test_steps)} - {label}")
        
        # Report step as running
        await _update_step(job_id, step_num, label, "running", running_state)
        
        # Wait 5 seconds
        await asyncio.sleep(5)
        
        # Report step as done with result text
        await _update_step(job_id, step_num, label, "done", running_state, result_text=complete_result)
        
        log.info(f"🧪 TEMP WORKER: Step {step_num}/{len(test_steps)} - {label} DONE")
    
    # Mark job as completed with mock result
    async with get_db_session() as db:
        from sqlalchemy import select
        from app.db.models import CrawlJobModel
        
        result = await db.execute(
            select(CrawlJobModel).where(CrawlJobModel.id == job_id)
        )
        job = result.scalar_one_or_none()
        
        if job:
            job.status = "completed"
            job.current_step = "Completed"
            job.progress = 100
            job.completed_at = datetime.utcnow()
            await db.commit()
    
    log.info("🧪 TEMP WORKER: Job completed successfully")
    return {"status": "completed", "message": "Test worker completed"}


async def _update_step(
    job_id: int,
    step_num: int,
    label: str,
    status: str,
    detail: str,
    result_text: str | None = None,
) -> None:
    """Update job step in database for frontend polling.
    
    Creates/updates CrawlJobStepModel entries with proper status and result details.
    """
    try:
        async with get_db_session() as db:
            from sqlalchemy import select
            from app.db.models import CrawlJobModel, CrawlJobStepModel
            
            result = await db.execute(
                select(CrawlJobModel).where(CrawlJobModel.id == job_id)
            )
            job = result.scalar_one_or_none()
            
            if not job:
                return
            
            # Update current step and progress on job
            job.current_step = label
            job.progress = int((step_num / 8) * 100)  # 8 total steps
            
            # Find or create step entry
            step_result = await db.execute(
                select(CrawlJobStepModel).where(
                    CrawlJobStepModel.job_id == job_id,
                    CrawlJobStepModel.step_name == label
                )
            )
            step = step_result.scalar_one_or_none()
            
            if status == "running":
                if not step:
                    # Create new step entry
                    step = CrawlJobStepModel(
                        job_id=job_id,
                        step_name=label,
                        status="running",
                        started_at=datetime.utcnow(),
                        details={"running_state": detail}
                    )
                    db.add(step)
                else:
                    step.status = "running"
                    step.started_at = datetime.utcnow()
                    step.details = {"running_state": detail}
            elif status == "done" and step:
                step.status = "done"
                step.completed_at = datetime.utcnow()
                if step.started_at:
                    step.duration_seconds = int(
                        (step.completed_at - step.started_at).total_seconds()
                    )
                step.details = {
                    "running_state": step.details.get("running_state", "") if step.details else "",
                    "result": result_text or detail
                }
            
            await db.commit()
            
    except Exception as e:
        logger.error("Failed to update step", error=str(e))
