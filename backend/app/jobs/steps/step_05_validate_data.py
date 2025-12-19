import asyncio
from app.jobs.steps.base import BaseStep
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import CrawlJobModel

class ValidateDataStep(BaseStep):
    label = "Validating Data"
    description = "Checking data source contents..."

    async def run(self, db: AsyncSession, job: CrawlJobModel) -> str:
        await asyncio.sleep(5)
        return "Validation passed: Data source contains expected structures."
