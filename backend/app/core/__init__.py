"""
Core package initialization.
"""

from app.core.config import Settings, get_settings, settings
from app.core.models import (
    APIResponse,
    ContentFormat,
    CrawlJob,
    CrawlJobCreate,
    DataType,
    DNOStatus,
    JobStatus,
    PaginatedResponse,
    Season,
    UserRole,
    VerificationStatus,
)

__all__ = [
    # Config
    "Settings",
    "get_settings",
    "settings",
    # Enums
    "UserRole",
    "JobStatus",
    "DataType",
    "Season",
    "ContentFormat",
    "VerificationStatus",
    "DNOStatus",
    # Models
    "CrawlJob",
    "CrawlJobCreate",
    "APIResponse",
    "PaginatedResponse",
]
