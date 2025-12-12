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
# Legacy crawl jobs (to be deprecated) - still from old location for compatibility
from app.worker.jobs import crawl_dno_job, discover_sources_job, extract_pdf_job

# New search job from this package
from app.jobs.search_job import job_process_search_request


class WorkerSettings:
    """ARQ worker settings."""
    
    functions = [
        health_check_job,
        crawl_dno_job,
        discover_sources_job,
        extract_pdf_job,
        job_process_search_request,
    ]
    redis_settings = RedisSettings.from_dsn(str(settings.redis_url))
    on_startup = startup
    on_shutdown = shutdown
    handle_signals = False
    
    # CRITICAL: Only process one search job at a time.
    # This forces the queue to be strictly sequential.
    max_jobs = 1
