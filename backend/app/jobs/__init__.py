"""
Jobs layer for ARQ worker orchestration.

This package contains the ARQ worker configuration and job functions
that orchestrate the services layer.
"""

import structlog
from arq.connections import RedisSettings

from app.core.config import settings
from app.db import close_db, init_db, get_db
from app.db.seeder import seed_dnos

logger = structlog.get_logger()


async def health_check_job(ctx) -> str:
    """Placeholder health check job."""
    logger.info("Worker health check job executed")
    return "ok"


async def startup(ctx):
    """Initialize the worker context."""
    logger.info("Starting up worker...")
    await init_db()
    
    # Seed the database with DNO data
    logger.info("Running database seeder...")
    async for db in get_db():
        try:
            inserted, updated, skipped = await seed_dnos(db)
            logger.info(
                "Database seeding complete",
                inserted=inserted,
                updated=updated,
                skipped=skipped
            )
        except Exception as e:
            logger.error("Database seeding failed", error=str(e))
            # Don't fail startup on seeding errors
    
    logger.info("Worker startup complete.")


async def shutdown(ctx):
    """Cleanup the worker context."""
    logger.info("Shutting down worker...")
    await close_db()
    logger.info("Worker shutdown complete.")

# Import job functions
from app.jobs.search_job import process_dno_crawl
from app.jobs.enrichment_job import enrich_dno


class WorkerSettings:
    """ARQ worker settings."""
    
    functions = [
        health_check_job,
        process_dno_crawl,
        enrich_dno,
    ]
    redis_settings = RedisSettings.from_dsn(str(settings.redis_url))
    on_startup = startup
    on_shutdown = shutdown
    handle_signals = False
    
    # CRITICAL: Only process one search job at a time.
    # This forces the queue to be strictly sequential.
    max_jobs = 1
