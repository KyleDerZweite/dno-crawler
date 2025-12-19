"""
Step 02: Search

Executes external search to find data sources.

What it does:
- Skip if strategy is "use_cache"
- If strategy is "try_pattern", first check if pattern URL exists
- If pattern fails or strategy is "search", execute DuckDuckGo queries
- Try each result until a valid source is found

Output stored in job.context:
- found_url: URL that was found
- successful_query: which query found it (for learning)
"""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CrawlJobModel
from app.jobs.steps.base import BaseStep


class SearchStep(BaseStep):
    label = "Searching"
    description = "Searching for data sources via DuckDuckGo..."

    async def run(self, db: AsyncSession, job: CrawlJobModel) -> str:
        # TODO: Replace mock with actual implementation
        
        ctx = job.context or {}
        strategy = ctx.get("strategy", "search")
        
        # Skip if using cache
        if strategy == "use_cache":
            return "Skipped → Using cached file"
        
        await asyncio.sleep(1.0)  # Simulate search time
        
        # Try pattern first (if that's the strategy)
        if strategy == "try_pattern":
            pattern_url = ctx.get("pattern_url")
            
            # TODO: Actually check if URL exists
            # exists = await self._url_exists(pattern_url)
            exists = False  # Mock: Pattern doesn't work
            
            if exists:
                ctx["found_url"] = pattern_url
                ctx["successful_query"] = "pattern"
                await db.commit()
                return f"Pattern worked! Found: {pattern_url}"
            else:
                # Pattern failed, fall back to search
                ctx["strategy"] = "search"
        
        # Execute search queries
        queries = ctx.get("search_queries", [])
        
        for query in queries:
            # TODO: Actually search DuckDuckGo
            # results = await self._search_duckduckgo(query)
            # for result in results:
            #     if await self._validate_source(result.url, job.data_type):
            #         ctx["found_url"] = result.url
            #         ctx["successful_query"] = query
            #         await db.commit()
            #         return f"Found via search: {result.url}"
            pass
        
        # Mock: Simulate finding something
        mock_url = f"https://example-dno.de/downloads/netzentgelte-{job.year}.pdf"
        ctx["found_url"] = mock_url
        ctx["successful_query"] = queries[0] if queries else "mock"
        await db.commit()
        
        return f"Found: {mock_url}"
    
    async def _url_exists(self, url: str) -> bool:
        """Check if a URL exists (HEAD request)."""
        # TODO: Implement actual URL check
        return False
    
    async def _search_duckduckgo(self, query: str) -> list:
        """Search DuckDuckGo and return results."""
        # TODO: Implement actual DuckDuckGo search
        return []
