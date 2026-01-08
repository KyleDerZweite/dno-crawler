"""
Content sanitization utilities for import data.

Provides protection against injection attacks in imported JSON data.
"""

import re
import html
from typing import Any

import structlog

logger = structlog.get_logger()


class SanitizationError(Exception):
    """Raised when content fails sanitization checks."""
    pass


# Patterns that indicate potential injection attempts
DANGEROUS_PATTERNS = [
    r"<script",                    # Script tags
    r"javascript:",                # JavaScript protocol
    r"vbscript:",                  # VBScript protocol
    r"on\w+\s*=",                  # Event handlers (onclick=, onerror=, etc.)
    r"data:text/html",             # Data URI with HTML
    r"data:application/",          # Data URI with applications
    r"expression\s*\(",            # CSS expression()
    r"url\s*\(\s*['\"]?javascript", # CSS url(javascript:)
    r"\x00",                       # Null bytes
    r"&#",                         # HTML entity encoding (potential bypass)
]

# Compiled regex for performance
DANGEROUS_REGEX = re.compile(
    "|".join(DANGEROUS_PATTERNS), 
    re.IGNORECASE
)


def sanitize_string(
    value: str, 
    field_name: str = "field",
    max_length: int = 1000,
    allow_html_entities: bool = False,
) -> str:
    """
    Sanitize a string value to prevent injection attacks.
    
    Args:
        value: The string to sanitize
        field_name: Name of the field (for error messages)
        max_length: Maximum allowed length
        allow_html_entities: If False, reject strings with HTML entities
        
    Returns:
        Sanitized string (HTML escaped)
        
    Raises:
        SanitizationError: If the value contains dangerous patterns
    """
    if not isinstance(value, str):
        raise SanitizationError(f"{field_name}: Expected string, got {type(value).__name__}")
    
    # Check length
    if len(value) > max_length:
        raise SanitizationError(
            f"{field_name}: Exceeds maximum length of {max_length} characters"
        )
    
    # Strip control characters (except newline, tab)
    cleaned = "".join(
        char for char in value 
        if char >= " " or char in "\n\t"
    )
    
    # Check for dangerous patterns
    if DANGEROUS_REGEX.search(cleaned):
        logger.warning(
            "sanitization_blocked_dangerous_pattern",
            field=field_name,
            value_preview=cleaned[:50],
        )
        raise SanitizationError(
            f"{field_name}: Contains potentially dangerous content"
        )
    
    # Check for HTML entities if not allowed
    if not allow_html_entities and re.search(r"&#\d+;|&#x[0-9a-fA-F]+;", cleaned):
        raise SanitizationError(
            f"{field_name}: HTML entity encoding is not allowed"
        )
    
    # HTML escape special characters
    return html.escape(cleaned)


def sanitize_time_string(value: str, field_name: str = "field") -> str:
    """
    Sanitize a time window string (e.g., "16:00-20:00").
    
    Only allows:
    - Time format: HH:MM-HH:MM
    - Dash for "not applicable": -
    - Empty string
    """
    if not value or value == "-":
        return value
    
    # Strict pattern for time windows
    pattern = r"^\d{1,2}:\d{2}-\d{1,2}:\d{2}$"
    if not re.match(pattern, value):
        raise SanitizationError(
            f"{field_name}: Invalid time format. Expected 'HH:MM-HH:MM' or '-'"
        )
    
    return value


def sanitize_dict(
    data: dict[str, Any],
    string_fields: list[str] | None = None,
    time_fields: list[str] | None = None,
    max_string_length: int = 1000,
) -> dict[str, Any]:
    """
    Sanitize all string fields in a dictionary.
    
    Args:
        data: Dictionary to sanitize
        string_fields: List of field names to sanitize as strings
        time_fields: List of field names to sanitize as time strings
        max_string_length: Maximum length for string fields
        
    Returns:
        Sanitized dictionary (new copy)
    """
    result = dict(data)
    
    # Sanitize specified string fields
    if string_fields:
        for field in string_fields:
            if field in result and result[field] is not None:
                result[field] = sanitize_string(
                    result[field], 
                    field_name=field,
                    max_length=max_string_length,
                )
    
    # Sanitize specified time fields
    if time_fields:
        for field in time_fields:
            if field in result and result[field] is not None:
                result[field] = sanitize_time_string(
                    result[field],
                    field_name=field,
                )
    
    return result
