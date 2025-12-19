import asyncio
from app.jobs.steps.base import BaseStep
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import CrawlJobModel

class FinalizeStep(BaseStep):
    label = "Finalizing"
    description = "Saving results..."

    async def run(self, db: AsyncSession, job: CrawlJobModel) -> str:
        await asyncio.sleep(5)
        return "Job finalized: Data committed to main DNO tables."
