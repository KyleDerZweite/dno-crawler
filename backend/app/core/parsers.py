"""
Shared parsing utilities for data extraction.

Common functions for parsing and normalizing values extracted from
PDF, HTML, and other document formats.
"""

import re
from typing import TypeVar

T = TypeVar('T')


def parse_german_number(value: str | None) -> float | None:
    """
    Parse a German-formatted number (comma as decimal separator).
    
    Examples:
        "1.234,56" -> 1234.56
        "1234,56" -> 1234.56
        "1234.56" -> 1234.56 (accepts both formats)
        "1,234.56" -> 1234.56 (US format)
        "-" -> None
        None -> None
        
    Args:
        value: String representation of number or None
        
    Returns:
        Parsed float or None if not parseable
    """
    if value is None:
        return None

    # Clean up the value
    s = str(value).strip()

    # Check for explicit "no value" markers
    if s.lower() in ("-", "n/a", "null", "none", "", "entfällt", "–"):
        return None

    try:
        # Remove thousands separators and normalize decimal
        # German: 1.234,56 -> 1234.56
        # US: 1,234.56 -> 1234.56

        # Count occurrences to detect format
        comma_count = s.count(",")
        dot_count = s.count(".")

        if comma_count == 1 and dot_count == 0:
            # Simple German format: 1234,56
            s = s.replace(",", ".")
        elif comma_count == 1 and dot_count >= 1:
            # German with thousands: 1.234,56
            s = s.replace(".", "").replace(",", ".")
        elif comma_count >= 1 and dot_count == 1:
            # US with thousands: 1,234.56
            s = s.replace(",", "")
        # else: assume it's already in correct format

        return float(s)
    except (ValueError, TypeError):
        return None


def parse_time_window(value: str | None) -> str | None:
    """
    Normalize a time window string.
    
    Converts various formats to standard "HH:MM-HH:MM" format.
    
    Examples:
        "7:30 - 15:30" -> "07:30-15:30"
        "07.30-15.30" -> "07:30-15:30"
        "7:30 Uhr bis 15:30 Uhr" -> "07:30-15:30"
        "entfällt" -> "-"
        
    Args:
        value: Time window string
        
    Returns:
        Normalized time string or "-" for no times
    """
    if value is None:
        return None

    s = str(value).strip()

    # Check for explicit "no value" markers
    if s.lower() in ("-", "entfällt", "keine", "n/a", ""):
        return "-"

    # Try to extract time patterns
    # Match patterns like "7:30", "07:30", "7.30", "07.30"
    time_pattern = r"(\d{1,2})[:\.](\d{2})"
    times = re.findall(time_pattern, s)

    if len(times) >= 2:
        # Format as HH:MM-HH:MM
        start = f"{int(times[0][0]):02d}:{times[0][1]}"
        end = f"{int(times[1][0]):02d}:{times[1][1]}"
        return f"{start}-{end}"

    # Return original if we can't parse
    return s


def clean_string(value: str | None, max_length: int | None = None) -> str | None:
    """
    Clean and normalize a string value.
    
    Args:
        value: Input string
        max_length: Optional maximum length to truncate to
        
    Returns:
        Cleaned string or None
    """
    if value is None:
        return None

    # Clean up whitespace
    s = " ".join(str(value).split())

    if not s:
        return None

    # Truncate if needed
    if max_length and len(s) > max_length:
        s = s[:max_length - 3] + "..."

    return s


def is_valid_value(value: str | float | int | None) -> bool:
    """
    Check if a value is valid (not None, not a "no value" marker).
    
    Args:
        value: Value to check
        
    Returns:
        True if value is valid
    """
    if value is None:
        return False

    if isinstance(value, (int, float)):
        return True

    s = str(value).strip().lower()
    return s not in ("-", "n/a", "null", "none", "", "entfällt", "–")


def parse_year(value: str | int | None) -> int | None:
    """
    Parse a year value.
    
    Args:
        value: Year as string or int
        
    Returns:
        Year as int or None
    """
    if value is None:
        return None

    if isinstance(value, int):
        return value if 1900 <= value <= 2100 else None

    try:
        # Try to extract year from string
        s = str(value).strip()

        # Look for 4-digit year
        match = re.search(r"\b(19\d{2}|20\d{2})\b", s)
        if match:
            return int(match.group(1))

        # Try direct conversion
        year = int(s)
        return year if 1900 <= year <= 2100 else None
    except (ValueError, TypeError):
        return None


def normalize_voltage_level(value: str | None) -> str | None:
    """
    Normalize voltage level string to standard format.
    
    See app.core.constants.normalize_voltage_level for the full
    implementation with more mappings.
    
    Args:
        value: Voltage level string
        
    Returns:
        Normalized voltage level or None
    """
    from app.core.constants import normalize_voltage_level as _normalize
    return _normalize(value) if value else None
