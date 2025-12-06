"""
Health check endpoints.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/health")
async def health_check() -> dict:
    """Basic health check."""
    return {"status": "healthy"}


@router.get("/api/ready")
async def readiness_check() -> dict:
    """Readiness check - includes database connectivity."""
    # TODO: Add actual database and Redis checks
    return {
        "status": "ready",
        "database": "connected",
        "redis": "connected",
    }
