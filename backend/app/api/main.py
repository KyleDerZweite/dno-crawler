"""
FastAPI application factory and main entry point.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.middleware import WideEventMiddleware
from app.api.routes import admin, auth, dnos, files, health, jobs, oauth, search, verification
from app.core.config import settings
from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DNOCrawlerException,
    ExternalServiceError,
    RateLimitError,
    ResourceNotFoundError,
)
from app.core.logging import configure_logging
from app.db import DatabaseError, close_db, init_db

# Configure structured logging with wide events support
configure_logging(
    json_logs=not settings.debug,  # JSON in production, console in dev
    log_level="DEBUG" if settings.debug else "INFO",
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Startup
    logger.info("Starting DNO Crawler API", version=settings.app_version)
    await init_db()
    logger.info("Database initialized")

    # Initialize rate limiter if Redis available
    try:
        from redis.asyncio import Redis

        from app.core.rate_limiter import init_rate_limiter
        from app.db import get_db_session
        from app.services.crawl_recovery import recover_stuck_crawl_jobs

        redis = Redis.from_url(str(settings.redis_url))
        init_rate_limiter(redis)
        logger.info("Rate limiter initialized")

        # Warn if CONTACT_EMAIL not configured (important for crawler politeness)
        if not settings.has_contact_email:
            if settings.is_auth_enabled:
                logger.warning(
                    "⚠️  CONTACT_EMAIL not configured! "
                    "BFS crawling will FAIL in production mode. "
                    "Set CONTACT_EMAIL in .env to enable full crawling."
                )
            else:
                logger.warning(
                    "⚠️  CONTACT_EMAIL not configured. "
                    "BFS crawling will use initiator IP as fallback. "
                    "Set CONTACT_EMAIL in .env for production use."
                )

        # Recover stuck crawl jobs
        async with get_db_session() as db:
            recovered = await recover_stuck_crawl_jobs(db)
            if recovered > 0:
                logger.info("Recovered stuck crawl jobs", count=recovered)
    except Exception as e:
        logger.warning("Could not initialize rate limiter or recovery", error=str(e))

    yield

    # Shutdown
    logger.info("Shutting down DNO Crawler API")
    await close_db()
    logger.info("Database connections closed")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="AI-powered German DNO data extraction system",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Wide Events middleware - canonical log line per request
    app.add_middleware(WideEventMiddleware)

    # Include routers - order matters for route matching
    app.include_router(health.router, tags=["Health"])
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
    app.include_router(files.router, prefix="/api/v1/files", tags=["Files"])
    app.include_router(search.router, prefix="/api/v1/search", tags=["Search"])  # Public search (skeleton creation)
    app.include_router(dnos.router, prefix="/api/v1/dnos", tags=["DNOs"])  # Authenticated DNO management
    app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["Jobs"])  # Job management
    app.include_router(verification.router, prefix="/api/v1/verification", tags=["Verification"])  # Data verification
    app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
    app.include_router(oauth.router, prefix="/api/v1/admin", tags=["OAuth"])  # OAuth under admin

    # Exception Handlers
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle FastAPI validation errors"""
        logger.warning("Validation error", url=str(request.url), errors=exc.errors())
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "message": "Validation failed",
                    "type": "validation_error",
                    "details": exc.errors()
                }
            }
        )

    @app.exception_handler(DatabaseError)
    async def database_exception_handler(request: Request, exc: DatabaseError):
        """Handle database errors"""
        logger.error("Database error", url=str(request.url), error=exc.message, exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Database operation failed"
            }
        )

    @app.exception_handler(AuthenticationError)
    async def authentication_exception_handler(request: Request, exc: AuthenticationError):
        """Handle authentication errors"""
        logger.warning("Authentication error", url=str(request.url), message=exc.message)
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "message": exc.message,
                    "type": "authentication_error",
                    "details": exc.details
                }
            }
        )

    @app.exception_handler(AuthorizationError)
    async def authorization_exception_handler(request: Request, exc: AuthorizationError):
        """Handle authorization errors"""
        logger.warning("Authorization error", url=str(request.url), message=exc.message)
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "message": exc.message,
                    "type": "authorization_error",
                    "details": exc.details
                }
            }
        )

    @app.exception_handler(ResourceNotFoundError)
    async def not_found_exception_handler(request: Request, exc: ResourceNotFoundError):
        """Handle not found errors"""
        logger.info("Resource not found", url=str(request.url), message=exc.message)
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "message": exc.message,
                    "type": "not_found_error",
                    "details": exc.details
                }
            }
        )

    @app.exception_handler(ConflictError)
    async def conflict_exception_handler(request: Request, exc: ConflictError):
        """Handle conflict errors"""
        logger.warning("Conflict error", url=str(request.url), message=exc.message)
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "message": exc.message,
                    "type": "conflict_error",
                    "details": exc.details
                }
            }
        )

    @app.exception_handler(RateLimitError)
    async def rate_limit_exception_handler(request: Request, exc: RateLimitError):
        """Handle rate limit errors"""
        logger.warning("Rate limit exceeded", url=str(request.url), message=exc.message)
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "message": exc.message,
                    "type": "rate_limit_error",
                    "details": exc.details
                }
            }
        )

    @app.exception_handler(ExternalServiceError)
    async def external_service_exception_handler(request: Request, exc: ExternalServiceError):
        """Handle external service errors"""
        logger.error("External service error", url=str(request.url), message=exc.message)
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "message": exc.message,
                    "type": "external_service_error",
                    "details": exc.details
                }
            }
        )

    @app.exception_handler(DNOCrawlerException)
    async def app_exception_handler(request: Request, exc: DNOCrawlerException):
        """Handle custom app exceptions"""
        logger.error("App error", url=str(request.url), message=exc.message)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "message": exc.message,
                    "type": "application_error",
                    "details": exc.details
                }
            }
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions"""
        logger.error("Unexpected error", url=str(request.url), error=str(exc), exc_info=True)

        # Don't expose internal details in production
        message = str(exc) if settings.debug else "An unexpected error occurred"

        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "message": message,
                    "type": "internal_server_error"
                }
            }
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
