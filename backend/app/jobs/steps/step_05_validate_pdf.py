import asyncio
from app.jobs.steps.base import BaseStep
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import CrawlJobModel

class ValidatePDFStep(BaseStep):
    label = "Validating PDF"
    description = "Checking document contents..."

    async def run(self, db: AsyncSession, job: CrawlJobModel) -> None:
        await asyncio.sleep(5)
        pass
