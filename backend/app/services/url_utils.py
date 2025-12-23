"""
URL Utilities for DNO Crawler.

Provides:
- UrlProber: SSRF-safe URL validation with content-type checking
- normalize_url: URL deduplication normalization
- RobotsChecker: robots.txt compliance checker

Security features:
- SSRF protection via ip.is_global checks
- Redirect validation with urljoin
- Content-type allowlist enforcement
- Domain allowlist support
"""

import asyncio
import ipaddress
import re
import socket
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import httpx
import structlog

logger = structlog.get_logger()


# =============================================================================
# Constants
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
    "text/html",  # Landing pages
}

# Document file extensions (for content-type fallback)
DOCUMENT_EXTENSIONS = {".pdf", ".pdfx", ".xlsx", ".xls", ".docx", ".doc"}

# Query parameters to strip (tracking, session, etc.)
STRIP_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "session_id", "sessionid", "sid", "ref", "referrer",
    "source", "tracking", "_ga", "_gl", "mc_cid", "mc_eid",
}


# =============================================================================
# URL Normalization
# =============================================================================


def normalize_url(url: str) -> str:
    """Normalize URL for deduplication.
    
    - Strip tracking params (?utm_*, ?session_id, etc)
    - Remove anchors (#section)
    - Normalize trailing slashes (keep for directories, remove for files)
    - Lowercase hostname
    - Sort remaining query parameters
    
    Args:
        url: URL to normalize
        
    Returns:
        Normalized URL string
    """
    try:
        parsed = urlparse(url)
        
        # Lowercase hostname
        hostname = parsed.hostname.lower() if parsed.hostname else ""
        
        # Rebuild netloc with lowercase hostname
        if parsed.port and parsed.port not in (80, 443):
            netloc = f"{hostname}:{parsed.port}"
        else:
            netloc = hostname
        
        # Clean path - normalize double slashes, handle trailing slash
        path = re.sub(r'/+', '/', parsed.path)
        if not path:
            path = "/"
        
        # Keep trailing slash for directories, remove for files
        if path != "/" and not any(path.lower().endswith(ext) for ext in DOCUMENT_EXTENSIONS):
            # Assume it's a directory if no extension
            if not path.endswith("/"):
                path = path + "/"
        
        # Filter out tracking parameters
        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=True)
            filtered = {
                k: v for k, v in params.items() 
                if k.lower() not in STRIP_PARAMS and not k.lower().startswith("utm_")
            }
            # Sort for consistency
            query = urlencode(sorted(filtered.items()), doseq=True)
        else:
            query = ""
        
        # Remove fragment (anchor)
        return urlunparse((
            parsed.scheme,
            netloc,
            path,
            "",  # params
            query,
            "",  # fragment removed
        ))
    except Exception:
        return url  # Return original on error


def extract_domain(url: str) -> str | None:
    """Extract domain from URL without www prefix."""
    try:
        parsed = urlparse(url)
        if parsed.hostname:
            domain = parsed.hostname.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
    except Exception:
        pass
    return None


# =============================================================================
# Robots.txt Checker
# =============================================================================


class RobotsChecker:
    """Check robots.txt compliance for crawling.
    
    Caches robots.txt per domain to avoid repeated fetches.
    """
    
    USER_AGENT = "DNO-Data-Crawler/1.0"
    
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self._cache: dict[str, RobotFileParser] = {}
        self.log = logger.bind(component="RobotsChecker")
    
    async def can_fetch(self, url: str) -> bool:
        """Check if URL can be fetched according to robots.txt.
        
        Args:
            url: URL to check
            
        Returns:
            True if allowed to fetch, False if disallowed
        """
        try:
            parsed = urlparse(url)
            domain = f"{parsed.scheme}://{parsed.netloc}"
            
            # Get or fetch robots.txt
            if domain not in self._cache:
                await self._fetch_robots(domain)
            
            rp = self._cache.get(domain)
            if rp is None:
                # No robots.txt or fetch failed - allow by default
                return True
            
            return rp.can_fetch(self.USER_AGENT, url)
        except Exception as e:
            self.log.debug("robots.txt check failed", url=url[:80], error=str(e))
            return True  # Allow on error
    
    async def _fetch_robots(self, domain: str):
        """Fetch and parse robots.txt for domain."""
        robots_url = f"{domain}/robots.txt"
        try:
            response = await self.client.get(robots_url, timeout=5.0)
            if response.status_code == 200:
                rp = RobotFileParser()
                rp.parse(response.text.splitlines())
                self._cache[domain] = rp
                self.log.debug("Loaded robots.txt", domain=domain)
            else:
                self._cache[domain] = None  # No robots.txt
        except Exception as e:
            self.log.debug("Failed to fetch robots.txt", domain=domain, error=str(e))
            self._cache[domain] = None


# =============================================================================
# URL Prober (SSRF-Safe)
# =============================================================================


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
        head_only: bool = False,
    ) -> tuple[bool, str | None, str | None, int | None]:
        """Probe URL for existence and content type.
        
        Args:
            url: URL to probe
            allowed_domains: Optional set of allowed domains (for SSRF protection)
            head_only: If True, only do HEAD request (faster for existence check)
        
        Returns:
            (is_valid, content_type, final_url, content_length)
            - is_valid: True if URL is reachable and safe
            - content_type: MIME type of response
            - final_url: URL after following redirects
            - content_length: Content-Length header if available
        """
        # Initial safety check
        if not self.is_safe_url(url):
            self.log.debug("URL failed safety check", url=url[:80])
            return False, None, None, None
        
        parsed = urlparse(url)
        
        # Domain allowlist check (if provided)
        if allowed_domains and not self._is_allowed_domain(parsed.hostname, allowed_domains):
            self.log.debug("Domain not in allowlist", host=parsed.hostname)
            return False, None, None, None
        
        # DNS safety check
        if not await self._resolves_to_safe_ip(parsed.hostname):
            self.log.warning("Blocked non-global IP", host=parsed.hostname)
            return False, None, None, None
        
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
                        return False, None, None, None
                    
                    # Resolve relative redirects
                    next_url = urljoin(str(response.url), location)
                    
                    # Validate redirect target
                    if not self.is_safe_url(next_url):
                        self.log.warning("Unsafe redirect blocked", location=next_url[:80])
                        return False, None, None, None
                    
                    next_parsed = urlparse(next_url)
                    
                    # Domain check on redirect
                    if allowed_domains and not self._is_allowed_domain(next_parsed.hostname, allowed_domains):
                        self.log.warning("Redirect to disallowed domain", host=next_parsed.hostname)
                        return False, None, None, None
                    
                    # DNS check on redirect (rebinding protection)
                    if not await self._resolves_to_safe_ip(next_parsed.hostname):
                        self.log.warning("Redirect to non-global IP blocked", host=next_parsed.hostname)
                        return False, None, None, None
                    
                    current_url = next_url
                    continue
                
                # Handle 405 Method Not Allowed (HEAD not supported)
                if response.status_code == 405 and not head_only:
                    # Fall back to bounded GET
                    response = await self.client.get(
                        current_url,
                        headers={"Range": "bytes=0-4095"},
                        follow_redirects=False
                    )
                
                # Check final status
                if response.status_code not in (200, 206):
                    return False, None, None, None
                
                # Extract content info
                content_type = response.headers.get("content-type", "")
                content_type = content_type.split(";")[0].strip().lower()
                content_length = response.headers.get("content-length")
                content_length = int(content_length) if content_length else None
                
                if content_type not in ALLOWED_CONTENT_TYPES:
                    # Allow files by extension even if content-type is wrong
                    url_lower = current_url.lower()
                    if not any(url_lower.endswith(ext) for ext in DOCUMENT_EXTENSIONS):
                        self.log.debug("Content type not allowed", 
                                      content_type=content_type, url=current_url[:80])
                        return False, None, None, None
                
                return True, content_type, current_url, content_length
            
            # Too many redirects
            self.log.warning("Too many redirects", url=url[:80])
            return False, None, None, None
            
        except httpx.TimeoutException:
            self.log.debug("Probe timeout", url=url[:80])
            return False, None, None, None
        except httpx.RequestError as e:
            self.log.debug("Probe request error", url=url[:80], error=str(e))
            return False, None, None, None
        except Exception as e:
            self.log.debug("Probe failed", url=url[:80], error=str(e))
            return False, None, None, None
