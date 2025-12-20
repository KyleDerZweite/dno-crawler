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

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CrawlJobModel
from app.jobs.steps.base import BaseStep


class StrategizeStep(BaseStep):
    label = "Planning Strategy"
    description = "Deciding how to find the data based on available knowledge..."

    async def run(self, db: AsyncSession, job: CrawlJobModel) -> str:
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
        raw_name = ctx.get("dno_name", "Unknown DNO")
        
        # Normalize name (remove "GmbH", "(RNG)", etc.)
        name = raw_name.replace("GmbH", "").replace("AG", "").split("(")[0].strip()
        
        year = job.year
        
        # Extract domain for site: filter if website is known
        website = ctx.get("dno_website")
        site_filter = ""
        if website:
            from urllib.parse import urlparse
            parsed = urlparse(website)
            if parsed.hostname:
                domain = parsed.hostname.lower()
                if domain.startswith("www."):
                    domain = domain[4:]
                site_filter = f"site:{domain} "
        
        if job.data_type == "netzentgelte":
            queries = []
            # Priority 1: Site-specific searches (if website known)
            if site_filter:
                queries.extend([
                    f'{site_filter}Netzentgelte {year} filetype:pdf',
                    f'{site_filter}Preisblatt {year} filetype:pdf',
                    f'{site_filter}Netzentgelte {year}',
                ])
            # Priority 2: Name-based searches
            queries.extend([
                f'"{raw_name}" Netzentgelte {year} filetype:pdf',
                f'"{name}" Preisblatt Netznutzung {year} filetype:pdf',
                f'"{name}" Netzentgelte {year} filetype:pdf',
                f'"{name}" Netzentgelte {year} filetype:xlsx',
                f'"{name}" Netzentgelte {year}',
                f'{name} Netzentgelte {year}',
            ])
            return queries
        else:  # hlzf
            queries = []
            if site_filter:
                queries.extend([
                    f'{site_filter}Hochlastzeitfenster {year}',
                    f'{site_filter}HLZF {year}',
                ])
            queries.extend([
                f'"{name}" Hochlastzeitfenster {year} filetype:pdf',
                f'"{name}" HLZF {year} filetype:pdf',
                f'"{name}" "§19 StromNEV" {year}',
                f'"{name}" Hochlastzeitfenster {year}',
                f'{name} Hochlastzeitfenster {year}',
                f'{name} HLZF {year}',
            ])
            return queries
