"""
Retry Utilities for DNO Crawler.

Provides exponential backoff retry logic for HTTP requests
and other transient operations.
"""

import asyncio
import contextlib
import random
from collections.abc import Callable
from typing import Any, TypeVar

import httpx
import structlog

logger = structlog.get_logger()

T = TypeVar("T")

# Exceptions that should trigger a retry
RETRYABLE_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.NetworkError,
    httpx.ConnectError,
    httpx.ReadError,
    httpx.WriteError,
    httpx.PoolTimeout,
)

# HTTP status codes that warrant a retry
STATUS_REQUEST_TIMEOUT = 408
STATUS_TOO_MANY_REQUESTS = 429
STATUS_INTERNAL_SERVER_ERROR = 500
STATUS_BAD_GATEWAY = 502
STATUS_SERVICE_UNAVAILABLE = 503
STATUS_GATEWAY_TIMEOUT = 504

RETRYABLE_STATUS_CODES = {
    STATUS_REQUEST_TIMEOUT,
    STATUS_TOO_MANY_REQUESTS,
    STATUS_INTERNAL_SERVER_ERROR,
    STATUS_BAD_GATEWAY,
    STATUS_SERVICE_UNAVAILABLE,
    STATUS_GATEWAY_TIMEOUT,
}


async def with_retries(
    func: Callable[..., T],
    *args: Any,
    max_attempts: int = 3,
    backoff_base: float = 1.0,
    backoff_max: float = 30.0,
    jitter: float = 0.1,
    retry_on: tuple = RETRYABLE_EXCEPTIONS,
    **kwargs: Any,
) -> T:
    """
    Execute an async function with exponential backoff retries.

    Args:
        func: Async function to call
        *args: Positional arguments for func
        max_attempts: Maximum number of attempts (default: 3)
        backoff_base: Base delay in seconds (default: 1.0)
        backoff_max: Maximum delay in seconds (default: 30.0)
        jitter: Random jitter factor (0.1 = ±10%)
        retry_on: Tuple of exception types to retry on
        **kwargs: Keyword arguments for func

    Returns:
        Result from successful function call

    Raises:
        Last exception if all attempts fail
    """
    log = logger.bind(func=func.__name__, max_attempts=max_attempts)

    last_exception: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            result = await func(*args, **kwargs)

            # Check for retryable HTTP status codes if result is a Response
            if isinstance(result, httpx.Response) and result.status_code in RETRYABLE_STATUS_CODES:
                # Check for Retry-After header on 429
                retry_after = None
                if result.status_code == STATUS_TOO_MANY_REQUESTS:
                    retry_after_header = result.headers.get("retry-after")
                    if retry_after_header:
                        with contextlib.suppress(ValueError):
                            retry_after = float(retry_after_header)

                if attempt < max_attempts:
                    delay = retry_after or min(backoff_base * (2 ** (attempt - 1)), backoff_max)
                    delay *= 1 + random.uniform(-jitter, jitter)
                    log.warning(
                        "Retrying due to HTTP status",
                        status=result.status_code,
                        attempt=attempt,
                        delay=round(delay, 2),
                    )
                    await asyncio.sleep(delay)
                    continue

            return result

        except retry_on as e:
            last_exception = e

            if attempt < max_attempts:
                delay = min(backoff_base * (2 ** (attempt - 1)), backoff_max)
                delay *= 1 + random.uniform(-jitter, jitter)

                log.warning(
                    "Retry after exception",
                    error=str(e),
                    attempt=attempt,
                    delay=round(delay, 2),
                )
                await asyncio.sleep(delay)
            else:
                log.error(
                    "All retry attempts failed",
                    error=str(e),
                    attempts=max_attempts,
                )
                raise

    # Should not reach here, but satisfy type checker
    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected retry loop exit")


async def fetch_with_retries(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    max_attempts: int = 3,
    **kwargs: Any,
) -> httpx.Response:
    """
    Convenience wrapper for HTTP requests with retries.

    Args:
        client: httpx AsyncClient
        method: HTTP method (GET, POST, etc.)
        url: URL to fetch
        max_attempts: Maximum retry attempts
        **kwargs: Additional arguments for client.request()

    Returns:
        httpx.Response
    """

    async def _do_request() -> httpx.Response:
        return await client.request(method, url, **kwargs)

    return await with_retries(_do_request, max_attempts=max_attempts)
