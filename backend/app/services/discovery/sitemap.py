"""
Discovery Module - Sitemap Discovery Strategy.

Uses sitemap.xml for efficient URL discovery:
1. Parse stored sitemap URLs from DNO record (or fetch fresh)
2. Score all URLs by keywords (no HTTP requests needed)
3. Return top candidates sorted by relevance
"""

from dataclasses import dataclass
import httpx
import structlog

from app.services.discovery.base import (
    DiscoveredDocument,
    DiscoveryResult,
    DiscoveryStrategy,
    FileType,
)
from app.services.discovery.scorer import detect_file_type, score_url
from app.services.sitemap_discovery import (
    fetch_sitemap,
    parse_sitemap,
)

logger = structlog.get_logger()


async def discover_via_sitemap(
    client: httpx.AsyncClient,
    base_url: str,
    data_type: str,
    target_year: int | None = None,
    sitemap_content: str | None = None,
    max_candidates: int = 50,
) -> DiscoveryResult:
    """
    Discover data files using sitemap.
    
    Much faster than BFS - only needs 1 HTTP request for sitemap,
    then scores URLs without fetching them.
    
    Args:
        client: HTTP client
        base_url: Site base URL
        data_type: "netzentgelte" or "hlzf"
        target_year: Optional target year
        sitemap_content: Pre-fetched sitemap content (or None to fetch fresh)
        max_candidates: Max candidates to return
    
    Returns:
        DiscoveryResult with scored candidates
    """
    log = logger.bind(component="SitemapDiscovery", base_url=base_url[:40])
    
    result = DiscoveryResult(
        start_url=base_url,
        data_type=data_type,
        target_year=target_year,
        strategy=DiscoveryStrategy.SITEMAP,
    )
    
    # Fetch sitemap if not provided
    if not sitemap_content:
        sitemap_content = await fetch_sitemap(client, base_url)
    
    if not sitemap_content:
        log.info("No sitemap available")
        result.errors.append("No sitemap found")
        return result
    
    # Parse URLs from sitemap
    urls = parse_sitemap(sitemap_content)
    result.sitemap_urls_checked = len(urls)
    log.info("Parsed sitemap", url_count=len(urls))
    
    if not urls:
        result.errors.append("Sitemap empty or unparseable")
        return result
    
    # Score each URL
    candidates = []
    
    for url in urls:
        score, keywords, has_year = score_url(url, data_type, target_year)
        file_type = detect_file_type(url)
        
        # Skip very low scores (unless it's a file)
        if score <= 0 and file_type == FileType.UNKNOWN:
            continue
        
        candidates.append(DiscoveredDocument(
            url=url,
            score=score,
            file_type=file_type,
            found_on_page="(sitemap)",
            keywords_found=keywords,
            has_target_year=has_year,
        ))
    
    # Sort by score
    candidates.sort(key=lambda d: d.score, reverse=True)
    
    # Take top candidates
    result.documents = candidates[:max_candidates]
    
    log.info(
        "Sitemap discovery complete",
        total_candidates=len(candidates),
        returned=len(result.documents),
        top_score=result.documents[0].score if result.documents else 0,
    )
    
    return result
