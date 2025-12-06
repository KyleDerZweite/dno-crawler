"""
Core models and types for DNO Crawler.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# Enums
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


# Base Models
class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(from_attributes=True)


class TimestampMixin(BaseModel):
    """Mixin for created/updated timestamps."""

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime | None = None


# DNO Models
class DNOBase(BaseSchema):
    slug: str = Field(..., description="URL-friendly identifier", examples=["netze-bw"])
    name: str = Field(..., description="Display name", examples=["Netze BW"])
    official_name: str | None = Field(None, examples=["Netze BW GmbH"])
    description: str | None = None
    region: str | None = Field(None, examples=["Baden-Württemberg"])
    website: str | None = Field(None, examples=["https://www.netze-bw.de"])


class DNOCreate(DNOBase):
    pass


class DNO(DNOBase, TimestampMixin):
    id: UUID


# Netzentgelte Models
class NetzentgelteBase(BaseSchema):
    year: int = Field(..., ge=2000, le=2100)
    voltage_level: str = Field(..., description="hs, hs/ms, ms, ms/ns, ns")
    leistung: float | None = Field(None, description="€/kW")
    arbeit: float | None = Field(None, description="ct/kWh")
    leistung_unter_2500h: float | None = None
    arbeit_unter_2500h: float | None = None


class NetzentgelteCreate(NetzentgelteBase):
    dno_id: UUID


class Netzentgelte(NetzentgelteBase, TimestampMixin):
    id: UUID
    dno_id: UUID
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    verified_by: UUID | None = None
    verified_at: datetime | None = None


# HLZF Models
class HLZFBase(BaseSchema):
    year: int = Field(..., ge=2000, le=2100)
    season: Season
    period_number: int = Field(..., ge=1, le=4)
    start_time: str | None = Field(None, examples=["08:00"])
    end_time: str | None = Field(None, examples=["12:00"])


class HLZFCreate(HLZFBase):
    dno_id: UUID


class HLZF(HLZFBase, TimestampMixin):
    id: UUID
    dno_id: UUID
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED


# User Models
class UserBase(BaseSchema):
    email: str
    name: str


class UserCreate(UserBase):
    password: str


class User(UserBase, TimestampMixin):
    id: UUID
    role: UserRole = UserRole.PENDING
    is_active: bool = True
    email_verified: bool = False


class UserInDB(User):
    password_hash: str


# Auth Models
class Token(BaseSchema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseSchema):
    sub: str  # user_id
    exp: datetime
    type: str  # "access" or "refresh"


# Strategy Models (for learning system)
class ExtractionStrategy(BaseSchema):
    id: UUID
    dno_id: UUID | None = None  # None = general strategy
    strategy_type: str  # "search", "parse", "extract"
    config: dict[str, Any]
    success_count: int = 0
    failure_count: int = 0
    last_used_at: datetime | None = None


class StrategyInsight(BaseSchema):
    id: UUID
    insight_type: str  # "pattern", "anti-pattern", "tip"
    description: str
    applies_to: list[UUID] = Field(default_factory=list)
    confidence: float = Field(..., ge=0, le=1)


# Crawl Job Models
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


# API Response Models
class APIResponse(BaseSchema):
    success: bool = True
    message: str | None = None
    data: Any = None


class PaginatedResponse(APIResponse):
    meta: dict[str, Any] = Field(
        default_factory=lambda: {
            "total": 0,
            "page": 1,
            "per_page": 20,
            "total_pages": 0,
        }
    )
