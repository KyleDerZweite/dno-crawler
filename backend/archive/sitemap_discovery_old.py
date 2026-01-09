"""
Sitemap Discovery for DNO Crawler.

Efficient URL discovery using sitemap.xml:
1. Fetch sitemap (usually not behind bot protection)
2. Score URLs by keywords without fetching pages
3. Only fetch top candidates for verification

Falls back to BFS crawl if sitemap unavailable.
"""

import re
from dataclasses import dataclass
from urllib.parse import urlparse
from xml.etree import ElementTree

import httpx
import structlog

from app.services.web_crawler import NEGATIVE_KEYWORDS, get_keywords_for_data_type

logger = structlog.get_logger()


# Common sitemap locations
SITEMAP_PATHS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap/sitemap.xml",
    "/googlesitemap",  # Used by RheinNetz
    "/sitemaps/sitemap.xml",
]


@dataclass
class SitemapUrl:
    """A URL from a sitemap with scoring info."""
    url: str
    lastmod: str | None = None
    priority: float = 0.5
    score: float = 0.0
    keywords_found: list[str] = None
    has_year: bool = False
    file_type: str | None = None

    def __post_init__(self):
        self.keywords_found = self.keywords_found or []


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


def score_sitemap_urls(
    urls: list[str],
    data_type: str,
    target_year: int | None = None,
) -> list[SitemapUrl]:
    """
    Score URLs from sitemap based on keywords and data type.
    
    This is very fast - no HTTP requests, just string matching.
    
    Args:
        urls: List of URLs from sitemap
        data_type: "netzentgelte" or "hlzf"
        target_year: Optional target year
        
    Returns:
        List of SitemapUrl objects, sorted by score (highest first)
    """
    keywords = get_keywords_for_data_type(data_type)
    neg_keywords = NEGATIVE_KEYWORDS.get(data_type, [])

    results = []

    for url in urls:
        url_lower = url.lower()
        score = 0.0
        keywords_found = []

        # Detect file type
        file_type = None
        if ".pdf" in url_lower or ".pdfx" in url_lower:
            file_type = "pdf"
            score += 20
        elif ".xlsx" in url_lower:
            file_type = "xlsx"
            score += 15
        elif ".xls" in url_lower:
            file_type = "xls"
            score += 15

        # Positive keywords
        for kw in keywords:
            if kw.lower() in url_lower:
                score += 15
                keywords_found.append(kw)

        # Negative keywords
        for neg_kw, penalty in neg_keywords:
            if neg_kw.lower() in url_lower:
                score += penalty  # penalty is negative

        # Year bonus
        has_year = False
        if target_year and str(target_year) in url:
            score += 25
            has_year = True

        # Skip very low scores (irrelevant URLs)
        if score <= 0 and not file_type:
            continue

        results.append(SitemapUrl(
            url=url,
            score=score,
            keywords_found=keywords_found,
            has_year=has_year,
            file_type=file_type,
        ))

    # Sort by score
    results.sort(key=lambda x: x.score, reverse=True)

    return results


async def discover_via_sitemap(
    client: httpx.AsyncClient,
    base_url: str,
    data_type: str,
    target_year: int | None = None,
    max_candidates: int = 20,
) -> tuple[list[SitemapUrl], bool]:
    """
    Discover data files using sitemap.
    
    Much faster than BFS - only needs 1 HTTP request for sitemap,
    then scores URLs without fetching them.
    
    Args:
        client: HTTP client
        base_url: Site base URL
        data_type: "netzentgelte" or "hlzf"
        target_year: Optional target year
        max_candidates: Max candidates to return
        
    Returns:
        (scored_urls, sitemap_found) - list of candidates and whether sitemap was found
    """
    log = logger.bind(component="SitemapDiscovery")

    # Try to get sitemap
    sitemap_content = await fetch_sitemap(client, base_url)

    if not sitemap_content:
        return [], False

    # Parse URLs
    urls = parse_sitemap(sitemap_content)
    log.info("Parsed sitemap", url_count=len(urls))

    if not urls:
        return [], True  # Sitemap found but empty

    # Score URLs
    scored = score_sitemap_urls(urls, data_type, target_year)
    log.info("Scored URLs",
             total=len(scored),
             high_score=len([u for u in scored if u.score > 50]))

    return scored[:max_candidates], True
