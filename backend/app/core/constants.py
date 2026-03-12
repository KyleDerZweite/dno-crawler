"""
Shared constants for the backend application.

These constants are used across multiple modules and should be
imported from here to ensure consistency.
"""

import re
from typing import Literal

from app.core.models import (
    DataType as DataTypeEnum,
)
from app.core.models import (
    DNOStatus as DNOStatusEnum,
)
from app.core.models import (
    JobStatus as JobStatusEnum,
)
from app.core.models import (
    VerificationStatus as VerificationStatusEnum,
)

# =============================================================================
# Voltage Levels
# =============================================================================

# Standard German grid voltage levels in order from highest to lowest
VOLTAGE_LEVELS = ("HöS", "HöS/HS", "HS", "HS/MS", "MS", "MS/NS", "NS")

# Type for voltage level
VoltageLevel = Literal["HöS", "HöS/HS", "HS", "HS/MS", "MS", "MS/NS", "NS"]

# Display labels for voltage levels
VOLTAGE_LEVEL_LABELS = {
    "HöS": "Höchstspannung",
    "HöS/HS": "Umspannung HS/HöS",
    "HS": "Hochspannung",
    "HS/MS": "Umspannung MS/HS",
    "MS": "Mittelspannung",
    "MS/NS": "Umspannung NS/MS",
    "NS": "Niederspannung",
}


def is_valid_voltage_level(value: str) -> bool:
    """Check if a string is a valid voltage level."""
    return value in VOLTAGE_LEVELS


# =============================================================================
# Voltage Level Normalization
# =============================================================================
# Maps various voltage level naming conventions to standardized abbreviations.
# Some DNOs (especially small municipal utilities) use non-standard naming.

VOLTAGE_LEVEL_ALIASES: dict[str, str] = {
    # Standard German names → abbreviations
    "hochspannung": "HS",
    "hochspannungsnetz": "HS",
    "inhs": "HS",
    "hs": "HS",
    "mittelspannung": "MS",
    "mittelspannungsnetz": "MS",
    "inms": "MS",
    "ms": "MS",
    # Non-standard (some municipal utilities use MSP)
    "msp": "MS",
    "mittelspannung (msp)": "MS",
    "niederspannung": "NS",
    "niederspannungsnetz": "NS",
    "inns": "NS",
    "ns": "NS",
    # Non-standard (some municipal utilities use NSP)
    "nsp": "NS",
    "niederspannung (nsp)": "NS",
    # Umspannung levels
    "umspannung hoch-/mittelspannung": "HS/MS",
    "umspannung hoch -/mittelspannung": "HS/MS",
    "umspannung hs/ms": "HS/MS",
    "umspannung ms/hs": "HS/MS",
    "ms/hs": "HS/MS",
    "umspannung zur mittelspannung": "HS/MS",
    "aushs": "HS/MS",
    "hs/ms": "HS/MS",
    "höchstspannung mit umspannung auf hochspannung": "HöS/HS",
    "hochspannung mit umspannung auf mittelspannung": "HS/MS",
    "hochspannung mit umspannung auf ms": "HS/MS",
    "mittelspannung mit umspannung auf niederspannung": "MS/NS",
    "mittelspannung mit umspannung auf ns": "MS/NS",
    "umspannung mittel-/niederspannung": "MS/NS",
    "umspannung mittel -/niederspannung": "MS/NS",
    "umspannung ms/ns": "MS/NS",
    "umspannung ns/ms": "MS/NS",
    "ns/ms": "MS/NS",
    "umspannung zur niederspannung": "MS/NS",
    "ausms": "MS/NS",
    "ms/ns": "MS/NS",
    # Non-standard municipal naming
    "msp/nsp": "MS/NS",
    "umspannung msp/nsp": "MS/NS",
    # Höchstspannung (TSO level - rare but possible)
    "höchstspannung": "HöS",
    "höchstspannungsnetz": "HöS",
    "hös": "HöS",
    "umspannung höchst-/hochspannung": "HöS/HS",
    "umspannung hös/hs": "HöS/HS",
    "umspannung hs/hös": "HöS/HS",
    "aushös": "HöS/HS",
    "hös/hs": "HöS/HS",
    "hs/hös": "HöS/HS",
}

# Standard voltage levels for validation
STANDARD_DNO_LEVELS = ["HS", "HS/MS", "MS", "MS/NS", "NS"]  # 5 levels
SMALL_DNO_LEVELS = ["MS", "MS/NS", "NS"]  # 3 levels (no high voltage)
TSO_LEVELS = ["HöS", "HöS/HS", "HS", "HS/MS", "MS"]  # 5 levels (no low voltage)


_RE_WHITESPACE = re.compile(r"\s+")
_RE_SEPARATOR = re.compile(r"\s*([-/])\s*")
_RE_PARENS = re.compile(r"[()]")

# kV-based voltage level resolution
# Maps numeric kV values to standard abbreviations
_KV_MAP: dict[str, str] = {
    "0.4": "NS",
    "10": "MS",
    "20": "MS",
    "30": "MS",
    "110": "HS",
    "220": "HöS",
    "380": "HöS",
}

# Pattern A: number kV / number (kV|V) — both sides have units
# e.g. "110 kV / 20 kV", "20 kV / 400 V"
_RE_KV_COMPOUND_FULL = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*kv\s*/\s*(\d+(?:[.,]\d+)?)\s*(kv|v)\b",
    re.IGNORECASE,
)

# Pattern B: number / number (kV|V) — trailing unit only
# e.g. "20/0,4kV", "110/20kV"
_RE_KV_COMPOUND = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)\s*kv",
    re.IGNORECASE,
)

# Single: number (kV|V) — captures unit to distinguish V from kV
_RE_KV_SINGLE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(kv|v)\b",
    re.IGNORECASE,
)


def _kv_to_level(kv_str: str, *, is_volt: bool = False) -> str | None:
    """Map a kV value string to a voltage level abbreviation.

    Args:
        kv_str: Numeric value as string (e.g. "110", "0,4", "400")
        is_volt: If True, value is in Volts (divide by 1000 to get kV)
    """
    normalized = kv_str.replace(",", ".").strip()
    if normalized.endswith(".0"):
        normalized = normalized[:-2]
    if is_volt:
        try:
            kv_val = float(normalized) / 1000
            # Format cleanly: 0.4, 20, etc.
            normalized = f"{kv_val:g}"
        except ValueError:
            return None
    return _KV_MAP.get(normalized)


def normalize_voltage_level(level: str) -> str | None:
    """
    Normalize voltage level name to standard abbreviation.

    Handles various German naming conventions and returns the canonical form.

    Args:
        level: Raw voltage level string from document

    Returns:
        Standardized abbreviation (HS, HS/MS, MS, MS/NS, NS, HöS, HöS/HS) or None
    """
    if not level:
        return None

    # Clean and lowercase for matching
    cleaned = level.strip().lower()
    cleaned = _RE_WHITESPACE.sub(" ", cleaned)  # Normalize whitespace

    # Normalize separators: remove spaces around hyphens and slashes
    # e.g. "Hoch - / Mittelspannung" -> "hoch-/mittelspannung"
    cleaned = _RE_SEPARATOR.sub(r"\1", cleaned)

    cleaned = _RE_PARENS.sub("", cleaned)  # Remove parentheses
    cleaned = cleaned.strip()

    # Direct match
    if cleaned in VOLTAGE_LEVELS:
        return cleaned  # Already normalized

    if cleaned in VOLTAGE_LEVEL_ALIASES:
        return VOLTAGE_LEVEL_ALIASES[cleaned]

    # Try kV/V-based resolution early — before partial alias matching which can
    # false-positive on short aliases like "ms" inside "umspannung"
    # (e.g. "Umspannung 20/0,4kV" → MS/NS, "110 kV / 20 kV" → HS/MS)

    # Pattern A: "110 kV / 20 kV", "20 kV / 400 V"
    compound_full = _RE_KV_COMPOUND_FULL.search(cleaned)
    if compound_full:
        high = _kv_to_level(compound_full.group(1))  # always kV
        low_is_v = compound_full.group(3).lower() == "v"
        low = _kv_to_level(compound_full.group(2), is_volt=low_is_v)
        if high and low:
            return f"{high}/{low}"

    # Pattern B: "20/0,4kV"
    compound_kv = _RE_KV_COMPOUND.search(cleaned)
    if compound_kv:
        high = _kv_to_level(compound_kv.group(1))
        low = _kv_to_level(compound_kv.group(2))
        if high and low:
            return f"{high}/{low}"

    # Single: "20 kV", "400 V"
    single_kv = _RE_KV_SINGLE.search(cleaned)
    if single_kv:
        is_v = single_kv.group(2).lower() == "v"
        resolved = _kv_to_level(single_kv.group(1), is_volt=is_v)
        if resolved:
            return resolved

    # Partial match - check if any key is contained in the level
    # Sort aliases by length (descending) to match specific phrases first
    # e.g. Match "umspannung hoch-/mittelspannung" before "mittelspannung"
    sorted_aliases = sorted(VOLTAGE_LEVEL_ALIASES.keys(), key=len, reverse=True)

    for alias in sorted_aliases:
        # Also clean the alias for comparison (though aliases should be clean in constant)
        clean_alias = _RE_SEPARATOR.sub(r"\1", alias)
        if len(clean_alias) <= 4:
            # Short aliases (hs, ms, ns, hös, ...) need word boundary matching
            # to avoid false positives like "hs" in "Verbrauchseinrichtung"
            if re.search(r"\b" + re.escape(clean_alias) + r"\b", cleaned):
                return VOLTAGE_LEVEL_ALIASES[alias]
        elif clean_alias in cleaned:
            return VOLTAGE_LEVEL_ALIASES[alias]

    # If no match found, try to extract useful info
    # Check for compound levels first (with /)
    if "/" in cleaned:
        parts = cleaned.split("/")
        if len(parts) == 2:
            # Try to normalize each part
            left = normalize_voltage_level(parts[0].strip())
            right = normalize_voltage_level(parts[1].strip())
            if left and right and len(left) <= 3 and len(right) <= 3:
                return f"{left}/{right}"

    # Return None if no match found
    return None


# =============================================================================
# Data Types
# Use enum aliases from core.models as single source of truth for type hints.
# =============================================================================

# Types of data that can be extracted
DATA_TYPES = tuple(member.value for member in DataTypeEnum)
DataType = DataTypeEnum

# =============================================================================
# Job Configuration
# =============================================================================

# Job types
JOB_TYPES = ("full", "crawl", "extract")
JobType = Literal["full", "crawl", "extract"]

# Job statuses
JOB_STATUSES = tuple(member.value for member in JobStatusEnum)
JobStatus = JobStatusEnum

# Default job priority
DEFAULT_JOB_PRIORITY = 10

# Bulk extraction job priority (lower priority than manual jobs)
BULK_JOB_PRIORITY = 100

# =============================================================================
# Verification Statuses
# =============================================================================

# NOTE: core/models.py VerificationStatus enum also includes "rejected"
VERIFICATION_STATUSES = tuple(member.value for member in VerificationStatusEnum)
VerificationStatus = VerificationStatusEnum

# =============================================================================
# Pagination
# =============================================================================

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 250
PAGE_SIZE_OPTIONS = (25, 50, 100, 250)

# =============================================================================
# Year Range
# =============================================================================

MIN_YEAR = 2020
MAX_YEAR = 2030  # Should be dynamically computed in most cases


def get_available_years(start_year: int = MIN_YEAR, end_year: int | None = None) -> list[int]:
    """Generate list of available years from end_year down to start_year."""
    from datetime import datetime

    if end_year is None:
        end_year = datetime.now().year + 1

    return list(range(end_year, start_year - 1, -1))


# =============================================================================
# Extraction Sources
# =============================================================================

EXTRACTION_SOURCES = ("ai", "html_parser", "pdf_regex", "manual", "import")
ExtractionSource = Literal["ai", "html_parser", "pdf_regex", "manual", "import"]

EXTRACTION_FORMATS = ("html", "pdf")
ExtractionFormat = Literal["html", "pdf"]

# =============================================================================
# DNO Status
# =============================================================================

DNO_STATUSES = tuple(member.value for member in DNOStatusEnum)
DNOStatus = DNOStatusEnum
