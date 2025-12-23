"""
BFS Web Crawler for DNO Crawler.

Crawls DNO websites using breadth-first search to discover data sources.
Features:
- robots.txt compliance via urllib.robotparser
- HEAD-first probing (detect PDFs without downloading)
- URL normalization for deduplication
- Priority queue based on keyword relevance
- Depth-limited traversal
- JS/SPA detection fallback
"""

import asyncio
from dataclasses import dataclass, field
from heapq import heappop, heappush
from urllib.parse import urljoin, urlparse

import httpx
import structlog
from bs4 import BeautifulSoup

from app.services.url_utils import (
    DOCUMENT_EXTENSIONS,
    RobotsChecker,
    UrlProber,
    extract_domain,
    normalize_url,
)

logger = structlog.get_logger()


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class CrawlResult:
    """Result of crawling a page."""
    url: str
    final_url: str  # After redirects
    content_type: str
    depth: int
    score: float
    title: str | None = None
    keywords_found: list[str] = field(default_factory=list)
    is_document: bool = False  # True if PDF/XLSX/etc
    content_length: int | None = None
    needs_headless: bool = False  # Possible SPA detected


@dataclass(order=True)
class QueueItem:
    """Priority queue item for BFS crawl."""
    priority: float  # Lower = higher priority (negative score)
    url: str = field(compare=False)
    depth: int = field(compare=False)
    parent_url: str | None = field(compare=False, default=None)


# =============================================================================
# Keywords and Filters
# =============================================================================


# Keywords indicating relevant pages for each data type
KEYWORDS = {
    "netzentgelte": [
        "netzentgelte", "preisblatt", "preisblaetter", "netzzugang", 
        "netznutzung", "entgelt", "tarif", "veroeffentlichung",
        "strom", "netznutzungsentgelte", "arbeitspreis", "leistungspreis",
    ],
    "hlzf": [
        "hlzf", "hochlast", "hochlastzeitfenster", "zeitfenster",
        "stromnev", "§19", "veroeffentlichung",
    ],
    "both": [
        "downloads", "dokumente", "service", "veroeffentlichung",
        "netzbetreiber", "netz",
    ],
}

# Irrelevant path segments to skip
IRRELEVANT_PATHS = {
    "/karriere/", "/jobs/", "/career/", "/stellenangebote/",
    "/kontakt/", "/contact/", "/impressum/", "/imprint/",
    "/datenschutz/", "/privacy/", "/agb/", "/terms/",
    "/presse/", "/press/", "/news/", "/blog/", "/aktuelles/",
    "/login/", "/register/", "/anmelden/", "/registrieren/",
    "/warenkorb/", "/cart/", "/checkout/",
    "/suche/", "/search/", "/sitemap/",
}

# External domains to skip
SKIP_DOMAINS = {
    "facebook.com", "twitter.com", "linkedin.com", "youtube.com",
    "instagram.com", "xing.com", "kununu.com", "google.com",
}


# =============================================================================
# Web Crawler
# =============================================================================


class WebCrawler:
    """BFS web crawler with safety features.
    
    Crawls websites breadth-first, prioritizing URLs likely to contain
    target data based on keyword matching and learned patterns.
    """
    
    USER_AGENT = "DNO-Data-Crawler/1.0 (Data Research Project; contact: abuse@kylehub.dev)"
    
    def __init__(
        self,
        client: httpx.AsyncClient,
        max_depth: int = 3,
        max_pages: int = 50,
        request_delay: float = 0.5,
        timeout: float = 10.0,
    ):
        """Initialize crawler.
        
        Args:
            client: httpx AsyncClient for requests
            max_depth: Maximum crawl depth from start URL
            max_pages: Maximum pages to crawl per session
            request_delay: Delay between requests (politeness)
            timeout: Request timeout in seconds
        """
        self.client = client
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.request_delay = request_delay
        self.timeout = timeout
        
        self.prober = UrlProber(client)
        self.robots = RobotsChecker(client)
        self.log = logger.bind(component="WebCrawler")
    
    async def crawl(
        self,
        start_url: str,
        target_keywords: list[str],
        priority_paths: list[str] | None = None,
        target_year: int | None = None,
    ) -> list[CrawlResult]:
        """BFS crawl from start_url, prioritizing relevant URLs.
        
        Args:
            start_url: Homepage or entrypoint URL
            target_keywords: Keywords to look for in URLs/content
            priority_paths: Learned patterns to try first (with {year})
            target_year: Year to substitute in patterns
            
        Returns:
            List of CrawlResult sorted by relevance score (highest first)
        """
        # Get allowed domain from start URL
        domain = extract_domain(start_url)
        if not domain:
            self.log.error("Invalid start URL", url=start_url)
            return []
        
        allowed_domains = {domain, f"www.{domain}"}
        
        # Initialize state
        visited: set[str] = set()
        results: list[CrawlResult] = []
        queue: list[QueueItem] = []
        pages_crawled = 0
        
        # Expand and queue priority paths first (if provided)
        if priority_paths and target_year:
            parsed_start = urlparse(start_url)
            base_url = f"{parsed_start.scheme}://{parsed_start.netloc}"
            
            for pattern in priority_paths:
                expanded = pattern.replace("{year}", str(target_year))
                priority_url = urljoin(base_url, expanded)
                normalized = normalize_url(priority_url)
                
                if normalized not in visited:
                    # High priority (negative score means processed first)
                    heappush(queue, QueueItem(-100.0, normalized, 0))
                    visited.add(normalized)
        
        # Add start URL
        start_normalized = normalize_url(start_url)
        if start_normalized not in visited:
            heappush(queue, QueueItem(0.0, start_normalized, 0))
            visited.add(start_normalized)
        
        self.log.info(
            "Starting BFS crawl",
            start_url=start_url,
            max_depth=self.max_depth,
            max_pages=self.max_pages,
            priority_paths=len(priority_paths or []),
        )
        
        while queue and pages_crawled < self.max_pages:
            item = heappop(queue)
            url = item.url
            depth = item.depth
            
            # Skip if too deep
            if depth > self.max_depth:
                continue
            
            # Check robots.txt
            if not await self.robots.can_fetch(url):
                self.log.debug("Blocked by robots.txt", url=url[:60])
                continue
            
            # Politeness delay
            if pages_crawled > 0:
                await asyncio.sleep(self.request_delay)
            
            # Probe URL with HEAD first
            is_valid, content_type, final_url, content_length = await self.prober.probe(
                url, 
                allowed_domains=allowed_domains,
                head_only=True,
            )
            
            if not is_valid or not final_url:
                continue
            
            pages_crawled += 1
            
            # Check if it's a document (PDF, etc) - no need to parse HTML
            is_document = self._is_document(final_url, content_type)
            
            if is_document:
                score = self._score_url(final_url, depth, target_keywords)
                result = CrawlResult(
                    url=url,
                    final_url=final_url,
                    content_type=content_type or "unknown",
                    depth=depth,
                    score=score,
                    is_document=True,
                    content_length=content_length,
                    keywords_found=self._find_keywords_in_url(final_url, target_keywords),
                )
                results.append(result)
                self.log.debug(
                    "Found document",
                    url=final_url[:60],
                    score=round(score, 2),
                    content_type=content_type,
                )
                continue
            
            # It's HTML - fetch and parse for links
            try:
                response = await self.client.get(
                    final_url,
                    timeout=self.timeout,
                    follow_redirects=True,
                )
                
                if response.status_code != 200:
                    continue
                
                content = response.text
                content_length = len(content)
                
                # Check for possible SPA (suspiciously small content)
                needs_headless = content_length < 1024 and "text/html" in (content_type or "")
                
                # Parse HTML
                soup = BeautifulSoup(content, "lxml")
                title = soup.title.string.strip() if soup.title and soup.title.string else None
                
                # Score this page
                score = self._score_url(final_url, depth, target_keywords)
                text_content = soup.get_text()
                text_keywords = self._find_keywords_in_text(text_content, target_keywords)
                
                result = CrawlResult(
                    url=url,
                    final_url=final_url,
                    content_type=content_type or "text/html",
                    depth=depth,
                    score=score + len(text_keywords) * 5,  # Boost for content keywords
                    title=title,
                    keywords_found=text_keywords or self._find_keywords_in_url(final_url, target_keywords),
                    is_document=False,
                    content_length=content_length,
                    needs_headless=needs_headless,
                )
                results.append(result)
                
                # Extract and queue links
                links = self._extract_links(soup, final_url, allowed_domains)
                
                for link in links:
                    normalized_link = normalize_url(link)
                    if normalized_link not in visited:
                        visited.add(normalized_link)
                        link_score = self._score_url(normalized_link, depth + 1, target_keywords)
                        heappush(queue, QueueItem(-link_score, normalized_link, depth + 1))
                
            except httpx.RequestError as e:
                self.log.debug("Failed to fetch page", url=final_url[:60], error=str(e))
            except Exception as e:
                self.log.debug("Error processing page", url=final_url[:60], error=str(e))
        
        # Sort results by score (highest first)
        results.sort(key=lambda r: r.score, reverse=True)
        
        self.log.info(
            "BFS crawl complete",
            pages_crawled=pages_crawled,
            results_found=len(results),
            documents_found=sum(1 for r in results if r.is_document),
        )
        
        return results
    
    def _is_document(self, url: str, content_type: str | None) -> bool:
        """Check if URL points to a document file."""
        url_lower = url.lower()
        
        # Check file extension
        for ext in DOCUMENT_EXTENSIONS:
            if url_lower.endswith(ext):
                return True
        
        # Check content type
        if content_type:
            ct = content_type.lower()
            if "pdf" in ct or "excel" in ct or "spreadsheet" in ct or "word" in ct:
                return True
        
        return False
    
    def _score_url(self, url: str, depth: int, target_keywords: list[str]) -> float:
        """Score URL based on relevance.
        
        Higher score = more likely to contain target data.
        """
        score = 0.0
        url_lower = url.lower()
        
        # Depth penalty (prefer shallower)
        score -= depth * 2
        
        # Document type bonus
        if any(url_lower.endswith(ext) for ext in DOCUMENT_EXTENSIONS):
            score += 20
            if url_lower.endswith(".pdf"):
                score += 10  # PDFs are most common format
        
        # Keyword bonuses
        for keyword in target_keywords:
            if keyword.lower() in url_lower:
                score += 15
        
        # Year in URL bonus (current/recent years)
        import re
        years = re.findall(r'/(\d{4})/', url_lower)
        for year in years:
            if 2020 <= int(year) <= 2026:
                score += 10
        
        # Irrelevant path penalty
        for pattern in IRRELEVANT_PATHS:
            if pattern in url_lower:
                score -= 50
                break
        
        return score
    
    def _find_keywords_in_url(self, url: str, target_keywords: list[str]) -> list[str]:
        """Find which target keywords appear in URL."""
        url_lower = url.lower()
        return [kw for kw in target_keywords if kw.lower() in url_lower]
    
    def _find_keywords_in_text(self, text: str, target_keywords: list[str]) -> list[str]:
        """Find which target keywords appear in text content."""
        text_lower = text.lower()
        return [kw for kw in target_keywords if kw.lower() in text_lower]
    
    def _extract_links(
        self, 
        soup: BeautifulSoup, 
        base_url: str,
        allowed_domains: set[str],
    ) -> list[str]:
        """Extract valid links from HTML.
        
        Filters out external links, skip patterns, and normalizes URLs.
        """
        links = []
        
        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            
            # Skip empty, javascript, mailto, tel links
            if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
                continue
            
            # Resolve relative URLs
            full_url = urljoin(base_url, href)
            
            try:
                parsed = urlparse(full_url)
                
                # Skip non-http(s)
                if parsed.scheme not in ("http", "https"):
                    continue
                
                # Check domain
                host = parsed.hostname
                if not host:
                    continue
                
                host_lower = host.lower()
                if host_lower.startswith("www."):
                    host_check = host_lower[4:]
                else:
                    host_check = host_lower
                
                # Skip external domains
                if not any(host_check == d or host_check.endswith(f".{d}") for d in allowed_domains):
                    continue
                
                # Skip known bad domains
                if any(skip in host_lower for skip in SKIP_DOMAINS):
                    continue
                
                # Skip irrelevant paths
                path_lower = parsed.path.lower()
                if any(pattern in path_lower for pattern in IRRELEVANT_PATHS):
                    continue
                
                links.append(full_url)
                
            except Exception:
                continue
        
        return links


def get_keywords_for_data_type(data_type: str) -> list[str]:
    """Get relevant keywords for a data type."""
    keywords = KEYWORDS.get(data_type, []).copy()
    keywords.extend(KEYWORDS.get("both", []))
    return keywords
