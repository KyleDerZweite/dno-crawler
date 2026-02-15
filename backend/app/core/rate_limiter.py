"""
Rate Limiter for Public API with dual-layer protection.

Layer 1: Per-IP limit (prevents individual abuse)
Layer 2: Global VNB API quota (protects external API key)

Uses Redis for distributed rate limiting across multiple workers.
"""

import structlog
from fastapi import HTTPException, Request, status
from redis.asyncio import Redis

logger = structlog.get_logger()


class RateLimiter:
    """
    Dual-layer rate limiter for public API protection.

    - Per-IP: Limits requests from individual clients
    - Global VNB: Limits total VNB Digital API calls across ALL users
    """

    # Redis key for GLOBAL VNB API counter (shared across all requests)
    VNB_GLOBAL_KEY = "global:vnb_api:count"

    def __init__(
        self,
        redis: Redis,
        ip_rate: int = 60,  # Requests per IP per window
        ip_window: int = 60,  # Window in seconds
        vnb_global_rate: int = 50,  # VNB API calls per window (ALL users)
        vnb_window: int = 60,
        authenticated_rate: int = 100,  # Requests per IP per window for authenticated users
    ):
        """
        Initialize rate limiter.

        Args:
            redis: Redis connection
            ip_rate: Max requests per IP per window (default 60/min = 1/sec avg)
            ip_window: Window in seconds for IP limiting
            vnb_global_rate: Max VNB API calls globally per window
            vnb_window: Window in seconds for VNB limiting
            authenticated_rate: Max requests per IP per window for authenticated users
        """
        self.redis = redis
        self.ip_rate = ip_rate
        self.ip_window = ip_window
        self.vnb_global_rate = vnb_global_rate
        self.vnb_window = vnb_window
        self.authenticated_rate = authenticated_rate
        self.log = logger.bind(component="RateLimiter")

    async def check_ip_limit(self, ip: str, authenticated: bool = False) -> None:
        """
        Check and increment IP rate limit.

        Args:
            ip: Client IP address.
            authenticated: If True, use the higher authenticated rate limit.

        Raises:
            HTTPException: 429 if rate limit exceeded
        """
        limit = self.authenticated_rate if authenticated else self.ip_rate
        key = f"rate_limit:ip:{ip}"

        try:
            async with self.redis.pipeline(transaction=True) as pipe:
                await pipe.incr(key)
                await pipe.expire(key, self.ip_window)
                results = await pipe.execute()
            count = results[0]

            if count > limit:
                self.log.warning("IP rate limit exceeded", ip=ip, count=count, authenticated=authenticated)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Max {limit} requests per minute.",
                    headers={"Retry-After": str(self.ip_window)},
                )
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            # Log but don't block on Redis errors
            self.log.error("Redis error in IP rate limit", error=str(e))

    async def check_vnb_quota(self) -> None:
        """
        Check global VNB API quota before making VNB Digital call.

        Raises:
            HTTPException: 503 if quota exhausted
        """
        try:
            async with self.redis.pipeline(transaction=True) as pipe:
                await pipe.incr(self.VNB_GLOBAL_KEY)
                await pipe.expire(self.VNB_GLOBAL_KEY, self.vnb_window)
                results = await pipe.execute()
            count = results[0]

            if count > self.vnb_global_rate:
                self.log.warning("VNB global quota exhausted", count=count)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="External API quota temporarily exhausted. Please retry later.",
                    headers={"Retry-After": str(self.vnb_window)},
                )
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            self.log.error("Redis error in VNB quota check", error=str(e))

    async def before_vnb_call(self) -> None:
        """Convenience method to call before every VNB Digital API request."""
        await self.check_vnb_quota()

    async def get_current_counts(self, ip: str) -> dict:
        """Get current rate limit counts (for debugging/monitoring)."""
        try:
            ip_count = await self.redis.get(f"rate_limit:ip:{ip}")
            vnb_count = await self.redis.get(self.VNB_GLOBAL_KEY)
            return {
                "ip_count": int(ip_count) if ip_count else 0,
                "ip_limit": self.ip_rate,
                "vnb_count": int(vnb_count) if vnb_count else 0,
                "vnb_limit": self.vnb_global_rate,
            }
        except Exception:
            return {}


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies.

    Uses rightmost-N approach: take the Nth IP from the right of X-Forwarded-For,
    where N = TRUSTED_PROXY_COUNT. This prevents spoofing because only trusted
    proxies append to the right side of the header.
    """
    from app.core.config import settings

    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ips = [ip.strip() for ip in forwarded.split(",") if ip.strip()]
        # The rightmost `trusted_proxy_count` entries are from trusted proxies.
        # The client IP is at index -(trusted_proxy_count + 1) from the end.
        idx = len(ips) - settings.trusted_proxy_count
        if 0 <= idx < len(ips):
            return ips[idx]
        # If fewer IPs than expected proxies, use the leftmost (direct client)
        return ips[0]

    # Fallback to direct connection IP
    if request.client:
        return request.client.host

    return "unknown"


# Rate limiter instance will be created with Redis connection at startup
_rate_limiter: RateLimiter | None = None


def init_rate_limiter(redis: Redis) -> RateLimiter:
    """Initialize the global rate limiter with Redis connection."""
    from app.core.config import settings

    global _rate_limiter
    _rate_limiter = RateLimiter(
        redis,
        ip_rate=settings.rate_limit_public,
        authenticated_rate=settings.rate_limit_authenticated,
    )
    return _rate_limiter


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    if _rate_limiter is None:
        raise RuntimeError("Rate limiter not initialized. Call init_rate_limiter() first.")
    return _rate_limiter
