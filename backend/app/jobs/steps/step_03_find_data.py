import asyncio
from app.jobs.steps.base import BaseStep
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import CrawlJobModel

class FindDataStep(BaseStep):
    label = "Finding Data"
    description = "Searching for relevant data sources..."

    async def run(self, db: AsyncSession, job: CrawlJobModel) -> str:
        await asyncio.sleep(5)
        return "Data location identified: 'https://www.westnetz.de/netzentgelte-2025.pdf' (PDF Source)"
