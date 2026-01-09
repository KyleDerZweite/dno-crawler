"""
Robots.txt Parser and Crawlability Detector.

Used during DNO skeleton creation to:
1. Fetch and store robots.txt
2. Extract Sitemap URLs
3. Parse Disallow rules
4. Detect Cloudflare/JS protection
"""

from dataclasses import dataclass, field

import httpx
import structlog

logger = structlog.get_logger()


@dataclass
class RobotsResult:
    """Result of robots.txt fetch and parse."""
    raw_content: str | None = None
    sitemap_urls: list[str] = field(default_factory=list)
    disallow_paths: list[str] = field(default_factory=list)
    crawlable: bool = True
    blocked_reason: str | None = None


# Indicators that a site is using JavaScript protection
JS_PROTECTION_INDICATORS = [
    "enable javascript",
    "javascript is required",
    "cf_chl_opt",  # Cloudflare challenge
    "challenge-platform",  # Cloudflare
    "__cf_bm",  # Cloudflare bot management
    "just a moment",  # Cloudflare "Just a moment..."
    "checking your browser",
    "ddos protection by",
]


def parse_robots_txt(content: str, user_agent: str = "*") -> tuple[list[str], list[str]]:
    """
    Parse robots.txt content.
    
    Args:
        content: Raw robots.txt content
        user_agent: User agent to match rules for (default: *)
    
    Returns:
        (sitemap_urls, disallow_paths)
    """
    sitemap_urls = []
    disallow_paths = []

    current_ua = None
    applies_to_us = False

    for line in content.splitlines():
        line = line.strip()

        # Skip comments and empty lines
        if not line or line.startswith("#"):
            continue

        # Check for Sitemap (global, not UA-specific)
        if line.lower().startswith("sitemap:"):
            url = line.split(":", 1)[1].strip()
            if url:
                sitemap_urls.append(url)
            continue

        # Parse User-agent directive
        if line.lower().startswith("user-agent:"):
            ua = line.split(":", 1)[1].strip().lower()
            applies_to_us = (ua == "*" or user_agent.lower() in ua)
            continue

        # Parse Disallow directive
        if line.lower().startswith("disallow:") and applies_to_us:
            path = line.split(":", 1)[1].strip()
            if path and path != "/":  # Ignore "Disallow: /" as it blocks everything
                disallow_paths.append(path)
            elif path == "/":
                # Complete block
                disallow_paths.append("/")

    return sitemap_urls, disallow_paths


def detect_js_protection(content: str) -> tuple[bool, str | None]:
    """
    Detect if response indicates JavaScript protection.
    
    Returns:
        (is_protected, protection_type)
    """
    content_lower = content.lower()

    for indicator in JS_PROTECTION_INDICATORS:
        if indicator in content_lower:
            if "cloudflare" in content_lower or "cf_chl" in content_lower:
                return True, "cloudflare"
            else:
                return True, "javascript_required"

    # Check for meta refresh to challenge page
    if 'meta http-equiv="refresh"' in content_lower:
        if "challenge" in content_lower:
            return True, "javascript_challenge"

    return False, None


async def fetch_robots_txt(
    client: httpx.AsyncClient,
    website: str,
    timeout: float = 10.0,
) -> RobotsResult:
    """
    Fetch and parse robots.txt from a website.
    
    Detects JS protection, HTTP errors, and extracts sitemap/disallow rules.
    
    Args:
        client: HTTP client
        website: Base website URL (e.g., https://www.example.de)
        timeout: Request timeout
    
    Returns:
        RobotsResult with crawlability info
    """
    log = logger.bind(website=website)
    result = RobotsResult()

    # Normalize URL
    if not website.startswith("http"):
        website = f"https://{website}"
    website = website.rstrip("/")

    robots_url = f"{website}/robots.txt"

    try:
        response = await client.get(robots_url, timeout=timeout, follow_redirects=True)
        content = response.text
        status = response.status_code

        # === Check HTTP status codes FIRST ===

        # 403 Forbidden - Often Cloudflare or WAF blocking
        if status == 403:
            cf_mitigated = response.headers.get("cf-mitigated", "").lower()
            server = response.headers.get("server", "").lower()

            if cf_mitigated == "challenge" or "cloudflare" in server:
                log.warning("Site blocked by Cloudflare challenge (403)", cf_mitigated=cf_mitigated)
                result.crawlable = False
                result.blocked_reason = "cloudflare"
                return result
            else:
                # Generic 403 - could be WAF, geo-block, etc.
                log.warning("Site returned 403 Forbidden - access denied")
                result.crawlable = False
                result.blocked_reason = "access_denied"
                return result

        # 429 Too Many Requests - Rate limited or IP banned
        if status == 429:
            retry_after = response.headers.get("retry-after", "unknown")
            log.warning("Site rate limiting or IP blocked (429)", retry_after=retry_after)
            result.crawlable = False
            result.blocked_reason = "rate_limited_or_ip_blocked"
            return result

        # 401/407 - Authentication required
        if status in (401, 407):
            log.warning("Site requires authentication", status=status)
            result.crawlable = False
            result.blocked_reason = "authentication_required"
            return result

        # 5xx Server errors
        if 500 <= status < 600:
            log.warning("Site server error", status=status)
            result.crawlable = False
            result.blocked_reason = f"server_error_{status}"
            return result

        # 404 - No robots.txt, but site is accessible
        if status == 404:
            log.info("No robots.txt found (404) - site is crawlable")
            result.raw_content = None
            return result

        # Other non-200 status codes
        if status != 200:
            log.warning("Unexpected HTTP status", status=status)
            result.crawlable = False
            result.blocked_reason = f"http_error_{status}"
            return result

        # === Check for Cloudflare challenge in response headers (even on 200) ===
        cf_mitigated = response.headers.get("cf-mitigated", "").lower()
        if cf_mitigated == "challenge":
            log.warning("Cloudflare challenge detected in headers despite 200 status")
            result.crawlable = False
            result.blocked_reason = "cloudflare"
            return result

        # === Check for JS protection in content ===
        is_protected, protection_type = detect_js_protection(content)
        if is_protected:
            log.warning("Site uses JavaScript protection", protection=protection_type)
            result.crawlable = False
            result.blocked_reason = protection_type
            return result

        # === Check if response is HTML instead of robots.txt ===
        content_lower = content.lower()
        if "<html" in content_lower[:500] or "<!doctype" in content_lower[:100]:
            # Received HTML instead of robots.txt - check for JS protection
            is_protected, protection_type = detect_js_protection(content)
            if is_protected:
                result.crawlable = False
                result.blocked_reason = protection_type
                return result
            log.warning("Received HTML instead of robots.txt - may be error page")
            result.raw_content = None
            return result

        # === Parse valid robots.txt ===
        result.raw_content = content
        result.sitemap_urls, result.disallow_paths = parse_robots_txt(content)

        # Check if we're completely blocked by robots.txt rules
        if "/" in result.disallow_paths:
            log.warning("Site blocks all crawling via robots.txt")
            result.crawlable = False
            result.blocked_reason = "robots_disallow_all"

        log.info(
            "Parsed robots.txt",
            sitemaps=len(result.sitemap_urls),
            disallow_rules=len(result.disallow_paths),
        )

        return result

    except httpx.TimeoutException:
        log.error("Timeout fetching robots.txt - site may be slow or blocking")
        result.crawlable = False
        result.blocked_reason = "timeout"
        return result

    except httpx.ConnectError as e:
        log.error("Connection failed - site may be down or blocking IP", error=str(e))
        result.crawlable = False
        result.blocked_reason = "connection_failed"
        return result

    except httpx.RequestError as e:
        log.error("Request error fetching robots.txt", error=str(e))
        result.crawlable = False
        result.blocked_reason = "request_error"
        return result
