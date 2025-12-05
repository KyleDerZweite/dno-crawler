"""
SQLAlchemy ORM models for DNO Crawler.
"""

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
)
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.core.models import (
    ContentFormat,
    DataType,
    JobStatus,
    Season,
    UserRole,
    VerificationStatus,
)
from src.db.database import Base


class TimestampMixin:
    """Mixin for created_at and updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )


# ============== DNO Tables ==============


class DNOModel(Base, TimestampMixin):
    """Distribution Network Operator."""

    __tablename__ = "dnos"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    official_name: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(String(255), index=True)
    website: Mapped[str | None] = mapped_column(String(500))

    # Relationships
    netzentgelte: Mapped[list["NetzentgelteModel"]] = relationship(back_populates="dno")
    hlzf: Mapped[list["HLZFModel"]] = relationship(back_populates="dno")
    crawl_configs: Mapped[list["DNOCrawlConfigModel"]] = relationship(back_populates="dno")
    strategies: Mapped[list["ExtractionStrategyModel"]] = relationship(back_populates="dno")


class DNOCrawlConfigModel(Base, TimestampMixin):
    """Crawl configuration for a DNO."""

    __tablename__ = "dno_crawl_configs"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    dno_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dnos.id", ondelete="CASCADE"), unique=True
    )
    crawl_type: Mapped[str] = mapped_column(String(50))
    netzentgelte_source_url: Mapped[str | None] = mapped_column(Text)
    hlzf_source_url: Mapped[str | None] = mapped_column(Text)
    netzentgelte_file_pattern: Mapped[str | None] = mapped_column(Text)
    hlzf_file_pattern: Mapped[str | None] = mapped_column(Text)
    auto_crawl: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_crawl_interval: Mapped[str | None] = mapped_column(String(50))
    auto_crawl_years: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))

    # Relationships
    dno: Mapped["DNOModel"] = relationship(back_populates="crawl_configs")


# ============== Data Tables ==============


class NetzentgelteModel(Base, TimestampMixin):
    """Netzentgelte (network tariffs) data."""

    __tablename__ = "netzentgelte_data"
    __table_args__ = (
        Index("idx_netzentgelte_dno_year", "dno_id", "year"),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    dno_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dnos.id", ondelete="CASCADE")
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    voltage_level: Mapped[str] = mapped_column(String(10), nullable=False)
    leistung: Mapped[float | None] = mapped_column(Float)
    arbeit: Mapped[float | None] = mapped_column(Float)
    leistung_unter_2500h: Mapped[float | None] = mapped_column(Float)
    arbeit_unter_2500h: Mapped[float | None] = mapped_column(Float)

    # Verification
    verification_status: Mapped[str] = mapped_column(
        String(20), default=VerificationStatus.UNVERIFIED.value
    )
    verified_by: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    dno: Mapped["DNOModel"] = relationship(back_populates="netzentgelte")


class HLZFModel(Base, TimestampMixin):
    """HLZF (Hauptlastzeiten) data."""

    __tablename__ = "hlzf_data"
    __table_args__ = (
        Index("idx_hlzf_dno_year", "dno_id", "year"),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    dno_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dnos.id", ondelete="CASCADE")
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    season: Mapped[str] = mapped_column(String(20), nullable=False)
    period_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[str | None] = mapped_column(String(10))
    end_time: Mapped[str | None] = mapped_column(String(10))

    # Verification
    verification_status: Mapped[str] = mapped_column(
        String(20), default=VerificationStatus.UNVERIFIED.value
    )
    verified_by: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    dno: Mapped["DNOModel"] = relationship(back_populates="hlzf")


class DataSourceModel(Base, TimestampMixin):
    """Tracking where data came from."""

    __tablename__ = "data_sources"
    __table_args__ = (
        Index("idx_data_sources_dno_year", "dno_id", "year"),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    dno_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dnos.id", ondelete="CASCADE")
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    data_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    file_path: Mapped[str | None] = mapped_column(Text)
    file_hash: Mapped[str | None] = mapped_column(String(64))
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    extraction_method: Mapped[str | None] = mapped_column(String(50))
    extraction_region: Mapped[dict | None] = mapped_column(JSON)
    ocr_text: Mapped[str | None] = mapped_column(Text)


# ============== User Tables ==============


class UserModel(Base, TimestampMixin):
    """User account."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default=UserRole.PENDING.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_status: Mapped[str] = mapped_column(String(50), default="awaiting_approval")
    approved_by: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    sessions: Mapped[list["SessionModel"]] = relationship(back_populates="user")
    api_keys: Mapped[list["APIKeyModel"]] = relationship(back_populates="user")


class SessionModel(Base, TimestampMixin):
    """User session for JWT management."""

    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    refresh_token_hash: Mapped[str | None] = mapped_column(String(255), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    refresh_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_used: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped["UserModel"] = relationship(back_populates="sessions")


class APIKeyModel(Base, TimestampMixin):
    """API keys for programmatic access."""

    __tablename__ = "api_keys"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    masked_key: Mapped[str] = mapped_column(String(50), nullable=False)
    last_used: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    user: Mapped["UserModel"] = relationship(back_populates="api_keys")


# ============== Crawl & Job Tables ==============


class CrawlJobModel(Base, TimestampMixin):
    """Crawl job tracking."""

    __tablename__ = "crawl_jobs"
    __table_args__ = (
        Index("idx_crawl_jobs_dno_year", "dno_id", "year"),
        Index("idx_crawl_jobs_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    dno_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dnos.id", ondelete="CASCADE")
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    data_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=JobStatus.PENDING.value)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    current_step: Mapped[str | None] = mapped_column(String(255))
    error_message: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, default=5)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    steps: Mapped[list["CrawlJobStepModel"]] = relationship(back_populates="job")


class CrawlJobStepModel(Base, TimestampMixin):
    """Individual steps within a crawl job."""

    __tablename__ = "crawl_job_steps"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crawl_jobs.id", ondelete="CASCADE"), index=True
    )
    step_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=JobStatus.PENDING.value)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[dict | None] = mapped_column(JSON)

    # Relationships
    job: Mapped["CrawlJobModel"] = relationship(back_populates="steps")


# ============== Learning System Tables ==============


class ExtractionStrategyModel(Base, TimestampMixin):
    """Learned extraction strategies."""

    __tablename__ = "extraction_strategies"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    dno_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dnos.id", ondelete="CASCADE")
    )
    strategy_type: Mapped[str] = mapped_column(String(50), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    dno: Mapped["DNOModel | None"] = relationship(back_populates="strategies")


class CrawlAttemptModel(Base, TimestampMixin):
    """Record of crawl attempts for learning."""

    __tablename__ = "crawl_attempts"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    dno_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dnos.id", ondelete="CASCADE")
    )
    strategy_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("extraction_strategies.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    data_found: Mapped[dict | None] = mapped_column(JSON)
    error_details: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)


class StrategyInsightModel(Base, TimestampMixin):
    """Insights learned from crawling."""

    __tablename__ = "strategy_insights"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    insight_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    applies_to: Mapped[list[UUID] | None] = mapped_column(ARRAY(UUID(as_uuid=True)))
    confidence: Mapped[float] = mapped_column(Float, nullable=False)


# ============== Logging Tables ==============


class QueryLogModel(Base):
    """Log of user queries."""

    __tablename__ = "query_logs"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    interpreted_dno: Mapped[str | None] = mapped_column(String(255))
    interpreted_year: Mapped[int | None] = mapped_column(Integer)
    interpreted_data_type: Mapped[str | None] = mapped_column(String(20))
    confidence: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    response_time_ms: Mapped[int | None] = mapped_column(Integer)
    result_from_cache: Mapped[bool] = mapped_column(Boolean, default=False)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class SystemLogModel(Base):
    """System-level logs."""

    __tablename__ = "system_logs"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    level: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    service: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict | None] = mapped_column(JSON)
    trace_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
