import structlog
from arq.connections import RedisSettings

from app.core.config import settings
from app.db import close_db, init_db
from app.worker.jobs import crawl_dno_job, discover_sources_job, extract_pdf_job
from app.worker.jobs.search_job import job_process_search_request

logger = structlog.get_logger()


async def health_check_job(ctx) -> str:
    """Placeholder health check job."""
    logger.info("Worker health check job executed")
    return "ok"


async def startup(ctx):
    """
    Initialize the worker context.
    """
    logger.info("Starting up worker...")
    await init_db()
    logger.info("Worker startup complete.")

async def shutdown(ctx):
    """
    Cleanup the worker context.
    """
    logger.info("Shutting down worker...")
    await close_db()
    logger.info("Worker shutdown complete.")

class WorkerSettings:
    """
    Arq worker settings.
    """
    functions = [
        health_check_job,
        crawl_dno_job,
        discover_sources_job,
        extract_pdf_job,
        job_process_search_request,  # New: SearchAgent job
    ]
    redis_settings = RedisSettings.from_dsn(str(settings.redis_url))
    on_startup = startup
    on_shutdown = shutdown
    handle_signals = False
    
    # CRITICAL: Only process one search job at a time.
    # This forces the queue to be strictly sequential.
    max_jobs = 1

