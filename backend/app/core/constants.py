"""
Shared constants for the backend application.

These constants are used across multiple modules and should be
imported from here to ensure consistency.
"""

from typing import Literal

# =============================================================================
# Voltage Levels
# =============================================================================

# Standard German grid voltage levels in order from highest to lowest
VOLTAGE_LEVELS = ("HS", "HS/MS", "MS", "MS/NS", "NS")

# Type for voltage level
VoltageLevel = Literal["HS", "HS/MS", "MS", "MS/NS", "NS"]

# Display labels for voltage levels
VOLTAGE_LEVEL_LABELS = {
    "HS": "Hochspannung",
    "HS/MS": "Hochspannung / Mittelspannung",
    "MS": "Mittelspannung",
    "MS/NS": "Mittelspannung / Niederspannung",
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
    "umspannung hs/ms": "HS/MS",
    "umspannung zur mittelspannung": "HS/MS",
    "aushs": "HS/MS",
    "hs/ms": "HS/MS",

    "höchstspannung mit umspannung auf hochspannung": "HöS/HS",
    "hochspannung mit umspannung auf mittelspannung": "HS/MS",
    "mittelspannung mit umspannung auf niederspannung": "MS/NS",

    "umspannung mittel-/niederspannung": "MS/NS",
    "umspannung ms/ns": "MS/NS",
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
    "aushös": "HöS/HS",
    "hös/hs": "HöS/HS",
}

# Standard voltage levels for validation
STANDARD_DNO_LEVELS = ["HS", "HS/MS", "MS", "MS/NS", "NS"]  # 5 levels
SMALL_DNO_LEVELS = ["MS", "MS/NS", "NS"]  # 3 levels (no high voltage)
TSO_LEVELS = ["HöS", "HöS/HS", "HS", "HS/MS", "MS"]  # 5 levels (no low voltage)


def normalize_voltage_level(level: str) -> str | None:
    """
    Normalize voltage level name to standard abbreviation.

    Handles various German naming conventions and returns the canonical form.

    Args:
        level: Raw voltage level string from document

    Returns:
        Standardized abbreviation (HS, HS/MS, MS, MS/NS, NS, HöS, HöS/HS) or None
    """
    import re

    if not level:
        return None

    # Clean and lowercase for matching
    cleaned = level.strip().lower()
    cleaned = re.sub(r'\s+', ' ', cleaned)  # Normalize whitespace
    cleaned = re.sub(r'[()]', '', cleaned)  # Remove parentheses
    cleaned = cleaned.strip()

    # Direct match
    if cleaned in VOLTAGE_LEVEL_ALIASES:
        return VOLTAGE_LEVEL_ALIASES[cleaned]

    # Partial match - check if any key is contained in the level
    for alias, standard in VOLTAGE_LEVEL_ALIASES.items():
        if alias in cleaned:
            return standard

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
# =============================================================================

# Types of data that can be extracted
DATA_TYPES = ("netzentgelte", "hlzf", "all")
DataType = Literal["netzentgelte", "hlzf", "all"]

# =============================================================================
# Job Configuration
# =============================================================================

# Job types
JOB_TYPES = ("full", "crawl", "extract")
JobType = Literal["full", "crawl", "extract"]

# Job statuses
JOB_STATUSES = ("pending", "running", "completed", "failed", "cancelled")
JobStatus = Literal["pending", "running", "completed", "failed", "cancelled"]

# Default job priority
DEFAULT_JOB_PRIORITY = 10

# Bulk extraction job priority (lower priority than manual jobs)
BULK_JOB_PRIORITY = 100

# =============================================================================
# Verification Statuses
# =============================================================================

VERIFICATION_STATUSES = ("unverified", "verified", "flagged")
VerificationStatus = Literal["unverified", "verified", "flagged"]

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

DNO_STATUSES = ("uncrawled", "pending", "running", "crawled", "failed")
DNOStatus = Literal["uncrawled", "pending", "running", "crawled", "failed"]
