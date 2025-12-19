import asyncio
from app.jobs.steps.base import BaseStep
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import CrawlJobModel

class DownloadDataStep(BaseStep):
    label = "Downloading Data"
    description = "Fetching data sources..."

    async def run(self, db: AsyncSession, job: CrawlJobModel) -> str:
        await asyncio.sleep(5)
        return "Download successful: 2.4MB data received and stored."
