"""
Core models and enums for DNO Crawler.

This module contains:
- Enums used by database models
- Pydantic schemas for API requests/responses
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ==============================================================================
# Enums
# ==============================================================================


class JobStatus(str, Enum):
    """Status of a crawl job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DataType(str, Enum):
    """Types of data to extract."""

    NETZENTGELTE = "netzentgelte"
    HLZF = "hlzf"
    ALL = "all"  # Both netzentgelte and hlzf


class UserRole(str, Enum):
    """User roles (for Zitadel integration)."""

    PENDING = "pending"
    USER = "user"
    MAINTAINER = "maintainer"  # Can manage data verification flags
    ADMIN = "admin"


class Season(str, Enum):
    """Seasons for HLZF data."""

    WINTER = "winter"
    SPRING = "fruehling"
    SUMMER = "sommer"
    AUTUMN = "herbst"


class ContentFormat(str, Enum):
    """Content format types."""

    HTML = "html"
    PDF = "pdf"
    IMAGE = "image"
    TABLE = "table"
    API = "api"


class DNOStatus(str, Enum):
    """DNO crawl status."""

    UNCRAWLED = "uncrawled"
    CRAWLING = "crawling"
    CRAWLED = "crawled"
    FAILED = "failed"


class EnrichmentStatus(str, Enum):
    """DNO enrichment status (for background data enrichment)."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DNOSource(str, Enum):
    """How the DNO record was created."""

    SEED = "seed"  # From MaStR seed data
    USER_DISCOVERY = "user_discovery"  # Created via user search/skeleton service


class SourceFormat(str, Enum):
    """Source document formats."""

    PDF = "pdf"
    XLSX = "xlsx"
    XLS = "xls"
    DOCX = "docx"
    HTML = "html"
    CSV = "csv"
    IMAGE = "image"
    PPTX = "pptx"


class VerificationStatus(str, Enum):
    """Verification status of extracted data."""

    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    REJECTED = "rejected"
    FLAGGED = "flagged"  # User reported as potentially incorrect


class CrawlStrategy(str, Enum):
    """Strategy for finding data."""

    USE_CACHE = "use_cache"  # File already downloaded locally
    EXACT_URL = "exact_url"  # Known URL from previous crawl
    PATTERN_MATCH = "pattern_match"  # Learned path pattern worked
    BFS_CRAWL = "bfs_crawl"  # Full BFS website crawl


class AIProvider(str, Enum):
    """Supported AI providers for extraction."""

    GEMINI = "gemini"  # Google Gemini (gemini-2.0-flash, gemini-1.5-pro)
    OPENAI = "openai"  # OpenAI GPT-4 Vision (gpt-4o, gpt-4-turbo)
    ANTHROPIC = "anthropic"  # Anthropic Claude (claude-3-5-sonnet)
    OLLAMA = "ollama"  # Local Ollama (llava, bakllava)


# ==============================================================================
# Base Schemas
# ==============================================================================


class BaseSchema(BaseModel):
    """Base schema with ORM compatibility."""

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# API Response Models
# ==============================================================================


class APIResponse(BaseSchema):
    """Standard API response wrapper."""

    success: bool = True
    message: str | None = None
    data: Any = None
    meta: dict[str, Any] | None = None


class PaginatedResponse(APIResponse):
    """Paginated API response."""

    meta: dict[str, Any] = Field(
        default_factory=lambda: {
            "total": 0,
            "page": 1,
            "per_page": 20,
            "total_pages": 0,
        }
    )


# ==============================================================================
# Crawl Job Schemas
# ==============================================================================


class TimestampMixin(BaseModel):
    """Mixin for created/updated timestamps."""

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None


class CrawlJobBase(BaseSchema):
    """Base schema for crawl jobs."""

    dno_id: int
    year: int
    data_type: DataType


class CrawlJobCreate(CrawlJobBase):
    """Schema for creating a crawl job."""

    priority: int = Field(5, ge=1, le=10)


class CrawlJob(CrawlJobBase, TimestampMixin):
    """Full crawl job schema."""

    id: int
    status: JobStatus = JobStatus.PENDING
    progress: int = Field(0, ge=0, le=100)
    current_step: str | None = None
    error_message: str | None = None
    triggered_by: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


# ==============================================================================
# Job Context (Shared Between Steps)
# ==============================================================================


class JobContext(BaseSchema):
    """
    Context passed between crawl job steps.

    Stored in CrawlJobModel.context as JSON.
    """

    # DNO info (loaded in step_00)
    dno_id: int
    dno_slug: str
    dno_name: str
    dno_website: str | None = None

    # Source profile (if exists)
    has_profile: bool = False
    profile_url_pattern: str | None = None
    profile_source_format: str | None = None

    # Cached file path (if exists)
    cached_file: str | None = None

    # Strategy (set in step_01)
    strategy: str = "bfs_crawl"  # use_cache | exact_url | pattern_match | bfs_crawl

    # Discovery (set in step_01)
    found_url: str | None = None
    found_content_type: str | None = None
    discovered_via_pattern: str | None = None  # Which pattern found it
    pages_crawled: int = 0  # For metrics
    needs_headless_review: bool = False  # JS/SPA detection flag

    # Downloaded file (set in step_03)
    downloaded_file: str | None = None
    file_format: str | None = None

    # Extraction results (set in step_04)
    extracted_data: list[dict] | None = None
    extraction_notes: str | None = None
    extraction_confidence: float = 0.0

    # Validation (set in step_05)
    is_valid: bool = False
    validation_issues: list[str] = Field(default_factory=list)


# ==============================================================================
# Extraction Result Models
# ==============================================================================


class ExtractionResult(BaseSchema):
    """Result from Gemini extraction."""

    success: bool
    data_type: str
    source_page: int | None = None
    notes: str | None = None
    data: list[dict] = Field(default_factory=list)
    reason: str | None = None  # If success=False


class NetzentgelteRecord(BaseSchema):
    """Single Netzentgelte record from extraction."""

    voltage_level: str
    arbeitspreis: float | None = None
    leistungspreis: float | None = None


class HLZFRecord(BaseSchema):
    """Single HLZF record from extraction."""

    voltage_level: str
    winter: str | None = None
    fruehling: str | None = None
    sommer: str | None = None
    herbst: str | None = None
