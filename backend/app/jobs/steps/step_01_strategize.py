"""
Step 01: Strategize

Analyzes gathered context and decides the best strategy for finding data.

Decision tree:
1. If cached file exists → strategy = "use_cache"
2. If source profile has URL pattern → strategy = "try_pattern"  
3. Otherwise → strategy = "search" (prepare DuckDuckGo queries)

What it does:
- Check if we already have the file locally
- Check if we have a known URL pattern from previous successful crawls
- Prepare search queries based on DNO name, data type, and year

Output stored in job.context:
- strategy: "use_cache" | "try_pattern" | "search"
- file_to_process: path to cached file (if use_cache)
- pattern_url: URL to try (if try_pattern)
- search_queries: list of DDG queries (if search)
"""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CrawlJobModel
from app.jobs.steps.base import BaseStep


class StrategizeStep(BaseStep):
    label = "Planning Strategy"
    description = "Deciding how to find the data based on available knowledge..."

    async def run(self, db: AsyncSession, job: CrawlJobModel) -> str:
        # TODO: Replace mock with actual implementation
        
        await asyncio.sleep(0.3)
        
        ctx = job.context or {}
        
        # Priority 1: Use cached file
        if ctx.get("cached_file"):
            ctx["strategy"] = "use_cache"
            ctx["file_to_process"] = ctx["cached_file"]
            await db.commit()
            return "Strategy: USE_CACHE → Using locally cached file (skip search & download)"
        
        # Priority 2: Try known URL pattern
        if ctx.get("has_profile") and ctx.get("profile_url_pattern"):
            pattern = ctx["profile_url_pattern"]
            url = pattern.replace("{year}", str(job.year))
            
            ctx["strategy"] = "try_pattern"
            ctx["pattern_url"] = url
            ctx["search_queries"] = self._build_queries(ctx, job)  # Fallback if pattern fails
            await db.commit()
            return f"Strategy: TRY_PATTERN → Will try known URL: {url}"
        
        # Priority 3: Full search
        ctx["strategy"] = "search"
        ctx["search_queries"] = self._build_queries(ctx, job)
        await db.commit()
        
        return f"Strategy: SEARCH → Will search with {len(ctx['search_queries'])} query variations"
    
    def _build_queries(self, ctx: dict, job: CrawlJobModel) -> list[str]:
        """Build DuckDuckGo search queries."""
        dno_name = ctx.get("dno_name", "Unknown DNO")
        year = job.year
        
        if job.data_type == "netzentgelte":
            return [
                f'"{dno_name}" Netzentgelte {year} filetype:pdf',
                f'"{dno_name}" Preisblatt Netznutzung {year} filetype:pdf',
                f'"{dno_name}" Netzentgelte {year} filetype:xlsx',
                f'"{dno_name}" Netzentgelte {year}',
            ]
        else:  # hlzf
            return [
                f'"{dno_name}" Hochlastzeitfenster {year} filetype:pdf',
                f'"{dno_name}" HLZF {year} filetype:pdf',
                f'"{dno_name}" "§19 StromNEV" {year}',
                f'"{dno_name}" Hochlastzeitfenster {year}',
            ]
