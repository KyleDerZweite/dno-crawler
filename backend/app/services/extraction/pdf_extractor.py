"""
PDF extraction utilities for DNO data extraction.

Uses pdfplumber to extract text and tables from Netzentgelte PDFs.
"""

import re
from pathlib import Path
from typing import Any

import structlog
import pdfplumber

logger = structlog.get_logger()


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


def normalize_voltage_level(level: str) -> str:
    """
    Normalize voltage level name to standard abbreviation.
    
    Args:
        level: Raw voltage level string from document
        
    Returns:
        Standardized abbreviation (HS, HS/MS, MS, MS/NS, NS, HöS, HöS/HS)
    """
    if not level:
        return level
    
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
    
    # Return original with first letter capitalized if no match
    return level.strip()


def extract_netzentgelte_from_pdf(pdf_path: str | Path) -> list[dict[str, Any]]:
    """
    Extract Netzentgelte data from a PDF file.
    
    Looks for tables with voltage levels and prices (Leistungspreis, Arbeitspreis).
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        List of dictionaries with extracted Netzentgelte records
    """
    log = logger.bind(pdf_path=str(pdf_path))
    log.info("Starting PDF extraction")
    
    records = []
    
    # Define voltage levels to look for (German)
    voltage_patterns = [
        r"[Hh]ochspannung",
        r"[Mm]ittelspannung", 
        r"[Nn]iederspannung",
        r"[Uu]mspannung.*HS.*MS",
        r"[Uu]mspannung.*MS.*NS",
        r"HS",
        r"MS",
        r"NS",
    ]
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            log.info(f"PDF has {len(pdf.pages)} pages")
            
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""
                
                # Look for Netzentgelte data patterns
                if "netzentgelt" in text.lower() or "leistungspreis" in text.lower():
                    log.info(f"Found potential data on page {page_num}")
                    
                    # Try to extract structured data from text
                    page_records = _parse_netzentgelte_text(text, page_num)
                    records.extend(page_records)
                    
                    # Also try table extraction
                    tables = page.extract_tables()
                    for table in tables:
                        table_records = _parse_netzentgelte_table(table, page_num)
                        records.extend(table_records)
                        
    except Exception as e:
        log.error(f"Error extracting PDF: {e}")
        raise
    
    # Deduplicate records based on voltage_level
    seen = set()
    unique_records = []
    for record in records:
        vl = record.get("voltage_level", "")
        if vl and vl not in seen:
            seen.add(vl)
            unique_records.append(record)
    
    log.info(f"Extracted {len(unique_records)} unique Netzentgelte records")
    return unique_records


def _parse_netzentgelte_text(text: str, page_num: int) -> list[dict[str, Any]]:
    """Parse Netzentgelte data from raw text."""
    records = []
    
    # Pattern for voltage levels with 4 numbers (LP<2500, AP<2500, LP>=2500, AP>=2500)
    # Now also matches MSP, NSP naming used by some municipal utilities
    # Example: Hochspannungsnetz   26,88  8,58  230,39  0,44
    # Example: Mittelspannung (MSP)  31,44  9,16  228,20  1,30
    pattern = r"((?:Hochspannung|Mittelspannung|Niederspannung|Umspannung|MSP|NSP|HS|MS|NS)[^\n\d]*)\s+([\d,\.]+)\s+([\d,\.]+)\s+([\d,\.]+)\s+([\d,\.]+)"
    
    matches = re.findall(pattern, text, re.IGNORECASE)
    
    for match in matches:
        voltage_level_raw = match[0].strip()
        # Clean up voltage level name
        voltage_level_raw = re.sub(r'\s+', ' ', voltage_level_raw).strip()
        # Normalize to standard abbreviation
        voltage_level = normalize_voltage_level(voltage_level_raw)
        
        try:
            # Parse German number format (comma as decimal separator)
            lp_unter = float(match[1].replace(',', '.'))
            ap_unter = float(match[2].replace(',', '.'))
            lp = float(match[3].replace(',', '.'))
            ap = float(match[4].replace(',', '.'))
            
            records.append({
                "voltage_level": voltage_level,
                "leistung_unter_2500h": lp_unter,
                "arbeit_unter_2500h": ap_unter,
                "leistung": lp,
                "arbeit": ap,
                "source_page": page_num,
            })
        except (ValueError, IndexError) as e:
            logger.warning(f"Failed to parse numbers: {match}, error: {e}")
            continue
    
    return records


def _parse_netzentgelte_table(table: list[list], page_num: int) -> list[dict[str, Any]]:
    """Parse Netzentgelte data from a table."""
    records = []
    
    if not table or len(table) < 2:
        return records
    
    # Try to identify header row and data rows
    for row in table:
        if not row or len(row) < 3:
            continue
        
        # Check if first column looks like a voltage level
        # Also match MSP/NSP naming used by some municipal utilities
        first_col = str(row[0] or "").lower()
        if any(v in first_col for v in ["spannung", "hs", "ms", "ns", "umspann", "msp", "nsp"]):
            # Try to extract numbers from remaining columns
            numbers = []
            for cell in row[1:]:
                if cell:
                    cell_str = str(cell).replace(',', '.').strip()
                    try:
                        numbers.append(float(cell_str))
                    except ValueError:
                        continue
            
            if len(numbers) >= 4:
                # Normalize voltage level to standard abbreviation
                voltage_level = normalize_voltage_level(str(row[0]).strip())
                records.append({
                    "voltage_level": voltage_level,
                    "leistung_unter_2500h": numbers[0],
                    "arbeit_unter_2500h": numbers[1],
                    "leistung": numbers[2],
                    "arbeit": numbers[3],
                    "source_page": page_num,
                })
    
    return records


def find_pdf_url_for_dno(dno_name: str, year: int, pdf_type: str = "netzentgelte") -> str | None:
    """
    Find PDF URL for a DNO.
    
    Args:
        dno_name: Name of the DNO
        year: Year to find data for
        pdf_type: "netzentgelte" or "regelungen"
        
    Returns:
        URL to the PDF or None if not found
    """
    # Known PDF URLs for specific DNOs
    known_pdfs = {
        "netze bw": {
            "netzentgelte": {
                2025: "https://assets.ctfassets.net/xytfb1vrn7of/7vhTdFhuKlhLpC8BNOgN3e/369f35dc195a3b8890873942bd7df432/netzentgelte-strom-2025.pdf",
                2024: "https://assets.ctfassets.net/xytfb1vrn7of/6Wb8sYU8x0Fw6benikLxGo/66537b6b8070d5503b1165d2aad21b02/netzentgelte-strom-2024.pdf",
            },
            "regelungen": {
                2025: "https://assets.ctfassets.net/xytfb1vrn7of/01bujLCqkK8CFb4NgKfbnu/12f56b562fab37f09d41cc6924994e3e/regelungen-fuer-die-nutzung-des-stromverteilnetzes-2025.pdf",
                2024: "https://assets.ctfassets.net/xytfb1vrn7of/2gDZwU8Xvjl80uIctHlNYe/738081518a3240d77968d024458e2f15/regelungen-fuer-die-nutzung-des-stromverteilnetzes-2024.pdf",
            },
        },
    }
    
    dno_key = dno_name.lower().strip()
    
    if dno_key in known_pdfs:
        pdf_dict = known_pdfs[dno_key].get(pdf_type, {})
        return pdf_dict.get(year)
    
    return None


def extract_hlzf_from_pdf(pdf_path: str | Path) -> list[dict[str, Any]]:
    """
    Extract HLZF (Hochlastzeitfenster) data from Regelungen PDF.
    
    Looks for the characteristic HLZF table with voltage levels and seasonal time windows.
    
    Args:
        pdf_path: Path to the Regelungen PDF file
        
    Returns:
        List of dictionaries with HLZF records per voltage level
    """
    import re
    
    log = logger.bind(pdf_path=str(pdf_path))
    log.info("Starting HLZF extraction from PDF")
    
    records = []
    
    # Voltage level patterns to look for
    voltage_patterns = {
        "Hochspannungsnetz": r"Hochspannung(?:snetz)?(?!\s*zur)",
        "Umspannung zur Mittelspannung": r"Umspannung\s+(?:zur\s+)?(?:Hoch-?\/?)?Mittelspannung|MS\/HS",
        "Mittelspannungsnetz": r"Mittelspannung(?:snetz)?(?!\s*zur)",
        "Umspannung zur Niederspannung": r"Umspannung\s+(?:zur\s+)?(?:Mittel-?\/?)?Niederspannung|NS\/MS",
        "Niederspannungsnetz": r"Niederspannung(?:snetz)?",
    }
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            log.info(f"PDF has {len(pdf.pages)} pages")
            
            # Find the HLZF table - typically has "Hochlastzeitfenster" header
            full_text = ""
            hlzf_page = None
            
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""
                full_text += text + "\n"
                
                if "hochlast" in text.lower() and "zeitfenster" in text.lower():
                    hlzf_page = page_num
                    log.info(f"Found HLZF table on page {page_num}")
                    
                    # Try to extract table from this page
                    tables = page.extract_tables()
                    for table in tables:
                        hlzf_records = _parse_hlzf_table(table, page_num)
                        if hlzf_records:
                            records.extend(hlzf_records)
                            log.info(f"Extracted {len(hlzf_records)} HLZF records from table")
            
            # If no table extraction worked, try text-based extraction
            if not records:
                log.info("Table extraction failed, trying text-based extraction")
                records = _parse_hlzf_text(full_text)
                
    except Exception as e:
        log.error(f"Error extracting HLZF from PDF: {e}")
        raise
    
    log.info(f"Extracted {len(records)} HLZF records")
    return records


def _parse_hlzf_table(table: list[list], page_num: int) -> list[dict[str, Any]]:
    """Parse HLZF data from a table."""
    records = []
    
    if not table or len(table) < 2:
        return records
    
    # Look for header row with seasons
    header_row_idx = None
    header_row = None
    for i, row in enumerate(table):
        row_str = str(row).lower()
        if row and any(s in row_str for s in ["winter", "frühling", "sommer", "herbst"]):
            header_row_idx = i
            header_row = row
            break
    
    if header_row_idx is None:
        return records
    
    # Parse header to determine column indices for each season
    # This handles tables where seasons appear in any order
    season_columns = {
        "winter": None,
        "fruehling": None,
        "sommer": None,
        "herbst": None,
    }
    
    for col_idx, cell in enumerate(header_row):
        cell_lower = str(cell or "").lower()
        if "winter" in cell_lower:
            season_columns["winter"] = col_idx
        elif "frühling" in cell_lower or "fruehling" in cell_lower or "frühjahr" in cell_lower:
            season_columns["fruehling"] = col_idx
        elif "sommer" in cell_lower:
            season_columns["sommer"] = col_idx
        elif "herbst" in cell_lower:
            season_columns["herbst"] = col_idx
    
    logger.debug(f"HLZF season column mapping: {season_columns}")
    
    # Parse data rows after header
    for row in table[header_row_idx + 1:]:
        if not row or len(row) < 2:
            continue
        
        first_col = str(row[0] or "").lower()
        
        # Check if this is a voltage level row
        if any(v in first_col for v in ["spannung", "netz", "umspann"]):
            voltage_level = str(row[0]).strip()
            
            # Extract seasonal values using the column mapping from header
            def get_season_value(season_key):
                col_idx = season_columns.get(season_key)
                if col_idx is not None and col_idx < len(row):
                    return _clean_time_value(row[col_idx])
                return None
            
            records.append({
                "voltage_level": voltage_level,
                "winter": get_season_value("winter"),
                "fruehling": get_season_value("fruehling"),
                "sommer": get_season_value("sommer"),
                "herbst": get_season_value("herbst"),
                "source_page": page_num,
            })
    
    return records


def _parse_hlzf_text(text: str) -> list[dict[str, Any]]:
    """Parse HLZF data from raw text when table extraction fails."""
    import re
    
    records = []
    
    # This is a fallback - try to find time patterns near voltage level keywords
    voltage_levels = [
        "Hochspannungsnetz",
        "Umspannung zur Mittelspannung",
        "Mittelspannungsnetz", 
        "Umspannung zur Niederspannung",
        "Niederspannungsnetz",
    ]
    
    # Time pattern: XX:XX-XX:XX
    time_pattern = r"(\d{1,2}:\d{2})-(\d{1,2}:\d{2})"
    
    for voltage in voltage_levels:
        # Find the voltage level in text and extract nearby time patterns
        pattern = rf"{re.escape(voltage)}[^\n]*?((?:\d{{1,2}}:\d{{2}}-\d{{1,2}}:\d{{2}}[\s\n]*)+)"
        match = re.search(pattern, text, re.IGNORECASE)
        
        if match:
            times = re.findall(time_pattern, match.group(1))
            if times:
                time_str = "\n".join([f"{t[0]}-{t[1]}" for t in times])
                records.append({
                    "voltage_level": voltage,
                    "winter": time_str,  # Assuming Winter since that's most common
                    "fruehling": None,
                    "sommer": None,
                    "herbst": None,
                    "source_page": 0,
                })
    
    return records


def _clean_time_value(value: Any) -> str | None:
    """
    Clean and normalize a time window value.
    
    Returns:
        - Cleaned time string like "08:15-18:00" or "12:15-13:15\n16:45-19:45"
        - "entfällt" if explicitly marked as not applicable
        - None if empty or missing
    """
    if value is None:
        return None
    
    s = str(value).strip()
    
    # Handle empty values
    if s == "" or s == "-":
        return None
    
    # Handle "entfällt" (not applicable) - return explicit marker, not None
    if "entfällt" in s.lower():
        return "entfällt"
    
    # Clean up time format: "08:15 - 18:00" or "08:15\n-\n18:00" -> "08:15-18:00"
    # First, normalize all whitespace/newlines around dashes
    s = re.sub(r'\s*-\s*', '-', s)
    s = re.sub(r'\s*–\s*', '-', s)  # en-dash
    s = re.sub(r'\s*—\s*', '-', s)  # em-dash
    
    # Multiple time ranges separated by newlines should be cleaned
    # "12:15-13:15\n16:45-19:45" is valid format
    # Split by remaining whitespace into potential time ranges
    parts = s.split()
    cleaned_parts = []
    for part in parts:
        part = part.strip()
        # Check if it looks like a time range (HH:MM-HH:MM)
        if re.match(r'^\d{1,2}:\d{2}-\d{1,2}:\d{2}$', part):
            cleaned_parts.append(part)
    
    if cleaned_parts:
        return "\n".join(cleaned_parts)
    
    # If no clean time ranges found, return the stripped value as-is
    # (might need manual review)
    return s if s else None
