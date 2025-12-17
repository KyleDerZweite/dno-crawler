"""
SQLAlchemy ORM models for DNO Crawler.
"""

from datetime import datetime
from decimal import Decimal
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
    Numeric,
    String,
    Text,
    Time,
)
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.models import (
    ContentFormat,
    DataType,
    JobStatus,
    Season,
    VerificationStatus,
)
from app.db.database import Base


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

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    official_name: Mapped[str | None] = mapped_column(String(255))
    
    # VNB Digital integration
    vnb_id: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="uncrawled", index=True)  # uncrawled | crawling | crawled | failed
    crawl_locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # For stuck job recovery
    
    description: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(String(255), index=True)
    website: Mapped[str | None] = mapped_column(String(500))

    # Relationships
    netzentgelte: Mapped[list["NetzentgelteModel"]] = relationship(back_populates="dno")
    hlzf: Mapped[list["HLZFModel"]] = relationship(back_populates="dno")
    crawl_configs: Mapped[list["DNOCrawlConfigModel"]] = relationship(back_populates="dno")
    strategies: Mapped[list["ExtractionStrategyModel"]] = relationship(back_populates="dno")
    locations: Mapped[list["LocationModel"]] = relationship(back_populates="dno")


class LocationModel(Base, TimestampMixin):
    """Geographic location linked to a DNO.
    
    Enables efficient lookups:
    - Address → (address_hash) → DNO
    - (lat, lon) → DNO (with spatial tolerance)
    
    Uses Numeric(9,6) for coordinates = ~11cm precision with exact matching.
    """
    __tablename__ = "locations"
    __table_args__ = (
        Index("idx_locations_geocoord", "latitude", "longitude"),
        Index("idx_locations_address_hash", "address_hash"),
        Index("idx_locations_zip", "zip_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dno_id: Mapped[int] = mapped_column(Integer, ForeignKey("dnos.id", ondelete="CASCADE"), index=True)
    
    # Hash for uniqueness (mashed string: "anderronne|160|12345")
    address_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    
    # Clean components for storage/API calls
    street_clean: Mapped[str] = mapped_column(String(255), nullable=False)  # "An der Ronne"
    number_clean: Mapped[str | None] = mapped_column(String(20))            # "160"
    zip_code: Mapped[str] = mapped_column(String(10), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Coordinates: Numeric(9,6) for exact matching (~11cm precision)
    latitude: Mapped["Decimal"] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped["Decimal"] = mapped_column(Numeric(9, 6), nullable=False)
    
    # Metadata
    source: Mapped[str] = mapped_column(String(50), default="vnb_digital")
    
    # Relationships
    dno: Mapped["DNOModel"] = relationship(back_populates="locations")


class DNOAddressCacheModel(Base, TimestampMixin):
    """Legacy cache for address → coordinates + DNO mappings.
    
    DEPRECATED: Use LocationModel instead. Kept for backwards compatibility.
    """
    __tablename__ = "dno_address_cache"
    __table_args__ = (
        Index("idx_dno_address_cache_lookup", "zip_code", "street_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    zip_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    street_name: Mapped[str] = mapped_column(String(255), nullable=False)  # Normalized
    
    # Geocoding result
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    
    # DNO resolution result
    dno_name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Metadata
    source: Mapped[str | None] = mapped_column(String(50))  # "vnb_digital", "manual", etc.


class DNOCrawlConfigModel(Base, TimestampMixin):
    """Crawl configuration for a DNO."""
    __tablename__ = "dno_crawl_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dno_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dnos.id", ondelete="CASCADE"), unique=True
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
    __tablename__ = "netzentgelte"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dno_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dnos.id", ondelete="CASCADE")
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
    # Note: verified_by kept for audit trail but FK removed (users in Zitadel)
    verified_by: Mapped[int | None] = mapped_column(Integer)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    dno: Mapped["DNOModel"] = relationship(back_populates="netzentgelte")


class HLZFModel(Base, TimestampMixin):
    """HLZF (Hochlastzeitfenster) data per voltage level and season.
    
    Structure based on Netze BW format:
    - Rows: Voltage levels (Hochspannungsnetz, Umspannung HS/MS, etc.)
    - Columns: Seasons (Winter, Frühling, Sommer, Herbst)
    - Values: Time windows like "07:30-15:30\n17:15-19:15" or "entfällt"
    """
    __tablename__ = "hlzf"
    __table_args__ = (
        Index("idx_hlzf_dno_year_voltage", "dno_id", "year", "voltage_level"),
    )
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dno_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dnos.id", ondelete="CASCADE")
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    voltage_level: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Seasonal time windows (can contain multiple lines like "07:30-15:30\n17:15-19:15")
    # "entfällt" or null means no HLZF for that season
    winter: Mapped[str | None] = mapped_column(Text)  # Jan, Feb, Dez
    fruehling: Mapped[str | None] = mapped_column(Text)  # Mrz - Mai
    sommer: Mapped[str | None] = mapped_column(Text)  # Jun - Aug
    herbst: Mapped[str | None] = mapped_column(Text)  # Sept - Nov

    # Verification
    verification_status: Mapped[str] = mapped_column(
        String(20), default=VerificationStatus.UNVERIFIED.value
    )
    # Note: verified_by kept for audit trail but FK removed (users in Zitadel)
    verified_by: Mapped[int | None] = mapped_column(Integer)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    dno: Mapped["DNOModel"] = relationship(back_populates="hlzf")


class DataSourceModel(Base, TimestampMixin):
    """Tracking where data came from."""

    __tablename__ = "data_sources"
    __table_args__ = (
        Index("idx_data_sources_dno_year", "dno_id", "year"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dno_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dnos.id", ondelete="CASCADE")
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


# ============== Crawl & Job Tables ==============


class CrawlJobModel(Base, TimestampMixin):
    """Crawl job tracking."""

    __tablename__ = "crawl_jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Note: user_id kept for audit trail but FK removed (users in Zitadel)
    user_id: Mapped[int | None] = mapped_column(Integer)
    dno_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dnos.id", ondelete="CASCADE")
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    data_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=JobStatus.PENDING.value)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    current_step: Mapped[str | None] = mapped_column(String(255))
    error_message: Mapped[str | None] = mapped_column(Text)
    triggered_by: Mapped[str | None] = mapped_column(String(255))  # User email who triggered
    priority: Mapped[int] = mapped_column(Integer, default=5)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    steps: Mapped[list["CrawlJobStepModel"]] = relationship(back_populates="job")


class CrawlJobStepModel(Base, TimestampMixin):
    """Individual steps within a crawl job."""

    __tablename__ = "crawl_job_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("crawl_jobs.id", ondelete="CASCADE"), index=True
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dno_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("dnos.id", ondelete="CASCADE")
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
    dno_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dnos.id", ondelete="CASCADE")
    )
    strategy_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("extraction_strategies.id", ondelete="SET NULL")
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
    # Note: user_id kept for audit trail but FK removed (users in Zitadel)
    user_id: Mapped[int | None] = mapped_column(Integer)
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