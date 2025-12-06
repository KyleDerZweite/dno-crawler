"""
FastAPI application factory and main entry point.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.routes import admin, auth, dnos, health, public
from src.core.config import settings
from src.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DNOCrawlerException,
    ExternalServiceError,
    RateLimitError,
    ResourceNotFoundError,
)
from src.db import DatabaseError, close_db, init_db
from src.db.database import async_session_maker
from sqlalchemy import select
from src.db.models import UserModel
from src.core.security import get_password_hash

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Startup
    logger.info("Starting DNO Crawler API", version=settings.app_version)
    await init_db()
    # Create an initial admin user from environment variables (if provided)
    try:
        if settings.admin_email and settings.admin_password:
            async with async_session_maker() as session:
                res = await session.execute(select(UserModel).where(UserModel.email == settings.admin_email))
                existing = res.scalar_one_or_none()
                if not existing:
                    admin_name = settings.admin_username or settings.admin_email
                    admin = UserModel(
                        email=settings.admin_email,
                        password_hash=get_password_hash(settings.admin_password),
                        name=admin_name,
                        role="admin",
                        is_active=True,
                        email_verified=True,
                    )
                    session.add(admin)
                    await session.commit()
                    logger.info("Created initial admin user from env", email=settings.admin_email)
                else:
                    logger.info("Admin user already exists, skipping creation", email=settings.admin_email)
    except Exception as e:
        logger.error("Failed to ensure initial admin user", error=str(e))
    logger.info("Database initialized")
    
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

    # Include routers
    app.include_router(health.router, tags=["Health"])
    app.include_router(public.router, prefix="/api/v1", tags=["Public"])
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
    app.include_router(dnos.router, prefix="/api/v1/dnos", tags=["DNOs"])
    app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])

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
        "src.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )