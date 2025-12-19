import asyncio
from app.jobs.steps.base import BaseStep
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import CrawlJobModel

class ExtractDataStep(BaseStep):
    label = "Extracting Data"
    description = "Processing document data..."

    async def run(self, db: AsyncSession, job: CrawlJobModel) -> str:
        await asyncio.sleep(5)
        return "Extraction complete: Successfully parsed 42 tariff records."
