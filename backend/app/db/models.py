"""
SQLAlchemy ORM models for DNO Crawler.

Organized into sections:
- DNO & Location Tables
- Data Tables (Netzentgelte, HLZF)
- Source Profile (Discovery Learning)
- Crawl Job Tables
- Logging Tables
"""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.models import JobStatus, VerificationStatus
from app.db.database import Base


class TimestampMixin:
    """Mixin for created_at and updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )


# ==============================================================================
# DNO & Location Tables
# ==============================================================================


class DNOModel(Base, TimestampMixin):
    """Distribution Network Operator."""

    __tablename__ = "dnos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    official_name: Mapped[str | None] = mapped_column(String(255))
    
    # VNB Digital integration
    vnb_id: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)
    
    # Status tracking
    status: Mapped[str] = mapped_column(String(20), default="uncrawled", index=True)
    crawl_locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    
    # Basic info
    description: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(String(255), index=True)
    website: Mapped[str | None] = mapped_column(String(500))
    
    # Contact info (from VNBdigital)
    phone: Mapped[str | None] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(255))
    contact_address: Mapped[str | None] = mapped_column(String(500))
    
    # Crawlability info (from skeleton creation)
    robots_txt: Mapped[str | None] = mapped_column(Text)  # Full robots.txt content
    sitemap_urls: Mapped[dict | None] = mapped_column(JSON)  # URLs from robots.txt Sitemap: directives
    disallow_paths: Mapped[dict | None] = mapped_column(JSON)  # Paths from robots.txt Disallow:
    crawlable: Mapped[bool] = mapped_column(Boolean, default=True)  # False if Cloudflare/JS-protected
    crawl_blocked_reason: Mapped[str | None] = mapped_column(String(100))  # "cloudflare", "robots_disallow", etc.

    # Relationships
    netzentgelte: Mapped[list["NetzentgelteModel"]] = relationship(back_populates="dno")
    hlzf: Mapped[list["HLZFModel"]] = relationship(back_populates="dno")
    source_profiles: Mapped[list["DNOSourceProfile"]] = relationship(back_populates="dno")
    locations: Mapped[list["LocationModel"]] = relationship(back_populates="dno")


class LocationModel(Base, TimestampMixin):
    """Geographic location linked to a DNO.
    
    Enables efficient lookups:
    - Address → (address_hash) → DNO
    - (lat, lon) → DNO (with spatial tolerance)
    """
    __tablename__ = "locations"
    __table_args__ = (
        Index("idx_locations_geocoord", "latitude", "longitude"),
        Index("idx_locations_address_hash", "address_hash"),
        Index("idx_locations_zip", "zip_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dno_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dnos.id", ondelete="CASCADE"), index=True
    )
    
    # Hash for uniqueness
    address_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    
    # Address components
    street_clean: Mapped[str] = mapped_column(String(255), nullable=False)
    number_clean: Mapped[str | None] = mapped_column(String(20))
    zip_code: Mapped[str] = mapped_column(String(10), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Coordinates
    latitude: Mapped["Decimal"] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped["Decimal"] = mapped_column(Numeric(9, 6), nullable=False)
    
    source: Mapped[str] = mapped_column(String(50), default="vnb_digital")
    
    dno: Mapped["DNOModel"] = relationship(back_populates="locations")


# ==============================================================================
# Data Tables
# ==============================================================================


class NetzentgelteModel(Base, TimestampMixin):
    """Netzentgelte (network tariffs) data."""
    __tablename__ = "netzentgelte"
    __table_args__ = (
        Index("idx_netzentgelte_dno_year", "dno_id", "year"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dno_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dnos.id", ondelete="CASCADE")
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    voltage_level: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Prices (all in standard units: ct/kWh for arbeit, €/kW for leistung)
    arbeit: Mapped[float | None] = mapped_column(Float)  # Arbeitspreis ct/kWh
    leistung: Mapped[float | None] = mapped_column(Float)  # Leistungspreis €/kW
    
    # Optional: prices for < 2500h usage
    arbeit_unter_2500h: Mapped[float | None] = mapped_column(Float)
    leistung_unter_2500h: Mapped[float | None] = mapped_column(Float)

    # Verification
    verification_status: Mapped[str] = mapped_column(
        String(20), default=VerificationStatus.UNVERIFIED.value
    )
    verified_by: Mapped[str | None] = mapped_column(String(255))  # Zitadel user sub
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_notes: Mapped[str | None] = mapped_column(Text)
    
    # Flagging (when users report data as wrong)
    flagged_by: Mapped[str | None] = mapped_column(String(255))  # User sub who flagged
    flagged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    flag_reason: Mapped[str | None] = mapped_column(Text)  # Why it's flagged as wrong

    dno: Mapped["DNOModel"] = relationship(back_populates="netzentgelte")


class HLZFModel(Base, TimestampMixin):
    """HLZF (Hochlastzeitfenster) data per voltage level.
    
    Each row = one voltage level for one year.
    Columns = seasonal time windows.
    """
    __tablename__ = "hlzf"
    __table_args__ = (
        Index("idx_hlzf_dno_year", "dno_id", "year"),
    )
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dno_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dnos.id", ondelete="CASCADE")
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    voltage_level: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Time windows per season (e.g., "08:00-12:00, 17:00-20:00" or "entfällt")
    winter: Mapped[str | None] = mapped_column(Text)
    fruehling: Mapped[str | None] = mapped_column(Text)
    sommer: Mapped[str | None] = mapped_column(Text)
    herbst: Mapped[str | None] = mapped_column(Text)

    # Verification
    verification_status: Mapped[str] = mapped_column(
        String(20), default=VerificationStatus.UNVERIFIED.value
    )
    verified_by: Mapped[str | None] = mapped_column(String(255))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    
    # Flagging (when users report data as wrong)
    flagged_by: Mapped[str | None] = mapped_column(String(255))  # User sub who flagged
    flagged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    flag_reason: Mapped[str | None] = mapped_column(Text)  # Why it's flagged as wrong

    dno: Mapped["DNOModel"] = relationship(back_populates="hlzf")


class DataSourceModel(Base, TimestampMixin):
    """Provenance tracking: where did extracted data come from?"""

    __tablename__ = "data_sources"
    __table_args__ = (
        Index("idx_data_sources_dno_year", "dno_id", "year"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dno_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dnos.id", ondelete="CASCADE")
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    data_type: Mapped[str] = mapped_column(String(20), nullable=False)  # netzentgelte | hlzf
    
    # Source info
    source_url: Mapped[str | None] = mapped_column(Text)
    file_path: Mapped[str | None] = mapped_column(Text)  # Local cache path
    file_hash: Mapped[str | None] = mapped_column(String(64))
    source_format: Mapped[str | None] = mapped_column(String(20))  # pdf | xlsx | html
    
    # Extraction metadata
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    extraction_method: Mapped[str | None] = mapped_column(String(50))  # gemini | ollama | regex
    extraction_notes: Mapped[str | None] = mapped_column(Text)  # Gemini's notes about source
    confidence: Mapped[float | None] = mapped_column(Float)


# ==============================================================================
# Source Profile (Discovery Learning)
# ==============================================================================


class CrawlPathPatternModel(Base, TimestampMixin):
    """Cross-DNO learned URL path patterns with year placeholders.
    
    Stores patterns like '/veroeffentlichungen/{year}/' that are known to work
    across multiple DNOs. Higher success_rate patterns are tried first during crawls.
    """
    __tablename__ = "crawl_path_patterns"
    __table_args__ = (
        Index("idx_path_patterns_data_type", "data_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Pattern with {year} placeholder (e.g., "/downloads/{year}/strom/")
    path_pattern: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    data_type: Mapped[str] = mapped_column(String(20), nullable=False)  # netzentgelte | hlzf | both
    
    # Stats
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    
    # JSON for DB portability (not ARRAY - SQLite compatible)
    successful_dno_slugs: Mapped[dict | None] = mapped_column(JSON)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate for pattern prioritization."""
        total = self.success_count + self.fail_count
        return self.success_count / total if total > 0 else 0.0


class DNOSourceProfile(Base, TimestampMixin):
    """Remember where to find data for each DNO.
    
    This is the "learning" system - stores what worked for future crawls.
    One profile per (dno_id, data_type) pair.
    """
    __tablename__ = "dno_source_profiles"
    __table_args__ = (
        Index("idx_source_profile_dno_type", "dno_id", "data_type", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dno_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dnos.id", ondelete="CASCADE")
    )
    data_type: Mapped[str] = mapped_column(String(20), nullable=False)  # netzentgelte | hlzf
    
    # Discovery info
    source_domain: Mapped[str | None] = mapped_column(String(255))  # e.g., "westnetz.de"
    source_format: Mapped[str | None] = mapped_column(String(20))  # pdf | xlsx | html | docx
    
    # URL patterns for quick recrawl
    last_url: Mapped[str | None] = mapped_column(Text)  # Last successful URL
    url_pattern: Mapped[str | None] = mapped_column(Text)  # URL with {year} placeholder
    
    # How this source was discovered (pattern_match | bfs_crawl | exact_url)
    discovery_method: Mapped[str | None] = mapped_column(String(50))
    # Which path pattern found this source
    discovered_via_pattern: Mapped[str | None] = mapped_column(Text)
    
    # Extraction hints (for Gemini prompt context)
    extraction_hints: Mapped[dict | None] = mapped_column(JSON)
    # Examples:
    # {"page": 3, "table_name": "Preisblatt 1"}
    # {"sheet": "Niederspannung", "header_row": 4}
    # {"css_selector": "table.tariff-table"}
    
    # Tracking
    last_success_year: Mapped[int | None] = mapped_column(Integer)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    
    dno: Mapped["DNOModel"] = relationship(back_populates="source_profiles")


# ==============================================================================
# Crawl Job Tables
# ==============================================================================


class CrawlJobModel(Base, TimestampMixin):
    """Crawl job tracking."""

    __tablename__ = "crawl_jobs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dno_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dnos.id", ondelete="CASCADE")
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    data_type: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Status
    status: Mapped[str] = mapped_column(String(20), default=JobStatus.PENDING.value)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    current_step: Mapped[str | None] = mapped_column(String(255))
    error_message: Mapped[str | None] = mapped_column(Text)
    
    # Job context (shared state between steps)
    context: Mapped[dict | None] = mapped_column(JSON)
    
    # Trigger info
    triggered_by: Mapped[str | None] = mapped_column(String(255))
    priority: Mapped[int] = mapped_column(Integer, default=5)
    
    # Timestamps
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    steps: Mapped[list["CrawlJobStepModel"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


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
    
    # Step details (description while running, result when done)
    details: Mapped[dict | None] = mapped_column(JSON)

    job: Mapped["CrawlJobModel"] = relationship(back_populates="steps")


# ==============================================================================
# Logging Tables
# ==============================================================================


class QueryLogModel(Base):
    """Log of user search queries."""

    __tablename__ = "query_logs"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[str | None] = mapped_column(String(255))  # Zitadel user sub
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Interpretation
    interpreted_dno: Mapped[str | None] = mapped_column(String(255))
    interpreted_year: Mapped[int | None] = mapped_column(Integer)
    interpreted_data_type: Mapped[str | None] = mapped_column(String(20))
    
    # Results
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    response_time_ms: Mapped[int | None] = mapped_column(Integer)
    result_from_cache: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Request metadata
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