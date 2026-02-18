"""
Step 01: Discover (Data-Type Agnostic)

Combined discovery step that finds candidate URLs for BOTH data types.
No ContentVerifier gate: collects URLs purely by URL scoring.

Strategy order:
1. Cached files -- note existing files, still proceed for fresh data
2. Exact URLs from profiles -- try patterns for both netzentgelte and hlzf
3. Sitemap discovery -- combined keywords, identify parent pages
4. Learned patterns -- try top patterns from PatternLearner
5. BFS crawl -- start from sitemap-identified parent pages or root

Output stored in job.context:
- candidate_urls: list of {url, score, source, file_type}
- pages_crawled: number of pages crawled (for metrics)
- parent_pages: sitemap-identified parent pages used as BFS seeds
"""

import asyncio
from urllib.parse import urlparse

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import CrawlJobModel, DNOModel
from app.jobs.steps.base import BaseStep, StepError
from app.services.discovery import DiscoveryManager
from app.services.pattern_learner import PatternLearner
from app.services.url_utils import DOCUMENT_EXTENSIONS, UrlProber
from app.services.user_agent import build_user_agent, require_contact_for_bfs
from app.services.web_crawler import WebCrawler, get_keywords_for_data_type

logger = structlog.get_logger()

# Maximum candidates to collect across all strategies
MAX_CANDIDATES = 30

# Timeout for BFS crawl (5 minutes)
BFS_CRAWL_TIMEOUT_SECONDS = 300

# Parent page keywords for identifying BFS seed pages from sitemap
_PARENT_PAGE_KEYWORDS = [
    "downloads",
    "veroeffentlichung",
    "dokumente",
    "service",
    "netz",
    "netzzugang",
    "publikationen",
]


class DiscoverStep(BaseStep):
    """Discover candidate URLs via data-type agnostic crawling."""

    label = "Discovering Sources"
    description = "Finding candidate URLs for all data types..."

    async def run(self, db: AsyncSession, job: CrawlJobModel) -> str:
        ctx = job.context or {}
        log = logger.bind(dno=ctx.get("dno_name"), year=job.year)

        # Initialize context fields
        ctx["pages_crawled"] = 0
        ctx["candidate_urls"] = []
        ctx["parent_pages"] = []

        # Read crawl pass settings (for deepening support)
        max_depth = ctx.get("max_depth", 3)
        max_pages = ctx.get("max_pages", getattr(settings, "crawler_max_pages", 50))
        crawl_pass = ctx.get("crawl_pass", 1)

        dno_website = ctx.get("dno_website")
        if not dno_website:
            raise StepError(f"No website known for DNO {ctx.get('dno_name')}")

        # Load DNO from DB for sitemap cache
        dno = await db.get(DNOModel, job.dno_id)

        # Check sitemap cache with TTL (120 days)
        cached_sitemap_urls = None
        if dno and dno.sitemap_parsed_urls and dno.sitemap_fetched_at:
            from datetime import UTC, datetime, timedelta

            sitemap_ttl_days = 120
            cache_age = datetime.now(UTC) - dno.sitemap_fetched_at.replace(tzinfo=UTC)
            if cache_age < timedelta(days=sitemap_ttl_days):
                cached_sitemap_urls = dno.sitemap_parsed_urls
                log.info("using_cached_sitemap", count=len(cached_sitemap_urls))

        # Build HTTP client
        initiator_ip = ctx.get("initiator_ip")
        user_agent = build_user_agent(initiator_ip)

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0),
            headers={"User-Agent": user_agent},
            follow_redirects=True,
            trust_env=False,
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
                keepalive_expiry=30.0,
            ),
        ) as client:
            prober = UrlProber(client)
            learner = PatternLearner()
            allowed_domains = self._get_allowed_domains(ctx)
            candidates: list[dict] = []
            seen_urls: set[str] = set()

            def _add_candidate(url: str, score: float, source: str, file_type: str = "unknown"):
                """Add a candidate URL if not already seen."""
                if url in seen_urls or len(candidates) >= MAX_CANDIDATES:
                    return
                seen_urls.add(url)
                candidates.append(
                    {
                        "url": url,
                        "score": score,
                        "source": source,
                        "file_type": file_type,
                    }
                )

            # =================================================================
            # Strategy 1: Note cached files (don't skip, we want fresh data too)
            # =================================================================
            cached_files = ctx.get("cached_files", {})
            if cached_files:
                log.info("cached_files_noted", types=list(cached_files.keys()))

            # =================================================================
            # Strategy 2: Exact URLs from profiles (both types)
            # =================================================================
            profiles = ctx.get("profiles", {})
            for dt, profile in profiles.items():
                url_pattern = profile.get("url_pattern")
                if not url_pattern:
                    continue

                exact_url = url_pattern.replace("{year}", str(job.year))
                log.debug("trying_profile_url", data_type=dt, url=exact_url[:80])

                is_valid, _ct, final_url, _ = await prober.probe(
                    exact_url, allowed_domains=allowed_domains
                )
                if is_valid and final_url:
                    ft = self._detect_file_type(final_url)
                    _add_candidate(final_url, 80.0, f"profile_{dt}", ft)

            # =================================================================
            # Strategy 3: Sitemap discovery (combined keywords)
            # =================================================================
            discovery = DiscoveryManager(client)
            discovery_result = await discovery.discover(
                base_url=dno_website,
                data_type="all",
                target_year=job.year,
                sitemap_urls=cached_sitemap_urls,
                max_candidates=20,
            )

            parent_pages = []
            if discovery_result.documents:
                log.info(
                    "sitemap_candidates",
                    count=len(discovery_result.documents),
                    strategy=discovery_result.strategy.value,
                )
                for doc in discovery_result.documents:
                    ft = self._detect_file_type(doc.url)
                    _add_candidate(doc.url, doc.score, "sitemap", ft)

                    # Identify parent pages for BFS seeding
                    url_lower = doc.url.lower()
                    if ft in ("html", "unknown") and any(
                        kw in url_lower for kw in _PARENT_PAGE_KEYWORDS
                    ):
                        parent_pages.append(doc.url)

            ctx["parent_pages"] = parent_pages[:5]

            # =================================================================
            # Strategy 4: Learned path patterns (both types)
            # =================================================================
            for dt in ("netzentgelte", "hlzf"):
                patterns = await learner.get_priority_paths(db, dt, limit=3)
                for pattern in patterns:
                    expanded = learner.expand_pattern(pattern, job.year)
                    test_url = dno_website.rstrip("/") + expanded

                    is_valid, _ct, final_url, _ = await prober.probe(
                        test_url, allowed_domains=allowed_domains
                    )
                    if is_valid and final_url:
                        ft = self._detect_file_type(final_url)
                        _add_candidate(final_url, 60.0, f"pattern_{dt}", ft)

            # =================================================================
            # Strategy 5: BFS crawl (start from parent pages or root)
            # =================================================================
            if len(candidates) < MAX_CANDIDATES:
                bfs_user_agent = require_contact_for_bfs(initiator_ip)

                crawler = WebCrawler(
                    client=client,
                    user_agent=bfs_user_agent,
                    max_depth=max_depth,
                    max_pages=max_pages,
                    request_delay=getattr(settings, "crawler_delay", 0.5),
                )

                keywords = get_keywords_for_data_type("all")

                # Combine learned patterns for both types for BFS priority
                all_patterns = []
                for dt in ("netzentgelte", "hlzf"):
                    all_patterns.extend(await learner.get_priority_paths(db, dt, limit=5))

                # Use parent pages as BFS start points, fall back to root
                start_url = parent_pages[0] if parent_pages else dno_website

                try:
                    results = await asyncio.wait_for(
                        crawler.crawl(
                            start_url=start_url,
                            target_keywords=keywords,
                            priority_paths=all_patterns,
                            target_year=job.year,
                            data_type="all",
                        ),
                        timeout=BFS_CRAWL_TIMEOUT_SECONDS,
                    )
                except TimeoutError:
                    log.error(
                        "bfs_crawl_timeout",
                        timeout=BFS_CRAWL_TIMEOUT_SECONDS,
                        website=dno_website,
                    )
                    results = []

                ctx["pages_crawled"] = len(results)

                # Add document results as candidates
                for result in results:
                    if result.is_document:
                        ft = self._detect_file_type(result.final_url)
                        _add_candidate(result.final_url, result.score, "bfs_crawl", ft)
                    elif result.score > 20:
                        # High-scoring HTML pages might contain embedded data
                        _add_candidate(result.final_url, result.score, "bfs_crawl", "html")

            # Sort candidates by score descending
            candidates.sort(key=lambda c: c["score"], reverse=True)
            candidates = candidates[:MAX_CANDIDATES]

            ctx["candidate_urls"] = candidates
            job.context = ctx
            await db.commit()

            if not candidates:
                raise StepError(
                    f"No candidate URLs found for {ctx.get('dno_name')} "
                    f"(pass {crawl_pass}, crawled {ctx['pages_crawled']} pages)"
                )

            doc_count = sum(1 for c in candidates if c["file_type"] not in ("html", "unknown"))
            return (
                f"Found {len(candidates)} candidates "
                f"({doc_count} documents, {len(candidates) - doc_count} pages, "
                f"pass {crawl_pass})"
            )

    def _get_allowed_domains(self, ctx: dict) -> set[str] | None:
        """Extract allowed domains from context."""
        website = ctx.get("dno_website")
        if not website:
            return None
        try:
            parsed = urlparse(website)
            if parsed.hostname:
                domain = parsed.hostname.lower()
                if domain.startswith("www."):
                    domain = domain[4:]
                return {domain, f"www.{domain}"}
        except Exception:
            pass
        return None

    def _detect_file_type(self, url: str) -> str:
        """Detect file type from URL extension."""
        url_lower = url.lower().split("?")[0]
        if url_lower.endswith(".pdf"):
            return "pdf"
        elif url_lower.endswith((".xlsx", ".xls")):
            return "xlsx"
        elif url_lower.endswith((".docx", ".doc")):
            return "docx"
        elif url_lower.endswith((".html", ".htm")):
            return "html"
        elif any(url_lower.endswith(ext) for ext in DOCUMENT_EXTENSIONS):
            return "document"
        return "unknown"
