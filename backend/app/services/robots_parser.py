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
    sitemap_verified: bool = False  # True if sitemap URL was successfully accessed


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
    if 'meta http-equiv="refresh"' in content_lower and "challenge" in content_lower:
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


async def verify_sitemap_access(
    client: httpx.AsyncClient,
    sitemap_url: str,
    timeout: float = 10.0,
) -> tuple[bool, str | None]:
    """
    Verify that a sitemap URL is accessible (not protected).

    This is a secondary check after robots.txt passes to detect
    false positives where robots.txt is open but content is protected.

    Args:
        client: HTTP client
        sitemap_url: Full URL to the sitemap
        timeout: Request timeout

    Returns:
        (is_accessible, blocked_reason) - True if accessible, False if protected
    """
    log = logger.bind(sitemap_url=sitemap_url)

    try:
        response = await client.get(sitemap_url, timeout=timeout, follow_redirects=True)
        content = response.text
        status = response.status_code

        # Check HTTP status
        if status == 403:
            cf_mitigated = response.headers.get("cf-mitigated", "").lower()
            server = response.headers.get("server", "").lower()
            if cf_mitigated == "challenge" or "cloudflare" in server:
                log.warning("Sitemap blocked by Cloudflare (403)")
                return False, "cloudflare"
            log.warning("Sitemap returned 403 - access denied")
            return False, "access_denied"

        if status == 429:
            log.warning("Sitemap rate limited (429)")
            return False, "rate_limited_or_ip_blocked"

        if status != 200:
            log.warning("Sitemap returned unexpected status", status=status)
            return False, f"http_error_{status}"

        # Check for Cloudflare challenge in headers
        cf_mitigated = response.headers.get("cf-mitigated", "").lower()
        if cf_mitigated == "challenge":
            log.warning("Sitemap blocked by Cloudflare challenge")
            return False, "cloudflare"

        # Check for JS protection in content
        is_protected, protection_type = detect_js_protection(content)
        if is_protected:
            log.warning("Sitemap uses JavaScript protection", protection=protection_type)
            return False, protection_type

        # Check if response is HTML instead of XML (sitemap should be XML)
        content_lower = content.lower()
        if "<html" in content_lower[:500] or "<!doctype" in content_lower[:100]:
            # Received HTML - check for protection
            is_protected, protection_type = detect_js_protection(content)
            if is_protected:
                return False, protection_type
            # HTML but no protection - might be error page, site may still work
            log.warning("Sitemap returned HTML instead of XML")
            return True, None

        # Check for valid sitemap content
        if "<urlset" in content_lower or "<sitemapindex" in content_lower:
            log.info("Sitemap verified successfully")
            return True, None

        # Unknown content - assume accessible
        log.debug("Sitemap content format unknown, assuming accessible")
        return True, None

    except httpx.TimeoutException:
        log.warning("Timeout fetching sitemap")
        return False, "timeout"

    except httpx.ConnectError as e:
        log.warning("Connection failed fetching sitemap", error=str(e))
        return False, "connection_failed"

    except httpx.RequestError as e:
        log.warning("Request error fetching sitemap", error=str(e))
        return False, "request_error"


async def fetch_and_verify_robots(
    client: httpx.AsyncClient,
    website: str,
    timeout: float = 10.0,
    verify_sitemap: bool = True,
) -> RobotsResult:
    """
    Fetch robots.txt and optionally verify sitemap accessibility.

    This is the recommended entry point for crawlability checks.
    It combines robots.txt parsing with sitemap verification to
    detect sites where robots.txt is open but content is protected.

    Args:
        client: HTTP client
        website: Base website URL
        timeout: Request timeout
        verify_sitemap: If True, verify first sitemap URL after robots.txt

    Returns:
        RobotsResult with crawlability and sitemap verification info
    """
    log = logger.bind(website=website)

    # First, fetch and parse robots.txt
    result = await fetch_robots_txt(client, website, timeout)

    # If robots.txt reports not crawlable, no need to check sitemap
    if not result.crawlable:
        return result

    # Verify sitemap if requested and sitemaps are available
    if verify_sitemap and result.sitemap_urls:
        sitemap_url = result.sitemap_urls[0]
        log.info("Verifying sitemap accessibility", sitemap_url=sitemap_url)

        is_accessible, blocked_reason = await verify_sitemap_access(
            client, sitemap_url, timeout
        )

        if is_accessible:
            result.sitemap_verified = True
        else:
            # Sitemap is blocked - mark site as protected
            result.sitemap_verified = False
            result.crawlable = False
            result.blocked_reason = blocked_reason
            log.warning(
                "Site marked as protected - robots.txt OK but sitemap blocked",
                blocked_reason=blocked_reason,
            )

    return result
