import asyncio
from app.jobs.steps.base import BaseStep
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import CrawlJobModel

class ParseInputStep(BaseStep):
    label = "Analyzing Input"
    description = "Parsing the search query..."

    async def run(self, db: AsyncSession, job: CrawlJobModel) -> None:
        # Simulate processing
        await asyncio.sleep(5)
        # Here we could store parsed info in job.details if we had that field
        pass
