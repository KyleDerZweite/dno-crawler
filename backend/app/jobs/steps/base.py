from abc import ABC, abstractmethod
from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CrawlJobModel, CrawlJobStepModel

logger = structlog.get_logger()


class StepError(Exception):
    """Custom exception for step failures that should be displayed to users.

    Use this for controlled failures with user-friendly messages,
    as opposed to unexpected exceptions.
    """

    pass


class BaseStep(ABC):
    """Base class for all crawl job steps."""

    label: str = "Base Step"
    description: str = "Performing base step..."

    def __init__(self):
        self.log = logger.bind(step=self.label)

    @abstractmethod
    async def run(self, db: AsyncSession, job: CrawlJobModel) -> None:
        """Logic for the step goes here."""
        pass

    async def execute(
        self, db: AsyncSession, job: CrawlJobModel, step_num: int, total_steps: int
    ) -> None:
        """Wrapper around run() that handles DB updates and logging."""
        self.log.info(f"Starting step {step_num}/{total_steps}")

        # 1. Update Job progress
        job.current_step = self.label
        job.progress = int(((step_num - 1) / total_steps) * 100)

        # 2. Create Step record
        step_record = CrawlJobStepModel(
            job_id=job.id,
            step_name=self.label,
            status="running",
            started_at=datetime.now(UTC),
            details={"description": self.description},
        )
        db.add(step_record)
        await db.commit()
        await db.refresh(step_record)

        start_time = datetime.now(UTC)
        try:
            # 3. Actually run the step
            result_msg = await self.run(db, job)

            # 4. Mark step as done
            end_time = datetime.now(UTC)
            step_record.status = "done"
            step_record.completed_at = end_time
            step_record.duration_seconds = int((end_time - start_time).total_seconds())

            # Add result to details if returned
            if result_msg:
                step_record.details = {**(step_record.details or {}), "result": result_msg}

            job.progress = int((step_num / total_steps) * 100)
            await db.commit()
            self.log.info(f"Step {step_num}/{total_steps} completed")

        except Exception as e:
            self.log.error(f"Step {step_num} failed", error=str(e))

            # Rollback the failed transaction to clear the error state
            # (e.g. if the step failed due to a DB error like UndefinedColumn)
            await db.rollback()

            # After rollback, ORM objects may be detached/expired.
            # Re-attach them via merge() so we can update failure state.
            try:
                step_record = await db.merge(step_record)
                job = await db.merge(job)

                step_record.status = "failed"
                step_record.completed_at = datetime.now(UTC)
                step_record.details = {"description": self.description, "error": str(e)}

                job.status = "failed"
                job.completed_at = datetime.now(UTC)
                job.error_message = f"Step '{self.label}' failed: {e!s}"

                await db.commit()
            except Exception as commit_err:
                self.log.error("Failed to persist failure state", error=str(commit_err))
                # Don't mask the original error
            raise e
