"""
Encoding Detection Utilities for DNO Crawler.

Detects character encoding for HTML and text content using:
1. HTTP Content-Type charset header
2. BOM (Byte Order Mark) detection
3. HTML <meta charset> tag
4. Statistical detection via charset_normalizer
"""

import re

import structlog

logger = structlog.get_logger()


def detect_encoding(
    content: bytes,
    content_type: str | None = None,
    default: str = "utf-8",
) -> str:
    """
    Detect content encoding with multiple fallback strategies.
    
    Priority:
    1. Content-Type header charset
    2. BOM detection
    3. HTML meta charset tag
    4. charset_normalizer statistical detection
    5. Default fallback
    
    Args:
        content: Raw bytes to detect encoding for
        content_type: Content-Type header value (optional)
        default: Default encoding if detection fails
    
    Returns:
        Detected encoding name (normalized)
    """
    log = logger.bind(component="EncodingDetector")

    # 1. Check Content-Type charset header
    if content_type:
        charset = _extract_charset_from_content_type(content_type)
        if charset:
            log.debug("Encoding from Content-Type", charset=charset)
            return _normalize_encoding(charset)

    # 2. Check BOM
    bom_encoding = _detect_bom(content)
    if bom_encoding:
        log.debug("Encoding from BOM", encoding=bom_encoding)
        return bom_encoding

    # 3. Check HTML meta charset (only first 1024 bytes for performance)
    meta_charset = _extract_meta_charset(content[:1024])
    if meta_charset:
        log.debug("Encoding from meta tag", charset=meta_charset)
        return _normalize_encoding(meta_charset)

    # 4. Statistical detection using charset_normalizer
    try:
        from charset_normalizer import from_bytes

        # Only use first 10KB for detection (faster, usually sufficient)
        detected = from_bytes(content[:10240]).best()
        if detected and detected.encoding:
            confidence = detected.encoding  # charset_normalizer doesn't give numeric confidence easily
            log.debug("Encoding from charset_normalizer", encoding=detected.encoding)
            return _normalize_encoding(detected.encoding)
    except ImportError:
        log.warning("charset_normalizer not installed, using default encoding")
    except Exception as e:
        log.debug("charset_normalizer detection failed", error=str(e))

    # 5. Fallback to default
    log.debug("Using default encoding", default=default)
    return default


def decode_content(
    content: bytes,
    content_type: str | None = None,
    default_encoding: str = "utf-8",
    errors: str = "replace",
) -> tuple[str, str]:
    """
    Decode bytes to string with automatic encoding detection.
    
    Args:
        content: Raw bytes to decode
        content_type: Content-Type header value (optional)
        default_encoding: Default encoding if detection fails
        errors: Error handling mode (replace, ignore, strict)
    
    Returns:
        Tuple of (decoded_string, detected_encoding)
    """
    encoding = detect_encoding(content, content_type, default_encoding)

    try:
        decoded = content.decode(encoding, errors=errors)
        return decoded, encoding
    except (UnicodeDecodeError, LookupError):
        # Fallback to default with replacement
        decoded = content.decode(default_encoding, errors="replace")
        return decoded, default_encoding


def _extract_charset_from_content_type(content_type: str) -> str | None:
    """Extract charset from Content-Type header."""
    # Example: "text/html; charset=utf-8"
    match = re.search(r'charset\s*=\s*"?([^";,\s]+)"?', content_type, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def _detect_bom(content: bytes) -> str | None:
    """Detect encoding from Byte Order Mark."""
    if content.startswith(b'\xef\xbb\xbf'):
        return 'utf-8'
    if content.startswith(b'\xff\xfe\x00\x00'):
        return 'utf-32-le'
    if content.startswith(b'\x00\x00\xfe\xff'):
        return 'utf-32-be'
    if content.startswith(b'\xff\xfe'):
        return 'utf-16-le'
    if content.startswith(b'\xfe\xff'):
        return 'utf-16-be'
    return None


def _extract_meta_charset(content: bytes) -> str | None:
    """Extract charset from HTML <meta> tags."""
    try:
        # Decode just enough to find meta tags (ASCII-compatible)
        html_start = content.decode('ascii', errors='ignore')

        # HTML5: <meta charset="utf-8">
        match = re.search(r'<meta\s+charset\s*=\s*["\']?([^"\'>\s]+)', html_start, re.IGNORECASE)
        if match:
            return match.group(1)

        # HTML4: <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
        match = re.search(
            r'<meta\s+[^>]*content\s*=\s*["\'][^"\']*charset\s*=\s*([^"\';\s]+)',
            html_start,
            re.IGNORECASE
        )
        if match:
            return match.group(1)

        # Alternative order
        match = re.search(
            r'<meta\s+[^>]*http-equiv\s*=\s*["\']?content-type["\']?\s+[^>]*charset\s*=\s*([^"\';\s>]+)',
            html_start,
            re.IGNORECASE
        )
        if match:
            return match.group(1)

    except Exception:
        pass

    return None


def _normalize_encoding(encoding: str) -> str:
    """Normalize encoding name to Python-compatible format."""
    encoding = encoding.lower().strip()

    # Common aliases
    aliases = {
        'iso-8859-1': 'iso-8859-1',
        'iso_8859_1': 'iso-8859-1',
        'latin1': 'iso-8859-1',
        'latin-1': 'iso-8859-1',
        'windows-1252': 'cp1252',
        'win-1252': 'cp1252',
        'utf8': 'utf-8',
        'utf-8': 'utf-8',
        'ascii': 'ascii',
        'us-ascii': 'ascii',
    }

    return aliases.get(encoding, encoding)
