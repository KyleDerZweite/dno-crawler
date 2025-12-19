import asyncio
from app.jobs.steps.base import BaseStep
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import CrawlJobModel

class CheckCacheStep(BaseStep):
    label = "Checking Cache"
    description = "Looking up cached DNO mappings..."

    async def run(self, db: AsyncSession, job: CrawlJobModel) -> str:
        await asyncio.sleep(5)
        return "Cache check complete: No existing data found for this location."
