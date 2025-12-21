"""
Step 02: Search

Executes external search to find data sources.

What it does:
- Skip if strategy is "use_cache"
- If strategy is "try_pattern", first check if pattern URL exists
- If pattern fails or strategy is "search", execute DuckDuckGo queries
- Validate found URLs for safety (SSRF protection) and content type

Output stored in job.context:
- found_url: Final URL after redirects
- successful_query: Which query found it (for learning)
"""

import asyncio

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CrawlJobModel
from app.jobs.steps.base import BaseStep
from app.services.search_engine import DdgsProvider, UrlProber

# Delay between DuckDuckGo queries to avoid rate limiting
SEARCH_DELAY_SECONDS = 1.0

logger = structlog.get_logger()

# User agent for HTTP requests (identifies the bot to webmasters)
USER_AGENT = "DNO-Data-Crawler/1.0 (Data Research Project; contact: abuse@kylehub.dev)"


class SearchStep(BaseStep):
    label = "Searching"
    description = "Searching for data sources via DuckDuckGo..."

    async def run(self, db: AsyncSession, job: CrawlJobModel) -> str:
        ctx = job.context or {}
        strategy = ctx.get("strategy", "search")
        
        # Skip if using cache
        if strategy == "use_cache":
            return "Skipped → Using cached file"
        
        log = logger.bind(dno=ctx.get("dno_name"), data_type=job.data_type)
        
        # Extract allowed domains from DNO website (if known)
        allowed_domains = self._get_allowed_domains(ctx)
        
        # Reuse single client for all requests (P1 improvement)
        async with httpx.AsyncClient(
            timeout=10.0,
            headers={"User-Agent": USER_AGENT},
            trust_env=False,  # Don't use system proxy (P1 privacy)
        ) as client:
            prober = UrlProber(client)
            provider = DdgsProvider(backend="duckduckgo")
            
            # Try pattern first
            if strategy == "try_pattern":
                pattern_url = ctx.get("pattern_url")
                if pattern_url:
                    log.info("Trying pattern URL", url=pattern_url[:80])
                    is_valid, content_type, final_url = await prober.probe(
                        pattern_url, 
                        allowed_domains=allowed_domains
                    )
                    if is_valid and final_url:
                        ctx["found_url"] = final_url
                        ctx["found_content_type"] = content_type
                        ctx["successful_query"] = "pattern"
                        job.context = ctx
                        await db.commit()
                        return f"Pattern worked: {final_url}"
                    else:
                        log.info("Pattern URL failed, falling back to search")
                
                ctx["strategy"] = "search"
            
            # Execute search queries
            queries = ctx.get("search_queries", [])
            if not queries:
                raise ValueError("No search queries configured")
            
            for idx, query in enumerate(queries):
                # Add delay between searches to avoid rate limiting
                if idx > 0:
                    await asyncio.sleep(SEARCH_DELAY_SECONDS)
                
                log.info("Executing search query", query=query[:60])
                
                try:
                    results = await provider.search(query, max_results=10)
                except ValueError as e:
                    log.warning("Search query failed", error=str(e))
                    continue
                
                for result in results:
                    # Quick relevance filter
                    if not self._is_relevant(result.url, job.data_type):
                        continue
                    
                    # Full URL probe with safety checks
                    is_valid, content_type, final_url = await prober.probe(
                        result.url,
                        allowed_domains=allowed_domains
                    )
                    
                    if not is_valid or not final_url:
                        continue
                    
                    # Additional content-type verification for direct files
                    if result.url.lower().endswith((".pdf", ".pdfx")):
                        if content_type and "pdf" not in content_type.lower():
                            log.debug("PDF URL has wrong content-type", 
                                     url=result.url[:60], content_type=content_type)
                            continue
                    
                    # Success!
                    ctx["found_url"] = final_url
                    ctx["found_content_type"] = content_type
                    ctx["successful_query"] = query
                    job.context = ctx
                    await db.commit()
                    
                    log.info("Found valid source", url=final_url[:80])
                    return f"Found: {final_url}"
        
        # No results found after all queries
        raise ValueError(f"No data source found for {ctx.get('dno_name')} after exhausting all queries")
    
    def _get_allowed_domains(self, ctx: dict) -> set[str] | None:
        """Extract allowed domains from context.
        
        If DNO website is known, restrict searches to that domain
        and common subdomains. Otherwise return None (allow all).
        """
        website = ctx.get("dno_website")
        if not website:
            return None
        
        try:
            from urllib.parse import urlparse
            parsed = urlparse(website)
            if parsed.hostname:
                # Allow the domain and any subdomains
                domain = parsed.hostname.lower()
                # Strip www. prefix for flexibility
                if domain.startswith("www."):
                    domain = domain[4:]
                return {domain, f"www.{domain}"}
        except Exception:
            pass
        
        return None
    
    def _is_relevant(self, url: str, data_type: str) -> bool:
        """Filter URLs likely to be data sources (quick heuristic).
        
        This is a fast pre-filter before the full probe.
        IMPORTANT: Also rejects URLs that clearly contain the WRONG data type.
        """
        url_lower = url.lower()
        
        # Obvious non-documents
        skip_patterns = [
            "/blog/", "/news/", "/career/", "/jobs/", 
            "/contact", "/impressum", "/datenschutz",
            "twitter.com", "facebook.com", "linkedin.com", "youtube.com",
        ]
        if any(pattern in url_lower for pattern in skip_patterns):
            return False
        
        # Keywords for each data type
        netzentgelte_keywords = [
            "netzentgelte", "preisblatt", "netzzugang", 
            "netznutzung", "entgelt", "tarif"
        ]
        hlzf_keywords = [
            "hlzf", "hochlast", "hochlastzeitfenster", 
            "stromnev", "zeitfenster"
        ]
        
        # CRITICAL: Reject URLs that clearly contain the WRONG data type
        # This prevents HLZF jobs from picking up Netzentgelte files
        if data_type == "hlzf":
            # If searching for HLZF, reject URLs with Netzentgelte keywords
            if any(kw in url_lower for kw in netzentgelte_keywords):
                # Exception: If URL also has HLZF keywords, it might be a combined doc
                if not any(kw in url_lower for kw in hlzf_keywords):
                    return False
        elif data_type == "netzentgelte":
            # If searching for Netzentgelte, reject URLs with HLZF-only keywords
            if any(kw in url_lower for kw in hlzf_keywords):
                if not any(kw in url_lower for kw in netzentgelte_keywords):
                    return False
        
        # Direct file links are best
        if any(url_lower.endswith(ext) for ext in [".pdf", ".pdfx", ".xlsx", ".xls", ".docx"]):
            return True
        
        # Check for correct data-related keywords in URL (positive signal)
        target_keywords = hlzf_keywords if data_type == "hlzf" else netzentgelte_keywords
        if any(kw in url_lower for kw in target_keywords):
            return True
        
        # For generic URLs on a known DNO domain, still allow (probe will verify)
        return True
