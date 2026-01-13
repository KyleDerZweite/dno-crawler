from abc import ABC, abstractmethod
from datetime import datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CrawlJobModel, CrawlJobStepModel

logger = structlog.get_logger()

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

    async def execute(self, db: AsyncSession, job: CrawlJobModel, step_num: int, total_steps: int) -> None:
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
            started_at=datetime.utcnow(),
            details={"description": self.description}
        )
        db.add(step_record)
        await db.commit()
        await db.refresh(step_record)

        start_time = datetime.utcnow()
        try:
            # 3. Actually run the step
            result_msg = await self.run(db, job)

            # 4. Mark step as done
            end_time = datetime.utcnow()
            step_record.status = "done"
            step_record.completed_at = end_time
            step_record.duration_seconds = int((end_time - start_time).total_seconds())

            # Add result to details if returned
            if result_msg:
                step_record.details = {
                    **(step_record.details or {}),
                    "result": result_msg
                }

            job.progress = int((step_num / total_steps) * 100)
            await db.commit()
            self.log.info(f"Step {step_num}/{total_steps} completed")

        except Exception as e:
            self.log.error(f"Step {step_num} failed", error=str(e))

            # Rollback the failed transaction to clear the error state
            # (e.g. if the step failed due to a DB error like UndefinedColumn)
            await db.rollback()

            # Update step record with error
            # We need to set fields again because rollback reverted any pending changes
            step_record.status = "failed"
            step_record.completed_at = datetime.utcnow()
            # Preserve existing details if possible, or reset
            step_record.details = {
                "description": self.description,
                "error": str(e)
            }

            # Update main job
            job.status = "failed"
            job.error_message = f"Step '{self.label}' failed: {e!s}"
            
            # Commit the failure state in a fresh transaction
            await db.commit()
            raise e
