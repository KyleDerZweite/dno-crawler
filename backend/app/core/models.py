"""
Core models and types for DNO Crawler.

Cleaned up - removed unused Pydantic models (auth handled by Zitadel).
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# Enums (used by db/models.py)
# =============================================================================


class UserRole(str, Enum):
    PENDING = "pending"
    USER = "user"
    ADMIN = "admin"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DataType(str, Enum):
    NETZENTGELTE = "netzentgelte"
    HLZF = "hlzf"
    ALL = "all"


class Season(str, Enum):
    WINTER = "winter"
    SPRING = "fruehling"
    SUMMER = "sommer"
    AUTUMN = "herbst"


class ContentFormat(str, Enum):
    HTML = "html"
    PDF = "pdf"
    IMAGE = "image"
    TABLE = "table"
    API = "api"


class VerificationStatus(str, Enum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    REJECTED = "rejected"


class DNOStatus(str, Enum):
    """DNO crawl status."""
    UNCRAWLED = "uncrawled"
    CRAWLING = "crawling"
    CRAWLED = "crawled"
    FAILED = "failed"


# =============================================================================
# Base Models
# =============================================================================


class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    model_config = ConfigDict(from_attributes=True)


class TimestampMixin(BaseModel):
    """Mixin for created/updated timestamps."""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime | None = None


# =============================================================================
# Crawl Job Models (used by dnos.py)
# =============================================================================


class CrawlJobBase(BaseSchema):
    dno_id: UUID
    year: int
    data_type: DataType


class CrawlJobCreate(CrawlJobBase):
    priority: int = Field(5, ge=1, le=10)


class CrawlJob(CrawlJobBase, TimestampMixin):
    id: UUID
    user_id: UUID | None = None
    status: JobStatus = JobStatus.PENDING
    progress: int = Field(0, ge=0, le=100)
    current_step: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


# =============================================================================
# API Response Models (used by admin.py, dnos.py)
# =============================================================================


class APIResponse(BaseSchema):
    success: bool = True
    message: str | None = None
    data: Any = None
    meta: dict[str, Any] | None = None


class PaginatedResponse(APIResponse):
    meta: dict[str, Any] = Field(
        default_factory=lambda: {
            "total": 0,
            "page": 1,
            "per_page": 20,
            "total_pages": 0,
        }
    )
