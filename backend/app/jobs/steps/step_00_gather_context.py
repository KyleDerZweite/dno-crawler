"""
Step 00: Gather Context

First step in the crawl pipeline. Loads all relevant information
about the DNO and any prior crawl history into the job context.

What it does:
- Load DNO details (name, slug, website)
- Load source profile (if exists) with known URL patterns
- Check for cached files in data/downloads/{slug}/
- Load historical extraction data for reference

Output stored in job.context:
- dno_id, dno_slug, dno_name, dno_website
- has_profile, profile_url_pattern, profile_source_format
- cached_file (path if exists)
"""

import asyncio
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CrawlJobModel, DNOModel, DNOSourceProfile
from app.jobs.steps.base import BaseStep


class GatherContextStep(BaseStep):
    label = "Gathering Context"
    description = "Loading DNO info, source profile, and checking for cached files..."

    async def run(self, db: AsyncSession, job: CrawlJobModel) -> str:
        # TODO: Replace mock with actual implementation
        
        # Mock: Simulate loading DNO
        await asyncio.sleep(0.5)
        
        # In real implementation:
        # 1. Load DNO from database
        # dno = await db.get(DNOModel, job.dno_id)
        
        # 2. Load source profile for this DNO + data_type
        # profile_query = select(DNOSourceProfile).where(
        #     DNOSourceProfile.dno_id == job.dno_id,
        #     DNOSourceProfile.data_type == job.data_type
        # )
        # profile = (await db.execute(profile_query)).scalar_one_or_none()
        
        # 3. Check for cached file
        # cache_dir = Path(f"data/downloads/{dno.slug}")
        # pattern = f"{dno.slug}-{job.data_type}-{job.year}.*"
        # cached_files = list(cache_dir.glob(pattern)) if cache_dir.exists() else []
        
        # 4. Build context
        job.context = {
            "dno_id": job.dno_id,
            "dno_slug": "rheinnetz",
            "dno_name": "RheinNetz GmbH (RNG)",
            "dno_website": "https://www.rheinnetz.de/",
            "has_profile": False,  # Mock: No profile yet
            "profile_url_pattern": None,
            "profile_source_format": None,
            "cached_file": None,  # Mock: No cache
        }
        await db.commit()
        
        # Return summary
        cached = job.context.get("cached_file")
        has_profile = job.context.get("has_profile")
        
        if cached:
            return f"Found cached file: {Path(cached).name}"
        elif has_profile:
            return f"Has source profile (format: {job.context.get('profile_source_format')})"
        else:
            return "No prior knowledge - will search from scratch"
