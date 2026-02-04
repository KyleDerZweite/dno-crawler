"""
Jobs layer for ARQ worker orchestration.

This package contains the ARQ worker configuration and job functions
that orchestrate the services layer.

Architecture:
- CrawlWorkerSettings: Dedicated single worker for crawling (steps 0-3)
  - Ensures polite crawling with no parallel requests to same domain
  - Listens on "crawl" queue

- ExtractWorkerSettings: Worker(s) for extraction (steps 4-6)
  - Can be scaled horizontally since no external requests
  - Listens on "extract" queue

- WorkerSettings: Legacy combined worker (for backwards compatibility)
  - Runs full pipeline (all steps)
  - Listens on default queue
"""

import structlog
from arq.connections import RedisSettings

from app.core.config import settings
from app.db import close_db, get_db_session, init_db
from app.db.seeder import seed_dnos

logger = structlog.get_logger()


async def health_check_job(ctx) -> str:
    """Placeholder health check job."""
    logger.info("Worker health check job executed")
    return "ok"


async def startup_with_seeding(ctx):
    """Initialize the worker context with database seeding (crawl worker only)."""
    logger.info("Starting up worker (with seeding)...")
    await init_db()

    # Seed the database with DNO data
    logger.info("Running database seeder...")
    async with get_db_session() as db:
        try:
            inserted, updated, skipped = await seed_dnos(db)
            logger.info(
                "Database seeding complete",
                inserted=inserted,
                updated=updated,
                skipped=skipped,
            )
        except Exception as e:
            logger.error("Database seeding failed", error=str(e))
            # Don't fail startup on seeding errors

    logger.info("Worker startup complete.")


async def startup_simple(ctx):
    """Initialize the worker context without seeding (extract worker)."""
    logger.info("Starting up worker (simple)...")
    await init_db()
    logger.info("Worker startup complete.")


async def shutdown(ctx):
    """Cleanup the worker context."""
    logger.info("Shutting down worker...")
    await close_db()
    logger.info("Worker shutdown complete.")


# Import job functions
from app.jobs.crawl_job import process_crawl  # noqa: E402
from app.jobs.enrichment_job import enrich_dno  # noqa: E402
from app.jobs.extract_job import process_extract  # noqa: E402
from app.jobs.search_job import process_dno_crawl  # noqa: E402


class CrawlWorkerSettings:
    """
    ARQ worker settings for CRAWL jobs (steps 0-3).

    This worker handles:
    - Step 00: Gather Context
    - Step 01: Discover (BFS crawl)
    - Step 03: Download

    IMPORTANT: Only run ONE crawl worker to ensure polite crawling!
    """

    functions = [
        health_check_job,
        process_crawl,
        enrich_dno,  # Enrichment is also I/O bound, run on crawl worker
    ]
    redis_settings = RedisSettings.from_dsn(str(settings.redis_url))
    queue_name = "crawl"  # Listen on dedicated crawl queue
    on_startup = startup_with_seeding
    on_shutdown = shutdown
    handle_signals = False

    # CRITICAL: Only process one job at a time for polite crawling
    max_jobs = 1

    # Job timeout: 10 minutes for crawl jobs (BFS crawling can take time)
    # Prevents jobs from hanging indefinitely
    job_timeout = 600


class ExtractWorkerSettings:
    """
    ARQ worker settings for EXTRACT jobs (steps 4-6).

    This worker handles:
    - Step 04: Extract (regex + AI)
    - Step 05: Validate
    - Step 06: Finalize

    Can run multiple extract workers safely since no external HTTP requests.
    """

    functions = [
        health_check_job,
        process_extract,
    ]
    redis_settings = RedisSettings.from_dsn(str(settings.redis_url))
    queue_name = "extract"  # Listen on dedicated extract queue
    on_startup = startup_simple
    on_shutdown = shutdown
    handle_signals = False

    # Can process multiple jobs (no external requests)
    # Start with 1, can increase if needed
    max_jobs = 1

    # Job timeout: 5 minutes for extract jobs (AI extraction)
    job_timeout = 300


class WorkerSettings:
    """
    Legacy ARQ worker settings - runs FULL pipeline.

    For backwards compatibility. Runs all steps (0-6) in sequence.
    Use this if you want a single combined worker.
    """

    functions = [
        health_check_job,
        process_dno_crawl,  # Full pipeline
        enrich_dno,
    ]
    redis_settings = RedisSettings.from_dsn(str(settings.redis_url))
    on_startup = startup_with_seeding
    on_shutdown = shutdown
    handle_signals = False

    # Only process one job at a time
    max_jobs = 1

    # Job timeout: 15 minutes for full pipeline
    job_timeout = 900
