"""
FastAPI application factory and main entry point.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import auth, dnos, health, public, admin
from src.core.config import settings
from src.db import close_db, init_db

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Startup
    logger.info("Starting DNO Crawler API", version=settings.app_version)
    await init_db()
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
