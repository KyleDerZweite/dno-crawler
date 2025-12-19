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

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CrawlJobModel, DNOModel, DNOSourceProfile
from app.jobs.steps.base import BaseStep


class GatherContextStep(BaseStep):
    label = "Gathering Context"
    description = "Loading DNO info, source profile, and checking for cached files..."

    async def run(self, db: AsyncSession, job: CrawlJobModel) -> str:
        # 1. Load DNO from database
        dno = await db.get(DNOModel, job.dno_id)
        if not dno:
            raise ValueError(f"DNO not found: {job.dno_id}")
        
        # 2. Load source profile for this DNO + data_type (if exists)
        profile_query = select(DNOSourceProfile).where(
            DNOSourceProfile.dno_id == job.dno_id,
            DNOSourceProfile.data_type == job.data_type
        )
        result = await db.execute(profile_query)
        profile = result.scalar_one_or_none()
        
        # 3. Check for cached files
        cache_dir = Path("data/downloads") / dno.slug
        pattern = f"{dno.slug}-{job.data_type}-{job.year}.*"
        cached_files = list(cache_dir.glob(pattern)) if cache_dir.exists() else []
        cached_file = str(cached_files[0]) if cached_files else None
        
        # 4. Build context
        job.context = {
            "dno_id": dno.id,
            "dno_slug": dno.slug,
            "dno_name": dno.name,
            "dno_website": dno.website,
            "has_profile": profile is not None,
            "profile_url_pattern": profile.url_pattern if profile else None,
            "profile_source_format": profile.source_format if profile else None,
            "cached_file": cached_file,
        }
        await db.commit()
        
        # Return summary based on what we found
        if cached_file:
            return f"Found cached file: {Path(cached_file).name}"
        elif profile:
            return f"Has source profile (format: {profile.source_format}, domain: {profile.source_domain})"
        else:
            return f"No prior knowledge for {dno.name} - will search from scratch"
