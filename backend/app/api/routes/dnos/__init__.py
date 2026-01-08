"""
DNO routes package.

This package contains decomposed DNO management routes:
- schemas.py: Pydantic request/response models
- utils.py: Shared utility functions
- crud.py: CRUD operations (create, read, update, delete DNO)
- crawl.py: Crawl and job-related endpoints
- data.py: Netzentgelte/HLZF data endpoints
- files.py: File upload/download operations
- import_export.py: Data import/export functionality
"""

from fastapi import APIRouter

from .crud import router as crud_router
from .crawl import router as crawl_router
from .data import router as data_router
from .files import router as files_router
from .import_export import router as import_export_router


# Create main router that combines all sub-routers
router = APIRouter()

# Include all sub-routers
# Note: Order matters for route matching - more specific routes first
router.include_router(crud_router)  # Basic CRUD operations
router.include_router(crawl_router)  # Crawl/job operations
router.include_router(data_router)  # Data operations
router.include_router(files_router)  # File operations
router.include_router(import_export_router)  # Import/export operations


__all__ = ["router"]
