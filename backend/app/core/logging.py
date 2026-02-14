"""
Logging configuration with Wide Events / Canonical Log Lines pattern.

This module implements the "wide events" pattern for structured logging:
- One comprehensive event per request with all context attached
- High cardinality fields for powerful debugging (user_id, request_id, etc.)
- Build event throughout request lifecycle, emit once at the end
- Tail sampling to keep costs under control

References:
- https://charity.wtf/2019/02/05/logs-vs-structured-events/
- Stripe's "canonical log lines" pattern
"""

import os
import sys
import time
import uuid
from contextvars import ContextVar
from typing import Any

import structlog
from structlog.types import Processor

# Context variables for request-scoped wide event
_request_event: ContextVar[dict[str, Any]] = ContextVar("request_event")
_request_start: ContextVar[float] = ContextVar("request_start", default=0.0)


def get_request_event() -> dict[str, Any]:
    """Get the current request's wide event for enrichment."""
    return _request_event.get({})


def enrich_event(**kwargs: Any) -> None:
    """
    Add fields to the current request's wide event.

    Use this throughout your request handlers to add business context:

        from app.core.logging import enrich_event

        enrich_event(
            user_subscription="premium",
            cart_total_cents=15999,
            feature_flags={"new_checkout": True},
        )
    """
    event = _request_event.get({})
    for key, value in kwargs.items():
        # Support nested objects with dot notation
        if "." in key:
            parts = key.split(".")
            target = event
            for part in parts[:-1]:
                if part not in target:
                    target[part] = {}
                target = target[part]
            target[parts[-1]] = value
        else:
            event[key] = value


def init_request_event(
    request_id: str | None = None,
    method: str = "",
    path: str = "",
    client_ip: str = "",
    user_agent: str = "",
) -> dict[str, Any]:
    """Initialize a new wide event for the request."""
    event = {
        "request_id": request_id or str(uuid.uuid4())[:8],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        # Request context
        "http": {
            "method": method,
            "path": path,
            "client_ip": client_ip,
            "user_agent": user_agent[:200] if user_agent else None,
        },
        # Service context
        "service": {
            "name": "dno-crawler-api",
            "version": os.environ.get("APP_VERSION", "dev"),
            "environment": os.environ.get("ENVIRONMENT", "development"),
        },
    }

    _request_event.set(event)
    _request_start.set(time.time())
    return event


def finalize_request_event(
    status_code: int,
    error: Exception | None = None,
) -> dict[str, Any]:
    """Finalize and return the wide event for emission."""
    event = _request_event.get({})
    start_time = _request_start.get()

    # Add response context
    event["http"]["status_code"] = status_code
    event["duration_ms"] = int((time.time() - start_time) * 1000)
    event["outcome"] = "success" if status_code < 400 else "error"

    # Add error context if present
    if error:
        event["error"] = {
            "type": type(error).__name__,
            "message": str(error)[:500],  # Truncate long messages
        }
        if hasattr(error, "code"):
            event["error"]["code"] = error.code
        if hasattr(error, "details"):
            event["error"]["details"] = error.details

    return event


def should_sample(event: dict[str, Any]) -> bool:
    """
    Tail sampling decision for wide events.

    Rules:
    1. Always keep errors (4xx and 5xx)
    2. Always keep slow requests (>2000ms)
    3. Always keep admin users
    4. Sample 10% of successful fast requests
    """
    # Always keep errors
    status_code = event.get("http", {}).get("status_code", 200)
    if status_code >= 400:
        return True

    # Always keep slow requests
    duration_ms = event.get("duration_ms", 0)
    if duration_ms > 2000:
        return True

    # Always keep admin actions
    if event.get("user", {}).get("is_admin"):
        return True

    # Always keep job operations (they're important)
    path = event.get("http", {}).get("path", "")
    if "/jobs" in path or "/crawl" in path:
        return True

    # Sample 10% of the rest
    import random

    return random.random() < 0.10


def add_request_id(logger: Any, method_name: str, event_dict: dict) -> dict:
    """Processor to add request_id to all log entries."""
    current_event = _request_event.get({})
    if current_event and "request_id" in current_event:
        event_dict["request_id"] = current_event["request_id"]
    return event_dict


def configure_logging(json_logs: bool = True, log_level: str = "INFO") -> None:
    """
    Configure structlog for wide events logging.

    Args:
        json_logs: If True, output JSON format (for production).
                   If False, output colored console format (for development).
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR).
    """
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        add_request_id,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_logs:
        # Production: JSON output
        shared_processors.append(structlog.processors.format_exc_info)
        renderer = structlog.processors.JSONRenderer()
    else:
        # Development: Colored console output
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Set log level for standard library logging
    import logging

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )


def emit_wide_event(event: dict[str, Any]) -> None:
    """
    Emit the canonical log line for a request.

    This is the single, comprehensive record of what happened.
    """
    logger = structlog.get_logger("wide_event")

    # Apply sampling
    if not should_sample(event):
        return

    # Determine log level based on outcome
    status_code = event.get("http", {}).get("status_code", 200)

    if status_code >= 500:
        logger.error("request_completed", **event)
    elif status_code >= 400:
        logger.warning("request_completed", **event)
    else:
        logger.info("request_completed", **event)
