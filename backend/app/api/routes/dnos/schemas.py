"""
Pydantic schemas for DNO API endpoints.
"""

from datetime import time
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class JobType(StrEnum):
    """Job types for crawl triggering."""

    FULL = "full"  # Full pipeline (crawl + extract)
    EXTRACT = "extract"  # Extract only (from existing files)


class TriggerCrawlRequest(BaseModel):
    """Request model for triggering a crawl job."""

    year: int
    priority: int = 5
    job_type: JobType = JobType.FULL


class CreateDNORequest(BaseModel):
    """Request model for creating a new DNO."""

    name: str
    slug: str | None = None  # Auto-generate if not provided
    official_name: str | None = None
    description: str | None = None
    region: str | None = None
    website: str | None = None
    vnb_id: str | None = None  # VNB Digital ID for validation/deduplication
    phone: str | None = None
    email: str | None = None
    contact_address: str | None = None


class UpdateDNORequest(BaseModel):
    """Request model for updating DNO metadata."""

    name: str | None = None
    official_name: str | None = None
    description: str | None = None
    region: str | None = None
    website: str | None = None
    phone: str | None = None
    email: str | None = None
    contact_address: str | None = None
    service_area_km2: float | None = Field(None, ge=0)
    customer_count: int | None = Field(None, ge=0)


class UpdateNetzentgelteRequest(BaseModel):
    """Request model for updating Netzentgelte."""

    leistung: float | None = None
    arbeit: float | None = None
    leistung_unter_2500h: float | None = None
    arbeit_unter_2500h: float | None = None


class HLZFTimeRange(BaseModel):
    """A single time range with start and end times."""

    start: str = Field(..., pattern=r"^\d{2}:\d{2}:\d{2}$")
    end: str = Field(..., pattern=r"^\d{2}:\d{2}:\d{2}$")

    @field_validator("start", "end", mode="after")
    @classmethod
    def validate_time_value(cls, v: str) -> str:
        """Validate that time strings represent valid clock times.

        Rejects impossible times like 25:61:99 by attempting to parse
        with datetime.time.fromisoformat().
        """
        try:
            time.fromisoformat(v)
        except ValueError as e:
            raise ValueError(f"Invalid time value '{v}': {e}") from e
        return v


class UpdateHLZFRequest(BaseModel):
    """Request model for updating HLZF."""

    winter: list[HLZFTimeRange] | None = None
    fruehling: list[HLZFTimeRange] | None = None
    sommer: list[HLZFTimeRange] | None = None
    herbst: list[HLZFTimeRange] | None = None


# Import/Export constants
MAX_IMPORT_RECORDS = 500

# Use shared voltage levels from core constants
from app.core.constants import VERIFICATION_STATUSES, VOLTAGE_LEVELS  # noqa: E402

VALID_VOLTAGE_LEVELS = list(VOLTAGE_LEVELS)


class NetzentgelteImport(BaseModel):
    """Pydantic model for importing Netzentgelte data with strict validation."""

    year: int = Field(..., ge=2000, le=2100)
    voltage_level: str = Field(...)
    leistung: float | None = Field(None, ge=0, le=1000000)
    arbeit: float | None = Field(None, ge=0, le=1000000)
    leistung_unter_2500h: float | None = Field(None, ge=0, le=1000000)
    arbeit_unter_2500h: float | None = Field(None, ge=0, le=1000000)
    verification_status: str | None = Field(None)
    extraction_source: str | None = Field(None)

    @field_validator("voltage_level")
    @classmethod
    def validate_voltage_level(cls, v: str) -> str:
        if v not in VALID_VOLTAGE_LEVELS:
            raise ValueError(f"Invalid voltage_level: must be one of {VALID_VOLTAGE_LEVELS}")
        return v

    @field_validator("verification_status")
    @classmethod
    def validate_verification_status(cls, v: str | None) -> str | None:
        if v is not None and v not in VERIFICATION_STATUSES:
            raise ValueError(f"Invalid verification_status: must be one of {VERIFICATION_STATUSES}")
        return v


class HLZFImport(BaseModel):
    """Pydantic model for importing HLZF data with strict validation."""

    year: int = Field(..., ge=2000, le=2100)
    voltage_level: str = Field(...)
    winter: list[HLZFTimeRange] | None = None
    fruehling: list[HLZFTimeRange] | None = None
    sommer: list[HLZFTimeRange] | None = None
    herbst: list[HLZFTimeRange] | None = None
    verification_status: str | None = Field(None)
    extraction_source: str | None = Field(None)

    @field_validator("voltage_level")
    @classmethod
    def validate_voltage_level(cls, v: str) -> str:
        if v not in VALID_VOLTAGE_LEVELS:
            raise ValueError(f"Invalid voltage_level: must be one of {VALID_VOLTAGE_LEVELS}")
        return v

    @field_validator("verification_status")
    @classmethod
    def validate_verification_status(cls, v: str | None) -> str | None:
        if v is not None and v not in VERIFICATION_STATUSES:
            raise ValueError(f"Invalid verification_status: must be one of {VERIFICATION_STATUSES}")
        return v


class ImportRequest(BaseModel):
    """Request model for importing DNO data."""

    mode: Literal["merge", "replace"] = "merge"
    netzentgelte: list[NetzentgelteImport] = Field(
        default_factory=list, max_length=MAX_IMPORT_RECORDS
    )
    hlzf: list[HLZFImport] = Field(default_factory=list, max_length=MAX_IMPORT_RECORDS)

    @field_validator("netzentgelte", "hlzf")
    @classmethod
    def validate_record_count(cls, v: list) -> list:
        if len(v) > MAX_IMPORT_RECORDS:
            raise ValueError(f"Too many records: maximum allowed is {MAX_IMPORT_RECORDS}")
        return v
