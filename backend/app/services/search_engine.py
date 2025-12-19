"""
Search Engine Service for DNO Crawler.

Provides:
- SearchProvider interface (swappable backends)
- DdgsProvider (DuckDuckGo via ddgs library)
- SearxngProvider (stub for future self-hosted search)
- UrlProber (SSRF-safe URL validation)

Security features:
- SSRF protection via ip.is_global checks
- Redirect validation with urljoin
- Content-type allowlist enforcement
- Domain allowlist support
"""

import asyncio
import ipaddress
import random
import socket
from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx
import structlog
from ddgs import DDGS

from app.core.config import settings

logger = structlog.get_logger()


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class SearchResult:
    """Single search result."""
    title: str
    url: str
    snippet: str


# =============================================================================
# Search Providers
# =============================================================================


class SearchProvider(ABC):
    """Abstract base for search providers."""
    
    @abstractmethod
    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        """Execute search query and return results."""
        pass


class DdgsProvider(SearchProvider):
    """DuckDuckGo search via ddgs library.
    
    Uses exponential backoff on rate limits.
    """
    
    def __init__(
        self,
        timeout: int = 10,
        backend: str = "duckduckgo",
        max_retries: int = 3,
        max_backoff: float = 30.0,
    ):
        self.timeout = timeout
        self.backend = backend  # "duckduckgo", "mojeek", "auto"
        self.max_retries = max_retries
        self.max_backoff = max_backoff
        self.log = logger.bind(provider="ddgs", backend=backend)
    
    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        """Execute DDG search with rate limit backoff."""
        for attempt in range(self.max_retries):
            try:
                self.log.info("Executing search", query=query[:50], attempt=attempt + 1)
                
                results = await asyncio.to_thread(
                    lambda: list(DDGS(timeout=self.timeout).text(
                        query,
                        max_results=max_results,
                        region="de-de",
                        backend=self.backend
                    ))
                )
                
                self.log.info("Search completed", result_count=len(results))
                return [
                    SearchResult(
                        title=r.get("title", ""),
                        url=r.get("href", ""),
                        snippet=r.get("body", "")
                    )
                    for r in results
                ]
                
            except Exception as e:
                if self._is_rate_limit(e):
                    wait = min((2 ** attempt) + random.uniform(0, 1), self.max_backoff)
                    self.log.warning("Rate limited, backing off", 
                                    attempt=attempt + 1, wait_seconds=round(wait, 2))
                    await asyncio.sleep(wait)
                else:
                    self.log.error("Search failed", error=str(e))
                    raise
        
        raise ValueError(f"Search failed after {self.max_retries} retries")
    
    def _is_rate_limit(self, e: Exception) -> bool:
        """Check if exception indicates rate limiting."""
        error_str = str(e).lower()
        return any(x in error_str for x in ["ratelimit", "429", "202", "too many"])


class SearxngProvider(SearchProvider):
    """SearXNG self-hosted search (future implementation).
    
    SearXNG is a privacy-respecting metasearch engine.
    When deployed, provides maximum privacy control.
    """
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.log = logger.bind(provider="searxng")
    
    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        """Search via SearXNG JSON API."""
        # TODO: Implement when SearXNG is deployed
        # API: GET {base_url}/search?q={query}&format=json
        raise NotImplementedError("SearXNG provider not yet implemented")


# =============================================================================
# URL Prober (SSRF-Safe)
# =============================================================================


# Allowed ports for URL probe
ALLOWED_PORTS = {80, 443}

# Allowed content types for data sources
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
    "application/vnd.ms-excel",  # .xls
    "application/msword",  # .doc
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "text/html",  # Landing pages (step_03 will follow links)
}


class UrlProber:
    """SSRF-safe URL validation with content-type checking.
    
    Security features:
    - Blocks private/loopback/link-local IPs (only allows ip.is_global)
    - Validates each redirect hop
    - Enforces content-type allowlist
    - Handles relative redirects with urljoin
    - Async DNS resolution to avoid blocking
    """
    
    MAX_REDIRECTS = 5
    
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.log = logger.bind(component="UrlProber")
    
    def is_safe_url(self, url: str) -> bool:
        """Validate URL structure (scheme, port, no userinfo)."""
        try:
            parsed = urlparse(url)
            
            # Scheme check
            if parsed.scheme not in ("http", "https"):
                return False
            
            # No credentials in URL
            if parsed.username or parsed.password:
                return False
            
            # Must have host
            if not parsed.netloc or not parsed.hostname:
                return False
            
            # Port check
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            if port not in ALLOWED_PORTS:
                return False
            
            return True
        except Exception:
            return False
    
    def _is_allowed_domain(self, host: str, allowed_domains: set[str]) -> bool:
        """Check if host matches allowed domains (exact or subdomain)."""
        host = host.lower()
        for domain in allowed_domains:
            domain = domain.lower()
            if host == domain or host.endswith("." + domain):
                return True
        return False
    
    async def _resolves_to_safe_ip(self, host: str) -> bool:
        """Check if host resolves only to global (public) IPs.
        
        Blocks: private, loopback, link-local, multicast, reserved, unspecified.
        """
        def _check():
            try:
                ips = socket.getaddrinfo(host, None, socket.AF_UNSPEC)
                if not ips:
                    return False
                
                for _, _, _, _, addr in ips:
                    try:
                        ip = ipaddress.ip_address(addr[0])
                        if not ip.is_global:
                            return False
                    except ValueError:
                        return False
                return True
            except socket.gaierror:
                return False
            except Exception:
                return False
        
        return await asyncio.to_thread(_check)
    
    async def probe(
        self,
        url: str,
        allowed_domains: set[str] | None = None,
    ) -> tuple[bool, str | None, str | None]:
        """Probe URL for existence and content type.
        
        Args:
            url: URL to probe
            allowed_domains: Optional set of allowed domains (for SSRF protection)
        
        Returns:
            (is_valid, content_type, final_url)
            - is_valid: True if URL is reachable and safe
            - content_type: MIME type of response
            - final_url: URL after following redirects
        """
        # Initial safety check
        if not self.is_safe_url(url):
            self.log.debug("URL failed safety check", url=url[:80])
            return False, None, None
        
        parsed = urlparse(url)
        
        # Domain allowlist check (if provided)
        if allowed_domains and not self._is_allowed_domain(parsed.hostname, allowed_domains):
            self.log.debug("Domain not in allowlist", host=parsed.hostname)
            return False, None, None
        
        # DNS safety check
        if not await self._resolves_to_safe_ip(parsed.hostname):
            self.log.warning("Blocked non-global IP", host=parsed.hostname)
            return False, None, None
        
        try:
            current_url = url
            redirect_count = 0
            
            while redirect_count < self.MAX_REDIRECTS:
                # Try HEAD first
                response = await self.client.head(current_url, follow_redirects=False)
                
                # Handle redirects manually (SSRF protection)
                if response.is_redirect:
                    redirect_count += 1
                    location = response.headers.get("location")
                    if not location:
                        return False, None, None
                    
                    # Resolve relative redirects
                    next_url = urljoin(str(response.url), location)
                    
                    # Validate redirect target
                    if not self.is_safe_url(next_url):
                        self.log.warning("Unsafe redirect blocked", location=next_url[:80])
                        return False, None, None
                    
                    next_parsed = urlparse(next_url)
                    
                    # Domain check on redirect
                    if allowed_domains and not self._is_allowed_domain(next_parsed.hostname, allowed_domains):
                        self.log.warning("Redirect to disallowed domain", host=next_parsed.hostname)
                        return False, None, None
                    
                    # DNS check on redirect (rebinding protection)
                    if not await self._resolves_to_safe_ip(next_parsed.hostname):
                        self.log.warning("Redirect to non-global IP blocked", host=next_parsed.hostname)
                        return False, None, None
                    
                    current_url = next_url
                    continue
                
                # Handle 405 Method Not Allowed (HEAD not supported)
                if response.status_code == 405:
                    # Fall back to bounded GET
                    response = await self.client.get(
                        current_url,
                        headers={"Range": "bytes=0-4095"},
                        follow_redirects=False
                    )
                
                # Check final status
                if response.status_code not in (200, 206):
                    return False, None, None
                
                # Extract and validate content type
                content_type = response.headers.get("content-type", "")
                content_type = content_type.split(";")[0].strip().lower()
                
                if content_type not in ALLOWED_CONTENT_TYPES:
                    # Allow files by extension even if content-type is wrong
                    url_lower = current_url.lower()
                    if not any(url_lower.endswith(ext) for ext in [".pdf", ".xlsx", ".xls", ".docx"]):
                        self.log.debug("Content type not allowed", 
                                      content_type=content_type, url=current_url[:80])
                        return False, None, None
                
                return True, content_type, current_url
            
            # Too many redirects
            self.log.warning("Too many redirects", url=url[:80])
            return False, None, None
            
        except httpx.TimeoutException:
            self.log.debug("Probe timeout", url=url[:80])
            return False, None, None
        except httpx.RequestError as e:
            self.log.debug("Probe request error", url=url[:80], error=str(e))
            return False, None, None
        except Exception as e:
            self.log.debug("Probe failed", url=url[:80], error=str(e))
            return False, None, None


# =============================================================================
# Factory Functions
# =============================================================================


def get_search_provider(provider_type: str = "ddgs", **kwargs) -> SearchProvider:
    """Factory function to get a search provider.
    
    Args:
        provider_type: "ddgs" or "searxng"
        **kwargs: Provider-specific configuration
    
    Returns:
        SearchProvider instance
    """
    if provider_type == "ddgs":
        return DdgsProvider(
            timeout=kwargs.get("timeout", settings.ddgs_timeout),
            backend=kwargs.get("backend", "duckduckgo"),
        )
    elif provider_type == "searxng":
        base_url = kwargs.get("base_url")
        if not base_url:
            raise ValueError("SearXNG requires base_url")
        return SearxngProvider(base_url=base_url)
    else:
        raise ValueError(f"Unknown provider type: {provider_type}")


# =============================================================================
# Legacy Compatibility (to be removed later)
# =============================================================================


class SearchEngine:
    """Legacy search engine class for backward compatibility.
    
    DEPRECATED: Use DdgsProvider directly for new code.
    """
    
    def __init__(self):
        """Initialize the search engine."""
        self.ddgs = DDGS(timeout=settings.ddgs_timeout)
        self.log = logger.bind(component="SearchEngine")
    
    def safe_search(self, query: str, max_results: int = 4) -> list[dict]:
        """Perform web search with rate limiting (sync)."""
        import time
        time.sleep(settings.ddgs_request_delay_seconds)
        
        try:
            self.log.info("Executing DDGS search", query=query)
            results = self.ddgs.text(query, max_results=max_results)
            return list(results) if results else []
        except Exception as e:
            self.log.error("DDGS search failed", error=str(e))
            return []
