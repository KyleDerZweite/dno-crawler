"""
Health check endpoints.
"""

import structlog
from fastapi import APIRouter
from redis.asyncio import Redis

from app.core.config import settings
from app.db.database import check_database_health

logger = structlog.get_logger()

router = APIRouter()


@router.get("/api/health")
async def health_check() -> dict:
    """Basic health check."""
    return {"status": "healthy"}


@router.get("/api/ready")
async def readiness_check() -> dict:
    """Readiness check - includes database and Redis connectivity."""
    db_ok = await check_database_health()

    redis_ok = False
    try:
        redis = Redis.from_url(str(settings.redis_url))
        try:
            await redis.ping()
            redis_ok = True
        finally:
            await redis.aclose()
    except Exception as e:
        logger.error("Redis health check failed", error=str(e))

    all_ok = db_ok and redis_ok

    return {
        "status": "ready" if all_ok else "degraded",
        "database": "connected" if db_ok else "unavailable",
        "redis": "connected" if redis_ok else "unavailable",
    }
