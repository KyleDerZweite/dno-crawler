"""
Discovery Module - Sitemap Discovery Strategy.

Uses sitemap.xml for efficient URL discovery:
1. Parse stored sitemap URLs from DNO record (or fetch fresh)
2. Score all URLs by keywords (no HTTP requests needed)
3. Return top candidates sorted by relevance
"""

import re
from urllib.parse import urlparse
from xml.etree import ElementTree

import httpx
import structlog

from app.services.discovery.base import (
    DiscoveredDocument,
    DiscoveryResult,
    DiscoveryStrategy,
    FileType,
)
from app.services.discovery.scorer import detect_file_type, score_url

logger = structlog.get_logger()


# Common sitemap locations
SITEMAP_PATHS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap/sitemap.xml",
    "/googlesitemap",  # Used by RheinNetz
    "/sitemaps/sitemap.xml",
]


async def fetch_sitemap(
    client: httpx.AsyncClient,
    base_url: str,
) -> str | None:
    """
    Try to fetch sitemap, first checking robots.txt for location.

    Strategy:
    1. Fetch robots.txt and look for Sitemap: directive
    2. If found, use that URL
    3. If not, try common sitemap paths

    Args:
        client: HTTP client
        base_url: Site base URL (e.g., https://www.example.de)

    Returns:
        Sitemap XML content, or None if not found
    """
    log = logger.bind(component="SitemapFetcher")

    parsed = urlparse(base_url)
    site_base = f"{parsed.scheme}://{parsed.netloc}"

    sitemap_urls = []

    # Step 1: Check robots.txt for Sitemap: directive
    try:
        robots_url = f"{site_base}/robots.txt"
        response = await client.get(robots_url, timeout=10.0, follow_redirects=True)

        if response.status_code == 200:
            robots_content = response.text
            # Extract Sitemap: URLs
            for line in robots_content.splitlines():
                line = line.strip()
                if line.lower().startswith("sitemap:"):
                    sitemap_url = line.split(":", 1)[1].strip()
                    sitemap_urls.append(sitemap_url)
                    log.info("Found sitemap in robots.txt", url=sitemap_url)

    except Exception as e:
        log.debug("Failed to fetch robots.txt", error=str(e))

    # Step 2: Add common fallback paths
    for path in SITEMAP_PATHS:
        sitemap_urls.append(site_base + path)

    # Step 3: Try each sitemap URL
    for url in sitemap_urls:
        try:
            response = await client.get(url, timeout=10.0, follow_redirects=True)

            # Check if it's valid XML (not a Cloudflare challenge)
            if response.status_code == 200:
                content = response.text
                if content.strip().startswith("<?xml") or "<urlset" in content[:500] or "<loc>" in content[:1000]:
                    log.info("Found sitemap", url=url)
                    return content

        except Exception as e:
            log.debug("Sitemap fetch failed", url=url[:60], error=str(e))
            continue

    log.info("No sitemap found", base_url=base_url)
    return None


def parse_sitemap(xml_content: str) -> list[str]:
    """
    Parse URLs from sitemap XML.

    Handles both regular sitemaps and sitemap indexes.

    Args:
        xml_content: Raw sitemap XML

    Returns:
        List of URLs found
    """
    urls = []

    try:
        # Handle namespace
        namespaces = {
            "sm": "http://www.sitemaps.org/schemas/sitemap/0.9"
        }

        root = ElementTree.fromstring(xml_content)

        # Check for sitemap index (contains other sitemaps)
        sitemap_refs = root.findall(".//sm:sitemap/sm:loc", namespaces)
        if sitemap_refs:
            # This is an index - would need to fetch referenced sitemaps
            # For now, just log and continue
            pass

        # Extract URLs from urlset
        for url_elem in root.findall(".//sm:url", namespaces):
            loc = url_elem.find("sm:loc", namespaces)
            if loc is not None and loc.text:
                urls.append(loc.text)

        # Also try without namespace (some sitemaps don't use it)
        if not urls:
            for loc in root.iter("loc"):
                if loc.text:
                    urls.append(loc.text)

    except ElementTree.ParseError:
        # Try regex fallback for malformed XML
        pattern = r'<loc>([^<]+)</loc>'
        urls = re.findall(pattern, xml_content)

    return urls


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
