"""
Jobs layer for ARQ worker orchestration.

This package contains the ARQ worker configuration and job functions
that orchestrate the services layer.
"""

import structlog
from arq.connections import RedisSettings

from app.core.config import settings
from app.db import close_db, init_db

logger = structlog.get_logger()


async def health_check_job(ctx) -> str:
    """Placeholder health check job."""
    logger.info("Worker health check job executed")
    return "ok"


async def startup(ctx):
    """Initialize the worker context."""
    logger.info("Starting up worker...")
    await init_db()
    logger.info("Worker startup complete.")


async def shutdown(ctx):
    """Cleanup the worker context."""
    logger.info("Shutting down worker...")
    await close_db()
    logger.info("Worker shutdown complete.")

# Import job functions
from app.jobs.search_job import process_dno_crawl


class WorkerSettings:
    """ARQ worker settings."""
    
    functions = [
        health_check_job,
        process_dno_crawl,
    ]
    redis_settings = RedisSettings.from_dsn(str(settings.redis_url))
    on_startup = startup
    on_shutdown = shutdown
    handle_signals = False
    
    # CRITICAL: Only process one search job at a time.
    # This forces the queue to be strictly sequential.
    max_jobs = 1
