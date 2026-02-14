"""
Crawl Recovery Service for handling stuck crawl jobs.

Recovers DNOs stuck in 'crawling' status due to crashes, OOM, or server restarts.
Also resets stale CrawlJobModel entries stuck in pending/running status.
Should be called on application startup.
"""

from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CrawlJobModel, DNOModel

logger = structlog.get_logger()


async def recover_stuck_crawl_jobs(
    db: AsyncSession,
    timeout_hours: int = 1,
) -> int:
    """
    Reset DNOs and CrawlJobs stuck due to crashes/OOM.

    Call this on application startup to recover from crashes.

    Args:
        db: Database session
        timeout_hours: Consider jobs stuck if created longer than this ago

    Returns:
        Number of recovered jobs
    """
    log = logger.bind(timeout_hours=timeout_hours)
    log.info("Checking for stuck crawl jobs")

    timeout_threshold = datetime.now(UTC) - timedelta(hours=timeout_hours)
    recovered_count = 0

    # 1. Recover stuck DNO statuses
    result = await db.execute(
        select(DNOModel).where(
            DNOModel.status == "crawling",
            DNOModel.crawl_locked_at < timeout_threshold,
        )
    )
    stuck_dnos = result.scalars().all()

    for dno in stuck_dnos:
        dno.status = "failed"
        dno.crawl_locked_at = None
        log.warning(
            "Recovered stuck DNO status",
            dno_id=dno.id,
            dno_name=dno.name,
        )
        recovered_count += 1

    # 2. Recover stuck CrawlJobModel entries
    job_result = await db.execute(
        select(CrawlJobModel).where(
            CrawlJobModel.status.in_(["pending", "running"]),
            CrawlJobModel.created_at < timeout_threshold,
        )
    )
    stuck_jobs = job_result.scalars().all()

    for job in stuck_jobs:
        job.status = "failed"
        job.error_message = "Timed out - recovered on startup"
        job.completed_at = datetime.now(UTC)
        log.warning(
            "Recovered stuck crawl job",
            job_id=job.id,
            dno_id=job.dno_id,
            status_was=job.status,
        )
        recovered_count += 1

    if recovered_count > 0:
        await db.commit()
        log.info("Recovered stuck crawl jobs", count=recovered_count)
    else:
        log.debug("No stuck crawl jobs found")

    return recovered_count
