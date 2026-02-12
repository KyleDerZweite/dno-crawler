"""
Database connection and session management.
"""

from collections.abc import AsyncGenerator

import structlog
from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = structlog.get_logger()


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""

    pass


class DatabaseError(Exception):
    """Custom database error for better error handling"""
    def __init__(self, message: str, original_error: Exception | None = None):
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)


# Create async engine
try:
    engine = create_async_engine(
        str(settings.database_url),
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        echo=settings.debug,
        pool_pre_ping=True,
        pool_recycle=3600,
        # Connection timeout settings
        connect_args={
            "command_timeout": 60,
            "server_settings": {
                "application_name": settings.app_name.lower().replace(" ", "_"),
                "jit": "off"
            }
        }
    )
    logger.info("Database engine created successfully")
except Exception as e:
    logger.error("Failed to create database engine", error=str(e))
    raise

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session with proper error handling."""
    session = None
    try:
        session = async_session_maker()
        yield session
    except OperationalError as e:
        logger.error("Database operational error", error=str(e))
        if session:
            await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed. Please try again later."
        ) from e
    except SQLAlchemyError as e:
        logger.error("Database error", error=str(e))
        if session:
            await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed"
        ) from e
    except Exception as e:
        # Don't catch application-level exceptions that should be handled by global handlers
        from fastapi.exceptions import HTTPException as FastAPIHTTPException

        from app.core.exceptions import DNOCrawlerException

        if isinstance(e, (DNOCrawlerException, FastAPIHTTPException)):
            if session:
                await session.rollback()
            raise  # Re-raise to let global exception handlers handle it

        logger.error("Unexpected database error", error=str(e))
        if session:
            await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again later."
        ) from e
    finally:
        if session:
            await session.close()


from contextlib import asynccontextmanager  # noqa: E402


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for getting database session in non-FastAPI contexts.

    Useful for background workers and standalone scripts.
    """
    session = async_session_maker()
    try:
        yield session
    except SQLAlchemyError as e:
        logger.error("Database error in session", error=str(e))
        await session.rollback()
        raise DatabaseError(f"Database operation failed: {e}", original_error=e) from e
    finally:
        await session.close()


async def init_db() -> None:
    """Initialize database tables.

    Handles concurrent startup of multiple workers safely by:
    1. Using checkfirst=True to avoid creating existing objects
    2. Catching duplicate key errors (race condition between check and create)

    If another worker creates tables between our check and create, we catch
    the error and continue - the tables exist, which is what we wanted.
    """
    try:
        async with engine.begin() as conn:
            # Enable extensions
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
            await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, checkfirst=True))
        logger.info("Database tables initialized")
    except Exception as e:
        error_str = str(e)
        # Race condition: another worker created tables/extensions between our check and create
        # This is fine - tables/extensions exist now, which is what we wanted
        race_condition_constraints = ["pg_type_typname_nsp_index", "pg_extension_name_index"]
        if "duplicate key value violates unique constraint" in error_str and any(
            constraint in error_str for constraint in race_condition_constraints
        ):
            logger.info("Database tables/extensions already created by another worker")
        else:
            logger.error("Failed to initialize database", error=error_str)
            raise


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()


async def check_database_health() -> bool:
    """Check database connectivity and health"""
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        return False
