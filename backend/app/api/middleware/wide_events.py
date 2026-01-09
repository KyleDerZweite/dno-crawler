"""
Wide Events Middleware for FastAPI.

This middleware implements the canonical log line pattern:
- Initializes a wide event at request start
- Enriches with user context after auth
- Finalizes and emits on request completion
- One comprehensive log entry per request

Usage:
    app.add_middleware(WideEventMiddleware)
    
Then in your handlers:
    from app.core.logging import enrich_event
    
    @router.post("/checkout")
    async def checkout(request: Request):
        enrich_event(
            cart_item_count=len(items),
            cart_total_cents=total,
            payment_method="card",
        )
        ...
"""

import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import (
    emit_wide_event,
    enrich_event,
    finalize_request_event,
    init_request_event,
)


class WideEventMiddleware(BaseHTTPMiddleware):
    """
    Middleware that captures wide events for every request.
    
    Creates one comprehensive log entry per request containing:
    - Request metadata (method, path, headers)
    - User context (added by auth middleware)
    - Business context (added by handlers via enrich_event)
    - Response metadata (status, duration)
    - Error context (if applicable)
    """
    
    # Paths to skip (health checks generate too much noise)
    SKIP_PATHS = {"/health", "/api/v1/health", "/metrics", "/favicon.ico"}
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        # Skip noisy endpoints
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)
        
        # Initialize wide event
        request_id = request.headers.get("x-request-id")
        init_request_event(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=self._get_client_ip(request),
            user_agent=request.headers.get("user-agent", ""),
        )
        
        # Add query params if present
        if request.query_params:
            enrich_event(**{"http.query_params": dict(request.query_params)})
        
        # Process request
        error: Exception | None = None
        status_code = 500
        
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
            
        except Exception as e:
            error = e
            status_code = getattr(e, "status_code", 500)
            raise
            
        finally:
            # Finalize and emit the wide event
            event = finalize_request_event(status_code, error)
            emit_wide_event(event)
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, respecting proxy headers."""
        # Check forwarded headers (reverse proxy)
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fall back to direct connection
        if request.client:
            return request.client.host
        
        return "unknown"


def add_user_to_wide_event(
    user_id: str | None = None,
    email: str | None = None,
    roles: list[str] | None = None,
    is_admin: bool = False,
) -> None:
    """
    Add authenticated user context to the wide event.
    
    Call this from your auth dependency after token validation:
    
        @router.get("/protected")
        async def protected(user: User = Depends(get_current_user)):
            add_user_to_wide_event(
                user_id=user.sub,
                email=user.email,
                roles=user.roles,
                is_admin="ADMIN" in user.roles,
            )
    """
    enrich_event(
        user={
            "id": user_id,
            "email": email,
            "roles": roles or [],
            "is_admin": is_admin,
        }
    )


def add_dno_to_wide_event(
    dno_id: int | str | None = None,
    dno_name: str | None = None,
    dno_status: str | None = None,
) -> None:
    """Add DNO context to the wide event."""
    enrich_event(
        dno={
            "id": dno_id,
            "name": dno_name,
            "status": dno_status,
        }
    )


def add_job_to_wide_event(
    job_id: int | str | None = None,
    job_type: str | None = None,
    job_status: str | None = None,
    data_type: str | None = None,
    year: int | None = None,
) -> None:
    """Add job context to the wide event."""
    enrich_event(
        job={
            "id": job_id,
            "type": job_type,
            "status": job_status,
            "data_type": data_type,
            "year": year,
        }
    )
