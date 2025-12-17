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
from typing import Optional

import structlog

from app.db import get_db_session

logger = structlog.get_logger()


async def process_dno_crawl(
    ctx: dict, 
    # Structured payload format (from batch search)
    payload: Optional[dict] = None,
    # NL search format
    job_id: Optional[str] = None,
    prompt: Optional[str] = None,
    filters: Optional[dict] = None,
) -> dict:
    """
    TEMPORARY: Simplified job function for testing queue mechanism.
    
    Accepts the job, then simulates processing with 5-second status updates.
    """
    log = logger.bind(job_id=job_id)
    log.info("🧪 TEMP WORKER: Job received", payload=payload, prompt=prompt)
    
    # Get job from DB and mark as running
    async with get_db_session() as db:
        from sqlalchemy import select
        from app.db.models import SearchJobModel
        
        result = await db.execute(
            select(SearchJobModel).where(SearchJobModel.id == job_id)
        )
        job = result.scalar_one_or_none()
        
        if not job:
            log.error("Job not found", job_id=job_id)
            return {"status": "error", "message": "Job not found"}
        
        job.status = "running"
        job.started_at = datetime.utcnow()
        await db.commit()
    
    log.info("🧪 TEMP WORKER: Job marked as running")
    
    # Simulate processing with status updates
    test_steps = [
        ("Analyzing Input", "Parsing the search query..."),
        ("Checking Cache", "Looking up cached DNO mappings..."),
        ("External Search", "Querying external APIs..."),
        ("Finding PDF", "Searching for relevant documents..."),
        ("Downloading PDF", "Fetching document..."),
        ("Validating PDF", "Checking document contents..."),
        ("Extracting Data", "Processing document data..."),
        ("Finalizing", "Saving results..."),
    ]
    
    for i, (label, detail) in enumerate(test_steps, 1):
        log.info(f"🧪 TEMP WORKER: Step {i}/{len(test_steps)} - {label}")
        
        # Report step as running
        await _update_step(job_id, i, label, "running", detail)
        
        # Wait 5 seconds
        await asyncio.sleep(5)
        
        # Report step as done
        await _update_step(job_id, i, label, "done", f"Completed: {detail}")
        
        log.info(f"🧪 TEMP WORKER: Step {i}/{len(test_steps)} - {label} DONE")
    
    # Mark job as completed with mock result
    async with get_db_session() as db:
        from sqlalchemy import select
        from app.db.models import SearchJobModel
        
        result = await db.execute(
            select(SearchJobModel).where(SearchJobModel.id == job_id)
        )
        job = result.scalar_one_or_none()
        
        if job:
            job.status = "completed"
            job.result = {
                "dno_name": "Test DNO (Temporary Worker)",
                "netzentgelte": {"2024": [], "2025": []},
                "hlzf": {"2024": [], "2025": []},
                "note": "This is mock data from the temporary test worker",
            }
            job.completed_at = datetime.utcnow()
            await db.commit()
    
    log.info("🧪 TEMP WORKER: Job completed successfully")
    return {"status": "completed", "message": "Test worker completed"}


async def _update_step(
    job_id: str,
    step_num: int,
    label: str,
    status: str,
    detail: str,
) -> None:
    """Update job step in database for frontend polling."""
    try:
        async with get_db_session() as db:
            from sqlalchemy import select
            from app.db.models import SearchJobModel
            
            result = await db.execute(
                select(SearchJobModel).where(SearchJobModel.id == job_id)
            )
            job = result.scalar_one_or_none()
            
            if not job:
                return
            
            now = datetime.utcnow().isoformat()
            
            if status == "running":
                # Add new step
                new_step = {
                    "step": step_num,
                    "label": label,
                    "status": status,
                    "detail": detail,
                    "started_at": now,
                }
                job.steps_history = [*job.steps_history, new_step]
                job.current_step = label
            else:
                # Update last step
                if job.steps_history:
                    updated_history = list(job.steps_history)
                    updated_history[-1] = {
                        **updated_history[-1],
                        "status": status,
                        "detail": detail,
                        "completed_at": now,
                    }
                    job.steps_history = updated_history
            
            await db.commit()
            
    except Exception as e:
        logger.error("Failed to update step", error=str(e))
