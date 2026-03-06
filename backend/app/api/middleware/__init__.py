"""
API Middleware package.

Contains middleware components for request processing:
- Wide Events: Canonical log line pattern for comprehensive request logging
"""

from app.api.middleware.security_headers import SecurityHeadersMiddleware
from app.api.middleware.wide_events import (
    WideEventMiddleware,
    add_dno_to_wide_event,
    add_job_to_wide_event,
    add_user_to_wide_event,
)

__all__ = [
    "SecurityHeadersMiddleware",
    "WideEventMiddleware",
    "add_dno_to_wide_event",
    "add_job_to_wide_event",
    "add_user_to_wide_event",
]
