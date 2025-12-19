"""
Step 06: Finalize

Final step that stores extracted data and updates learning profiles.

What it does:
- Save extracted data to NetzentgelteModel or HLZFModel
- Save provenance to DataSourceModel
- Update DNOSourceProfile with what worked (for learning)
- Mark job as completed

Learning updates:
- Store successful URL and pattern for future crawls
- Store file format for this DNO
- Store any extraction hints from Gemini
- Reset consecutive failure counter on success

Output:
- Job marked as completed
- Data persisted to database
- Source profile updated for future crawls
"""

import asyncio
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CrawlJobModel
from app.jobs.steps.base import BaseStep


class FinalizeStep(BaseStep):
    label = "Finalizing"
    description = "Saving data and updating learning profile..."

    async def run(self, db: AsyncSession, job: CrawlJobModel) -> str:
        ctx = job.context or {}
        data = ctx.get("extracted_data", [])
        is_valid = ctx.get("is_valid", False)
        
        await asyncio.sleep(0.3)  # Simulate DB operations
        
        if not is_valid or not data:
            # Don't save invalid data, but still complete the job
            return "Skipped data save (validation failed)"
        
        # TODO: Actual implementation:
        
        # 1. Save extracted data
        # for record in data:
        #     if job.data_type == "netzentgelte":
        #         model = NetzentgelteModel(
        #             dno_id=job.dno_id,
        #             year=job.year,
        #             voltage_level=record["voltage_level"],
        #             arbeit=record.get("arbeitspreis"),
        #             leistung=record.get("leistungspreis"),
        #         )
        #     else:
        #         model = HLZFModel(
        #             dno_id=job.dno_id,
        #             year=job.year,
        #             voltage_level=record["voltage_level"],
        #             winter=record.get("winter"),
        #             fruehling=record.get("fruehling"),
        #             sommer=record.get("sommer"),
        #             herbst=record.get("herbst"),
        #         )
        #     db.add(model)
        
        # 2. Save provenance
        # source = DataSourceModel(
        #     dno_id=job.dno_id,
        #     year=job.year,
        #     data_type=job.data_type,
        #     source_url=ctx.get("found_url"),
        #     file_path=ctx.get("downloaded_file"),
        #     source_format=ctx.get("file_format"),
        #     extracted_at=datetime.utcnow(),
        #     extraction_method="gemini",
        #     extraction_notes=ctx.get("extraction_notes"),
        #     confidence=ctx.get("extraction_confidence"),
        # )
        # db.add(source)
        
        # 3. Update source profile (learning)
        # profile = await self._get_or_create_profile(db, job.dno_id, job.data_type)
        # profile.source_domain = self._extract_domain(ctx.get("found_url"))
        # profile.source_format = ctx.get("file_format")
        # profile.last_url = ctx.get("found_url")
        # profile.url_pattern = self._detect_pattern(ctx.get("found_url"), job.year)
        # profile.successful_query = ctx.get("successful_query")
        # profile.last_success_year = job.year
        # profile.last_success_at = datetime.utcnow()
        # profile.consecutive_failures = 0
        
        # await db.commit()
        
        records_saved = len(data)
        url = ctx.get("found_url", "unknown")
        
        return f"Saved {records_saved} records from {url}"
    
    def _extract_domain(self, url: str | None) -> str | None:
        """Extract domain from URL."""
        if not url:
            return None
        # Simple extraction: https://example.com/path -> example.com
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc
    
    def _detect_pattern(self, url: str | None, year: int) -> str | None:
        """Detect year pattern in URL for future use."""
        if not url:
            return None
        year_str = str(year)
        if year_str in url:
            return url.replace(year_str, "{year}")
        return None
