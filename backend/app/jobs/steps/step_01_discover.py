"""
Step 01: Discover

Combined strategy and discovery step. Finds data sources via:
1. Cached file (if exists) → Skip crawling
2. Exact URL from profile → Try known URL with year substitution
3. Learned patterns → Try top patterns on DNO domain
4. BFS crawl → Full website crawl with keyword scoring

Output stored in job.context:
- strategy: "use_cache" | "exact_url" | "pattern_match" | "bfs_crawl"
- found_url: URL of discovered data source
- discovered_via_pattern: Which pattern found it (if pattern_match)
- pages_crawled: Number of pages crawled (for metrics)
- needs_headless_review: True if possible SPA detected
"""

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import CrawlJobModel
from app.jobs.steps.base import BaseStep
from app.services.pattern_learner import PatternLearner
from app.services.url_utils import UrlProber
from app.services.web_crawler import WebCrawler, get_keywords_for_data_type

logger = structlog.get_logger()

# User agent for HTTP requests
USER_AGENT = "DNO-Data-Crawler/1.0 (Data Research Project; contact: abuse@kylehub.dev)"


class DiscoverStep(BaseStep):
    """Discover data source via BFS crawling or cached patterns."""
    
    label = "Discovering Source"
    description = "Finding data source via web crawling..."

    async def run(self, db: AsyncSession, job: CrawlJobModel) -> str:
        ctx = job.context or {}
        log = logger.bind(dno=ctx.get("dno_name"), data_type=job.data_type, year=job.year)
        
        # Initialize context fields
        ctx["pages_crawled"] = 0
        ctx["needs_headless_review"] = False
        ctx["discovered_via_pattern"] = None
        
        # =========================================================================
        # Strategy 1: Use cached file
        # =========================================================================
        if ctx.get("cached_file"):
            ctx["strategy"] = "use_cache"
            ctx["file_to_process"] = ctx["cached_file"]
            job.context = ctx
            await db.commit()
            log.info("Using cached file", path=ctx["cached_file"])
            return f"Strategy: USE_CACHE → {ctx['cached_file']}"
        
        # Need HTTP client for remaining strategies
        async with httpx.AsyncClient(
            timeout=15.0,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            trust_env=False,
        ) as client:
            prober = UrlProber(client)
            learner = PatternLearner()
            
            # Get allowed domains from DNO website
            allowed_domains = self._get_allowed_domains(ctx)
            
            # =====================================================================
            # Strategy 2: Try exact URL from profile (with year substitution)
            # =====================================================================
            if ctx.get("profile_url_pattern"):
                pattern = ctx["profile_url_pattern"]
                exact_url = pattern.replace("{year}", str(job.year))
                
                log.info("Trying exact URL from profile", url=exact_url[:80])
                
                is_valid, content_type, final_url, _ = await prober.probe(
                    exact_url,
                    allowed_domains=allowed_domains,
                )
                
                if is_valid and final_url:
                    ctx["strategy"] = "exact_url"
                    ctx["found_url"] = final_url
                    ctx["found_content_type"] = content_type
                    job.context = ctx
                    await db.commit()
                    return f"Strategy: EXACT_URL → {final_url}"
                else:
                    log.info("Exact URL failed, trying patterns")
            
            # =====================================================================
            # Strategy 3: Try learned path patterns
            # =====================================================================
            dno_website = ctx.get("dno_website")
            if dno_website:
                patterns = await learner.get_priority_paths(db, job.data_type, limit=5)
                
                for pattern in patterns:
                    expanded = learner.expand_pattern(pattern, job.year)
                    test_url = dno_website.rstrip("/") + expanded
                    
                    log.debug("Trying learned pattern", pattern=pattern, url=test_url[:80])
                    
                    is_valid, content_type, final_url, _ = await prober.probe(
                        test_url,
                        allowed_domains=allowed_domains,
                    )
                    
                    if is_valid and final_url:
                        ctx["strategy"] = "pattern_match"
                        ctx["found_url"] = final_url
                        ctx["found_content_type"] = content_type
                        ctx["discovered_via_pattern"] = pattern
                        job.context = ctx
                        await db.commit()
                        log.info("Found via learned pattern", pattern=pattern, url=final_url[:80])
                        return f"Strategy: PATTERN_MATCH → {pattern} → {final_url}"
                    else:
                        # Record pattern failure
                        await learner.record_failure(db, pattern)
            
            # =====================================================================
            # Strategy 4: Full BFS crawl
            # =====================================================================
            if not dno_website:
                raise ValueError(f"No website known for DNO {ctx.get('dno_name')}")
            
            log.info("Starting full BFS crawl", website=dno_website)
            
            crawler = WebCrawler(
                client=client,
                max_depth=3,
                max_pages=getattr(settings, "crawler_max_pages", 50),
                request_delay=getattr(settings, "crawler_delay", 0.5),
            )
            
            keywords = get_keywords_for_data_type(job.data_type)
            patterns = await learner.get_priority_paths(db, job.data_type, limit=10)
            
            results = await crawler.crawl(
                start_url=dno_website,
                target_keywords=keywords,
                priority_paths=patterns,
                target_year=job.year,
            )
            
            ctx["pages_crawled"] = len(results)
            
            # Find best document result
            for result in results:
                if result.is_document:
                    ctx["strategy"] = "bfs_crawl"
                    ctx["found_url"] = result.final_url
                    ctx["found_content_type"] = result.content_type
                    ctx["needs_headless_review"] = result.needs_headless
                    job.context = ctx
                    await db.commit()
                    log.info(
                        "Found document via BFS",
                        url=result.final_url[:80],
                        score=round(result.score, 2),
                        depth=result.depth,
                    )
                    return f"Strategy: BFS_CRAWL → {result.final_url} (score: {result.score:.1f})"
            
            # Check for pages that might contain download links
            for result in results:
                if not result.is_document and result.score > 20:
                    # This page might have links to documents
                    ctx["strategy"] = "bfs_crawl"
                    ctx["found_url"] = result.final_url
                    ctx["found_content_type"] = result.content_type
                    ctx["needs_headless_review"] = result.needs_headless
                    job.context = ctx
                    await db.commit()
                    log.info(
                        "Found promising page via BFS",
                        url=result.final_url[:80],
                        score=round(result.score, 2),
                        keywords=result.keywords_found,
                    )
                    return f"Strategy: BFS_CRAWL → {result.final_url} (landing page, score: {result.score:.1f})"
            
            # No results found
            job.context = ctx
            await db.commit()
            raise ValueError(
                f"No data source found for {ctx.get('dno_name')} after crawling "
                f"{ctx['pages_crawled']} pages"
            )
    
    def _get_allowed_domains(self, ctx: dict) -> set[str] | None:
        """Extract allowed domains from context."""
        website = ctx.get("dno_website")
        if not website:
            return None
        
        try:
            from urllib.parse import urlparse
            parsed = urlparse(website)
            if parsed.hostname:
                domain = parsed.hostname.lower()
                if domain.startswith("www."):
                    domain = domain[4:]
                return {domain, f"www.{domain}"}
        except Exception:
            pass
        
        return None
