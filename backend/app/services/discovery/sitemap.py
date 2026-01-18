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


def parse_sitemap(xml_content: str) -> tuple[list[str], list[str]]:
    """
    Parse URLs from sitemap XML.

    Handles both regular sitemaps and sitemap indexes.

    Args:
        xml_content: Raw sitemap XML

    Returns:
        Tuple of (urls, nested_sitemap_urls)
        - urls: Direct URLs found in this sitemap
        - nested_sitemap_urls: URLs of nested sitemaps (for sitemap indexes)
    """
    urls = []
    nested_sitemaps = []

    try:
        # Handle namespace
        namespaces = {
            "sm": "http://www.sitemaps.org/schemas/sitemap/0.9"
        }

        root = ElementTree.fromstring(xml_content)

        # Check for sitemap index (contains other sitemaps)
        for sitemap_elem in root.findall(".//sm:sitemap", namespaces):
            loc = sitemap_elem.find("sm:loc", namespaces)
            if loc is not None and loc.text:
                nested_sitemaps.append(loc.text)

        # Also try without namespace
        if not nested_sitemaps:
            for sitemap in root.iter("sitemap"):
                loc = sitemap.find("loc")
                if loc is not None and loc.text:
                    nested_sitemaps.append(loc.text)

        # Extract URLs from urlset
        for url_elem in root.findall(".//sm:url", namespaces):
            loc = url_elem.find("sm:loc", namespaces)
            if loc is not None and loc.text:
                urls.append(loc.text)

        # Also try without namespace (some sitemaps don't use it)
        if not urls:
            for loc in root.iter("loc"):
                # Skip if this is inside a sitemap element (index)
                if loc.text and loc.text not in nested_sitemaps:
                    urls.append(loc.text)

    except ElementTree.ParseError:
        # Try regex fallback for malformed XML
        pattern = r'<loc>([^<]+)</loc>'
        urls = re.findall(pattern, xml_content)

    return urls, nested_sitemaps


# Language path patterns to filter/prioritize
PREFERRED_LANG = "/de/"
FALLBACK_LANG = "/en/"
EXCLUDE_LANGS = ["/es/", "/it/", "/fr/", "/nl/", "/pt/", "/ru/", "/cn/", "/zh/", "/ja/", "/ko/", "/pl/", "/tr/"]


def filter_sitemaps_by_language(sitemap_urls: list[str]) -> list[str]:
    """
    Filter sitemap URLs to prefer German, fallback to English, exclude others.
    
    Priority:
    1. German (/de/) sitemaps
    2. English (/en/) sitemaps (if no German)
    3. Language-neutral sitemaps (no language path)
    """
    german_sitemaps = []
    english_sitemaps = []
    neutral_sitemaps = []
    
    for url in sitemap_urls:
        url_lower = url.lower()
        
        # Check for excluded languages first
        if any(lang in url_lower for lang in EXCLUDE_LANGS):
            continue
        
        # Categorize by language
        if PREFERRED_LANG in url_lower:
            german_sitemaps.append(url)
        elif FALLBACK_LANG in url_lower:
            english_sitemaps.append(url)
        else:
            # No language path - neutral
            neutral_sitemaps.append(url)
    
    # Return in priority order: German first, then English, then neutral
    if german_sitemaps:
        return german_sitemaps + neutral_sitemaps
    elif english_sitemaps:
        return english_sitemaps + neutral_sitemaps
    else:
        return neutral_sitemaps


async def fetch_and_parse_sitemap_recursive(
    client: httpx.AsyncClient,
    sitemap_url: str,
    max_depth: int = 2,
    _current_depth: int = 0,
) -> list[str]:
    """
    Recursively fetch and parse sitemaps, following sitemap indexes.

    Args:
        client: HTTP client
        sitemap_url: URL of sitemap to fetch
        max_depth: Maximum recursion depth for nested sitemaps
        _current_depth: Internal tracker for current depth

    Returns:
        List of all URLs found across all sitemaps
    """
    log = logger.bind(component="SitemapFetcher")
    all_urls = []

    if _current_depth >= max_depth:
        log.debug("Max sitemap depth reached", url=sitemap_url[:60], depth=_current_depth)
        return all_urls

    try:
        response = await client.get(sitemap_url, timeout=10.0, follow_redirects=True)

        if response.status_code != 200:
            log.debug("Sitemap fetch failed", url=sitemap_url[:60], status=response.status_code)
            return all_urls

        content = response.text

        # Verify it's XML
        if not (content.strip().startswith("<?xml") or "<urlset" in content[:500] or "<sitemapindex" in content[:500]):
            log.debug("Not valid sitemap XML", url=sitemap_url[:60])
            return all_urls

        urls, nested_sitemaps = parse_sitemap(content)

        log.debug(
            "Parsed sitemap",
            url=sitemap_url[:60],
            urls_found=len(urls),
            nested_sitemaps=len(nested_sitemaps),
            depth=_current_depth,
        )

        # Add direct URLs
        all_urls.extend(urls)

        # Recursively fetch nested sitemaps
        # Filter by language preference (German first, English fallback)
        if nested_sitemaps:
            filtered_sitemaps = filter_sitemaps_by_language(nested_sitemaps)
            log.info(
                "Following nested sitemaps",
                total=len(nested_sitemaps),
                filtered=len(filtered_sitemaps),
                depth=_current_depth,
            )
            # Fetch filtered nested sitemaps
            for nested_url in filtered_sitemaps:
                nested_urls = await fetch_and_parse_sitemap_recursive(
                    client, nested_url, max_depth, _current_depth + 1
                )
                all_urls.extend(nested_urls)

    except Exception as e:
        log.debug("Sitemap fetch/parse failed", url=sitemap_url[:60], error=str(e))

    return all_urls


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

    # Parse URLs from sitemap (handles sitemap indexes recursively)
    urls, nested_sitemaps = parse_sitemap(sitemap_content)
    
    # If this is a sitemap index, recursively fetch nested sitemaps
    if nested_sitemaps and not urls:
        log.info("Sitemap is an index, fetching nested sitemaps", count=len(nested_sitemaps))
        # Get the sitemap URL we're working with
        parsed = urlparse(base_url)
        site_base = f"{parsed.scheme}://{parsed.netloc}"
        
        for nested_url in nested_sitemaps:
            nested_urls = await fetch_and_parse_sitemap_recursive(client, nested_url, max_depth=2)
            urls.extend(nested_urls)
    
    result.sitemap_urls_checked = len(urls)
    log.info("Parsed sitemap", url_count=len(urls), nested_sitemaps_found=len(nested_sitemaps))

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
