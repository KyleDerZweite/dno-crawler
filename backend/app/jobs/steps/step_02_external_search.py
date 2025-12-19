import asyncio
from app.jobs.steps.base import BaseStep
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import CrawlJobModel

class ExternalSearchStep(BaseStep):
    label = "External Search"
    description = "Querying external APIs..."

    async def run(self, db: AsyncSession, job: CrawlJobModel) -> None:
        await asyncio.sleep(5)
        pass
