"""
SQLAlchemy ORM models for DNO Crawler.

Organized into sections:
- DNO (Core "Golden Record" Hub)
- Location Tables
- Data Tables (Netzentgelte, HLZF)
- Source Profile (Discovery Learning)
- Crawl Job Tables
- Logging Tables

Source data from external APIs is stored in separate models:
- DNOMastrData (Marktstammdatenregister)
- DNOVnbData (VNB Digital API)
- DNOBdewData (BDEW Codes API)
See: app/db/source_models.py
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
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
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.models import JobStatus, VerificationStatus
from app.db.database import Base

if TYPE_CHECKING:
    from app.db.source_models import DNOBdewData, DNOMastrData, DNOVnbData


class TimestampMixin:
    """Mixin for created_at and updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )


# ==============================================================================
# DNO - Core "Golden Record" Hub
# ==============================================================================


class DNOModel(Base, TimestampMixin):
    """
    Distribution Network Operator - The Core "Golden Record".
    
    This is the hub in a hub-and-spoke pattern. It contains:
    - Internal identifiers (id, slug)
    - Operational status (crawl status, locks)
    - Resolved/display fields (best values from sources)
    - Crawlability info
    - Relationships to data tables and source data
    
    Source data is stored in separate tables:
    - DNOMastrData: Marktstammdatenregister data
    - DNOVnbData: VNB Digital API data  
    - DNOBdewData: BDEW Codes data (one-to-many)
    """

    __tablename__ = "dnos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)

    # -------------------------------------------------------------------------
    # Resolved/Display Fields (populated from source merge logic)
    # -------------------------------------------------------------------------
    name: Mapped[str] = mapped_column(String(255), nullable=False)  # Best available name
    official_name: Mapped[str | None] = mapped_column(String(255))  # Full legal name
    website: Mapped[str | None] = mapped_column(String(500))  # Resolved website
    phone: Mapped[str | None] = mapped_column(String(100))  # Resolved phone
    email: Mapped[str | None] = mapped_column(String(255))  # Resolved email
    region: Mapped[str | None] = mapped_column(String(255), index=True)  # Bundesland
    description: Mapped[str | None] = mapped_column(Text)

    # -------------------------------------------------------------------------
    # Quick-Access Keys (duplicated from source for fast lookups)
    # -------------------------------------------------------------------------
    mastr_nr: Mapped[str | None] = mapped_column(String(50), unique=True, index=True)
    vnb_id: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)
    primary_bdew_code: Mapped[str | None] = mapped_column(String(20), index=True)  # Netzbetreiber code

    # -------------------------------------------------------------------------
    # Operational Status
    # -------------------------------------------------------------------------
    status: Mapped[str] = mapped_column(String(20), default="uncrawled", index=True)
    crawl_locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(20), default="seed")  # seed | user_discovery
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # -------------------------------------------------------------------------
    # Enrichment Status (VNB lookup, robots.txt analysis)
    # -------------------------------------------------------------------------
    enrichment_status: Mapped[str | None] = mapped_column(String(20), default="pending")  # pending | processing | completed | failed
    last_enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contact_address: Mapped[str | None] = mapped_column(Text)  # Resolved contact address

    # -------------------------------------------------------------------------
    # Crawlability Info (from skeleton creation/robots.txt analysis)
    # -------------------------------------------------------------------------
    robots_txt: Mapped[str | None] = mapped_column(Text)
    sitemap_urls: Mapped[list | None] = mapped_column(JSON)
    disallow_paths: Mapped[list | None] = mapped_column(JSON)
    crawlable: Mapped[bool] = mapped_column(Boolean, default=True)
    crawl_blocked_reason: Mapped[str | None] = mapped_column(String(100))

    # -------------------------------------------------------------------------
    # Source Data Relationships (One-to-One/Many)
    # -------------------------------------------------------------------------
    mastr_data: Mapped[Optional["DNOMastrData"]] = relationship(
        "DNOMastrData",
        back_populates="dno",
        uselist=False,
        cascade="all, delete-orphan",
    )
    vnb_data: Mapped[Optional["DNOVnbData"]] = relationship(
        "DNOVnbData",
        back_populates="dno",
        uselist=False,
        cascade="all, delete-orphan",
    )
    bdew_data: Mapped[list["DNOBdewData"]] = relationship(
        "DNOBdewData",
        back_populates="dno",
        cascade="all, delete-orphan",
    )

    # -------------------------------------------------------------------------
    # Business Data Relationships
    # -------------------------------------------------------------------------
    netzentgelte: Mapped[list["NetzentgelteModel"]] = relationship(back_populates="dno")
    hlzf: Mapped[list["HLZFModel"]] = relationship(back_populates="dno")
    source_profiles: Mapped[list["DNOSourceProfile"]] = relationship(back_populates="dno")
    locations: Mapped[list["LocationModel"]] = relationship(back_populates="dno")

    # -------------------------------------------------------------------------
    # Convenience Properties for Source Data Access
    # -------------------------------------------------------------------------

    @property
    def display_name(self) -> str:
        """Get the best available name (prefers VNB official name)."""
        if self.vnb_data and self.vnb_data.official_name:
            return self.vnb_data.official_name
        return self.official_name or self.name

    @property
    def display_website(self) -> str | None:
        """Get website (prefers VNB, falls back to BDEW)."""
        if self.vnb_data and self.vnb_data.homepage_url:
            return self.vnb_data.homepage_url
        if self.bdew_data:
            for bdew in self.bdew_data:
                if bdew.website:
                    return bdew.website
        return self.website

    @property
    def display_phone(self) -> str | None:
        """Get phone (prefers VNB)."""
        if self.vnb_data and self.vnb_data.phone:
            return self.vnb_data.phone
        return self.phone

    @property
    def display_email(self) -> str | None:
        """Get email (prefers VNB)."""
        if self.vnb_data and self.vnb_data.email:
            return self.vnb_data.email
        return self.email

    @property
    def mastr_contact_address(self) -> str | None:
        """Get formatted contact address from MaStR data (fallback)."""
        if self.mastr_data:
            return self.mastr_data.contact_address
        return None

    @property
    def address_components(self) -> dict | None:
        """Get structured address from MaStR data."""
        if self.mastr_data:
            return self.mastr_data.address_components
        return None

    @property
    def marktrollen(self) -> list | None:
        """Get market roles from MaStR data."""
        if self.mastr_data:
            return self.mastr_data.marktrollen
        return None

    @property
    def acer_code(self) -> str | None:
        """Get ACER code from MaStR data."""
        if self.mastr_data:
            return self.mastr_data.acer_code
        return None

    @property
    def grid_operator_bdew_code(self) -> str | None:
        """Get the primary BDEW code for grid operator function."""
        if self.bdew_data:
            for bdew in self.bdew_data:
                if bdew.is_grid_operator:
                    return bdew.bdew_code
            # Fallback to first code if no grid operator code
            return self.bdew_data[0].bdew_code if self.bdew_data else None
        return self.primary_bdew_code

    @property
    def has_mastr(self) -> bool:
        """Check if MaStR data is available."""
        return self.mastr_data is not None

    @property
    def has_vnb(self) -> bool:
        """Check if VNB Digital data is available."""
        return self.vnb_data is not None

    @property
    def has_bdew(self) -> bool:
        """Check if BDEW data is available."""
        return bool(self.bdew_data)

    @property
    def enrichment_sources(self) -> list[str]:
        """Get list of available enrichment sources."""
        sources = []
        if self.has_mastr:
            sources.append("mastr")
        if self.has_vnb:
            sources.append("vnb")
        if self.has_bdew:
            sources.append("bdew")
        return sources


# ==============================================================================
# Location Tables
# ==============================================================================


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

    # Extraction source tracking
    extraction_source: Mapped[str | None] = mapped_column(String(20))  # ai | html_parser | pdf_regex | manual
    extraction_model: Mapped[str | None] = mapped_column(String(100))  # e.g., "gemini-2.0-flash"
    extraction_source_format: Mapped[str | None] = mapped_column(String(20))  # html | pdf

    # Manual edit tracking
    last_edited_by: Mapped[str | None] = mapped_column(String(255))  # User sub who last edited
    last_edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

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

    # Extraction source tracking
    extraction_source: Mapped[str | None] = mapped_column(String(20))  # ai | html_parser | pdf_regex | manual
    extraction_model: Mapped[str | None] = mapped_column(String(100))  # e.g., "gemini-2.0-flash"
    extraction_source_format: Mapped[str | None] = mapped_column(String(20))  # html | pdf

    # Manual edit tracking
    last_edited_by: Mapped[str | None] = mapped_column(String(255))  # User sub who last edited
    last_edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

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
    """Crawl job tracking.
    
    Supports split job architecture:
    - job_type: 'crawl' (discover+download), 'extract' (extract+validate+finalize), or 'full' (legacy)
    - parent_job_id: Links extract job back to its parent crawl job
    - child_job_id: Links crawl job to the extract job it spawned
    """

    __tablename__ = "crawl_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dno_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dnos.id", ondelete="CASCADE")
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    data_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # Job type: 'crawl' (steps 0-3), 'extract' (steps 4-6), or 'full' (legacy all steps)
    job_type: Mapped[str] = mapped_column(String(20), default="full")

    # Parent/child linking for split jobs
    parent_job_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("crawl_jobs.id", ondelete="SET NULL"), nullable=True
    )
    child_job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Updated when extract job is created

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

    # Relationship to parent job (for extract jobs)
    parent_job: Mapped["CrawlJobModel | None"] = relationship(
        "CrawlJobModel",
        remote_side=[id],
        foreign_keys=[parent_job_id],
        uselist=False,
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


# ==============================================================================
# AI Provider Configuration
# ==============================================================================


class AIProviderConfigModel(Base, TimestampMixin):
    """AI provider configuration for multi-provider support.
    
    Supports multiple authentication methods:
    - OAuth (for subscription plans: ChatGPT Plus, Claude Pro, Google AI Pro)
    - API Key (for OpenRouter, direct API access)
    
    Features:
    - Priority-based fallback ordering (drag-and-drop in admin UI)
    - Subscription preference (OAuth configs prioritized over API keys)
    - Health tracking (consecutive failures, rate limit detection)
    - Model capability tracking (text, vision, file support)
    """
    __tablename__ = "ai_provider_configs"
    __table_args__ = (
        Index("idx_ai_provider_enabled_priority", "is_enabled", "priority"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # -------------------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------------------
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # "My ChatGPT Plus"
    provider_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Allowed: "openai" | "google" | "anthropic" | "openrouter" | "litellm" | "custom"

    # -------------------------------------------------------------------------
    # Authentication
    # -------------------------------------------------------------------------
    auth_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # "oauth" | "api_key"

    # For API Key auth
    api_url: Mapped[str | None] = mapped_column(String(500))  # Custom endpoint URL
    api_key_encrypted: Mapped[str | None] = mapped_column(Text)  # Fernet encrypted

    # For OAuth auth (encrypted tokens)
    oauth_access_token_encrypted: Mapped[str | None] = mapped_column(Text)
    oauth_refresh_token_encrypted: Mapped[str | None] = mapped_column(Text)
    oauth_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    oauth_scope: Mapped[str | None] = mapped_column(Text)  # Granted scopes

    # -------------------------------------------------------------------------
    # Model Configuration
    # -------------------------------------------------------------------------
    model: Mapped[str] = mapped_column(String(100), nullable=False)  # "gpt-4o", "gemini-2.0-flash"

    # Model capabilities (detected via test or user-configured)
    supports_text: Mapped[bool] = mapped_column(Boolean, default=True)
    supports_vision: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_files: Mapped[bool] = mapped_column(Boolean, default=False)

    # -------------------------------------------------------------------------
    # Priority & Status
    # -------------------------------------------------------------------------
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)  # Lower = higher priority

    # -------------------------------------------------------------------------
    # Health Tracking
    # -------------------------------------------------------------------------
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_message: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    rate_limited_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # -------------------------------------------------------------------------
    # Usage Stats
    # -------------------------------------------------------------------------
    total_requests: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens_used: Mapped[int] = mapped_column(Integer, default=0)

    # -------------------------------------------------------------------------
    # Audit
    # -------------------------------------------------------------------------
    created_by: Mapped[str | None] = mapped_column(String(255))  # Admin user sub
    last_modified_by: Mapped[str | None] = mapped_column(String(255))

    @property
    def is_subscription(self) -> bool:
        """Check if this config uses a subscription (OAuth-based)."""
        return self.auth_type == "oauth"

    @property
    def is_healthy(self) -> bool:
        """Check if provider is currently healthy."""
        from datetime import datetime, timezone
        
        # Check rate limiting
        if self.rate_limited_until:
            if datetime.now(timezone.utc) < self.rate_limited_until:
                return False
        
        # Check consecutive failures (unhealthy after 3 failures)
        if self.consecutive_failures >= 3:
            return False
        
        return True

    @property
    def status_display(self) -> str:
        """Get human-readable status."""
        from datetime import datetime, timezone
        
        if not self.is_enabled:
            return "disabled"
        if self.rate_limited_until and datetime.now(timezone.utc) < self.rate_limited_until:
            return "rate_limited"
        if self.consecutive_failures >= 3:
            return "unhealthy"
        if self.last_success_at:
            return "active"
        return "untested"
