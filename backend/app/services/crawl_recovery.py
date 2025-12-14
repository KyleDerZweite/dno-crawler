"""
Crawl Recovery Service for handling stuck crawl jobs.

Recovers DNOs stuck in 'crawling' status due to crashes, OOM, or server restarts.
Should be called on application startup.
"""

from datetime import datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DNOModel

logger = structlog.get_logger()


async def recover_stuck_crawl_jobs(
    db: AsyncSession,
    timeout_hours: int = 1,
) -> int:
    """
    Reset DNOs stuck in 'crawling' status.
    
    Call this on application startup to recover from crashes/OOM.
    
    Args:
        db: Database session
        timeout_hours: Consider jobs stuck if locked longer than this
        
    Returns:
        Number of recovered jobs
    """
    log = logger.bind(timeout_hours=timeout_hours)
    log.info("Checking for stuck crawl jobs")
    
    timeout_threshold = datetime.utcnow() - timedelta(hours=timeout_hours)
    
    result = await db.execute(
        select(DNOModel).where(
            DNOModel.status == "crawling",
            DNOModel.crawl_locked_at < timeout_threshold,
        )
    )
    stuck_dnos = result.scalars().all()
    
    recovered_count = 0
    for dno in stuck_dnos:
        dno.status = "failed"
        dno.crawl_locked_at = None
        log.warning(
            "Recovered stuck crawl job",
            dno_id=dno.id,
            dno_name=dno.name,
            stuck_since=dno.crawl_locked_at,
        )
        recovered_count += 1
    
    if recovered_count > 0:
        await db.commit()
        log.info("Recovered stuck crawl jobs", count=recovered_count)
    else:
        log.debug("No stuck crawl jobs found")
    
    return recovered_count
