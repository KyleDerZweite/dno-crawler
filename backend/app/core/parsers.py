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

    # Check for explicit "no value" markers (including German abbreviations)
    if s.lower() in ("-", "n/a", "null", "none", "", "entfällt", "–", "k.a.", "keine angabe"):
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
        "16:30 - 19:45" -> "16:30-19:45" (removes spaces around dash)
        "k.A." -> "-"
        "entfällt" -> "-"

    Args:
        value: Time window string

    Returns:
        Normalized time string or "-" for no times
    """
    if value is None:
        return None

    s = str(value).strip()

    # Check for explicit "no value" markers (including German abbreviations)
    if s.lower() in ("-", "entfällt", "keine", "n/a", "", "k.a.", "keine angabe"):
        return "-"

    # Remove "Uhr" suffix (e.g., "16:30 Uhr bis 19:30 Uhr" -> "16:30 bis 19:30")
    s = re.sub(r'\s*[Uu]hr\s*', ' ', s).strip()

    # Replace "bis" with dash (e.g., "16:30 bis 19:30" -> "16:30-19:30")
    s = re.sub(r'\s*bis\s*', '-', s, flags=re.IGNORECASE)

    # Remove spaces around dashes (e.g., "16:30 - 19:30" -> "16:30-19:30")
    s = re.sub(r'\s*-\s*', '-', s)
    s = re.sub(r'\s*–\s*', '-', s)  # en-dash
    s = re.sub(r'\s*—\s*', '-', s)  # em-dash

    # Try to extract time patterns
    # Match patterns like "7:30", "07:30", "7.30", "07.30"
    time_pattern = r"(\d{1,2})[:.](\d{2})"
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
    return s not in ("-", "n/a", "null", "none", "", "entfällt", "–", "k.a.", "keine angabe")


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


def clean_ai_extraction_result(records: list[dict], data_type: str) -> list[dict]:
    """
    Post-process AI extraction results to fix common formatting issues.

    This function is a safety net for when AI doesn't follow formatting
    instructions exactly. It handles:
    - "k.A." → "-"
    - "Uhr" suffix removal
    - German number format (comma → dot)
    - Spaces around dashes in time windows

    Args:
        records: List of extracted records from AI
        data_type: "netzentgelte" or "hlzf"

    Returns:
        Cleaned records list
    """
    if data_type == "netzentgelte":
        return _clean_netzentgelte_records(records)
    else:  # hlzf
        return _clean_hlzf_records(records)


def _clean_netzentgelte_records(records: list[dict]) -> list[dict]:
    """Clean Netzentgelte price records from AI extraction."""
    price_fields = ["leistung", "arbeit", "leistung_unter_2500h", "arbeit_unter_2500h"]

    cleaned = []
    for record in records:
        cleaned_record = record.copy()

        for field in price_fields:
            if field in cleaned_record:
                cleaned_record[field] = _clean_price_value(cleaned_record[field])

        cleaned.append(cleaned_record)

    return cleaned


def _clean_hlzf_records(records: list[dict]) -> list[dict]:
    """Clean HLZF time window records from AI extraction."""
    time_fields = ["winter", "fruehling", "sommer", "herbst"]

    cleaned = []
    for record in records:
        cleaned_record = record.copy()

        for field in time_fields:
            if field in cleaned_record:
                cleaned_record[field] = _clean_time_value(cleaned_record[field])

        cleaned.append(cleaned_record)

    return cleaned


def _clean_price_value(value) -> str:
    """
    Clean a price value from AI extraction.

    Handles:
    - "k.A." → "-"
    - German number format: "26,88" → "26.88"
    - null/None → "-"
    """
    if value is None:
        return "-"

    s = str(value).strip()

    # Handle "no value" markers
    if s.lower() in ("k.a.", "keine angabe", "n/a", "null", "none", "", "entfällt"):
        return "-"

    if s == "-":
        return "-"

    # Convert German decimal format (comma → dot)
    # Only if there's exactly one comma and it looks like a decimal
    if "," in s and "." not in s:
        # Simple case: "26,88" → "26.88"
        s = s.replace(",", ".")
    elif "," in s and "." in s:
        # German thousands format: "1.234,56" → "1234.56"
        # Remove dots (thousands separator), replace comma (decimal)
        s = s.replace(".", "").replace(",", ".")

    return s


def _clean_time_value(value) -> str:
    """
    Clean a time window value from AI extraction.

    Handles:
    - "k.A." → "-"
    - "16:30 Uhr" → "16:30"
    - "16:30 - 19:30" → "16:30-19:30" (remove spaces)
    - null/None → "-"
    """
    if value is None:
        return "-"

    s = str(value).strip()

    # Handle "no value" markers
    if s.lower() in ("k.a.", "keine angabe", "n/a", "null", "none", "", "entfällt"):
        return "-"

    if s == "-":
        return "-"

    # Use the full parse_time_window function which already handles these
    result = parse_time_window(s)
    return result if result else "-"
