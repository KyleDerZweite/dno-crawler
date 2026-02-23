"""Shared job orchestration helpers."""

from datetime import UTC, datetime

from app.db.models import CrawlJobModel


async def mark_job_running(job: CrawlJobModel, db) -> bool:
    """Mark a job as running.

    Returns False when the job is already completed/cancelled and should be treated as idempotent.
    """
    if job.status in {"completed", "cancelled", "running"}:
        return False

    if not job.started_at:
        job.started_at = datetime.now(UTC)

    job.status = "running"
    await db.commit()
    return True


async def mark_job_completed(job: CrawlJobModel, db, current_step: str) -> None:
    """Mark a job as completed with final metadata."""
    job.status = "completed"
    job.progress = 100
    job.current_step = current_step
    job.completed_at = datetime.now(UTC)
    await db.commit()


async def ensure_job_failure_timestamp(job: CrawlJobModel, db) -> None:
    """Ensure a failed job has a completion timestamp persisted."""
    if not job.completed_at:
        job.completed_at = datetime.now(UTC)
        await db.commit()
