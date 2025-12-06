import structlog
from arq.connections import RedisSettings

from src.core.config import settings
from src.db import close_db, init_db

logger = structlog.get_logger()

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
    functions = []  # Register job functions here
    redis_settings = RedisSettings.from_dsn(str(settings.redis_url))
    on_startup = startup
    on_shutdown = shutdown
    handle_signals = False 
