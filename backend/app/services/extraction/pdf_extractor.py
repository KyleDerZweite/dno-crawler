"""
PDF extraction utilities for DNO data extraction.

Uses pdfplumber to extract text and tables from Netzentgelte PDFs.
"""

import re
from pathlib import Path
from typing import Any

import pdfplumber
import structlog

from app.core.constants import normalize_voltage_level

# Import voltage level normalization from shared constants

logger = structlog.get_logger()


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
    """
    Parse Netzentgelte data from raw text.

    Handles multiple PDF formats:
    1. Standard: Voltage level followed by 4 numbers in a row
    2. With units: "17,84 EUR / kW a" style values
    3. Separate tables for <2500h and >=2500h
    """
    records = []

    # Pattern 1: Standard format - voltage level with 4 numbers on same line
    # Example: Hochspannungsnetz   26,88  8,58  230,39  0,44
    pattern1 = r"((?:Hochspannung|Mittelspannung|Niederspannung|Umspannung|MSP|NSP|HS|MS|NS)[^\n\d]*)\s+([\d,\.]+)\s+([\d,\.]+)\s+([\d,\.]+)\s+([\d,\.]+)"

    # Pattern 2: Format with units embedded - extract just the number
    # Example: Mittelspannung (MSP)  17,84 EUR / kW a  5,12 Ct / kWh
    # Match: voltage level, then pairs of (number, unit)

    # Try Pattern 1 first
    matches = re.findall(pattern1, text, re.IGNORECASE)

    for match in matches:
        voltage_level_raw = match[0].strip()
        voltage_level_raw = re.sub(r'\s+', ' ', voltage_level_raw).strip()
        voltage_level = normalize_voltage_level(voltage_level_raw)

        try:
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

    # If Pattern 1 found results, return them
    if records:
        return records

    # Try Pattern 2: Parse tables with units embedded
    # This format often has TWO separate tables (unter 2500h and über 2500h)
    # Look for sections marked by "bis zu 2.500 Stunden" and "über 2.500 Stunden"

    unter_section = ""
    uber_section = ""

    # Split text by usage threshold markers
    unter_match = re.search(r"bis\s+(?:zu\s+)?2\.?500\s+Stunden[^\n]*\n(.*?)(?=über\s+2\.?500\s+Stunden|$)", text, re.IGNORECASE | re.DOTALL)
    uber_match = re.search(r"über\s+2\.?500\s+Stunden[^\n]*\n(.*?)(?=bis\s+(?:zu\s+)?2\.?500\s+Stunden|$)", text, re.IGNORECASE | re.DOTALL)

    if unter_match:
        unter_section = unter_match.group(1)
    if uber_match:
        uber_section = uber_match.group(1)

    # Parse voltage levels from each section
    voltage_patterns = [
        (r"Mittelspannung\s*\(?MSP\)?", "MS"),
        (r"Umspannung\s*MSP\s*/?\s*NSP", "MS/NS"),
        (r"Niederspannung\s*\(?NSP\)?", "NS"),
        (r"Hochspannung\s*\(?(?:HS|HSP)\)?", "HS"),
        (r"Umspannung\s*(?:HS|HSP)\s*/?\s*(?:MS|MSP)", "HS/MS"),
    ]

    def extract_prices_from_section(section_text: str) -> dict:
        """Extract voltage level -> (leistungspreis, arbeitspreis) from a section."""
        results = {}
        lines = section_text.split('\n')

        for line in lines:
            for vl_pattern, vl_abbrev in voltage_patterns:
                if re.search(vl_pattern, line, re.IGNORECASE):
                    # Extract Leistungspreis (EUR/kW)
                    lp_match = re.search(r"([\d,\.]+)\s*(?:EUR|€)\s*/\s*kW", line, re.IGNORECASE)
                    # Extract Arbeitspreis (Ct/kWh)
                    ap_match = re.search(r"([\d,\.]+)\s*(?:Ct|ct)\s*/\s*kWh", line, re.IGNORECASE)

                    lp = float(lp_match.group(1).replace(',', '.')) if lp_match else None
                    ap = float(ap_match.group(1).replace(',', '.')) if ap_match else None

                    if lp is not None or ap is not None:
                        results[vl_abbrev] = (lp, ap)
                    break

        return results

    # Extract from both sections
    unter_prices = extract_prices_from_section(unter_section) if unter_section else {}
    uber_prices = extract_prices_from_section(uber_section) if uber_section else {}

    # Combine into records
    all_vls = set(unter_prices.keys()) | set(uber_prices.keys())

    for vl in all_vls:
        unter_lp, unter_ap = unter_prices.get(vl, (None, None))
        uber_lp, uber_ap = uber_prices.get(vl, (None, None))

        records.append({
            "voltage_level": vl,
            "leistung_unter_2500h": unter_lp,
            "arbeit_unter_2500h": unter_ap,
            "leistung": uber_lp,
            "arbeit": uber_ap,
            "source_page": page_num,
        })

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

    log = logger.bind(pdf_path=str(pdf_path))
    log.info("Starting HLZF extraction from PDF")

    records = []

    # Voltage level patterns to look for

    try:
        with pdfplumber.open(pdf_path) as pdf:
            log.info(f"PDF has {len(pdf.pages)} pages")

            # Find the HLZF table - typically has "Hochlastzeitfenster" header
            full_text = ""

            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""
                full_text += text + "\n"

                if "hochlast" in text.lower() and "zeitfenster" in text.lower():
                    log.info(f"Found HLZF table on page {page_num}")

                    # Try to extract table from this page
                    tables = page.extract_tables()

                    # Merge fragmented tables (Netze BW 2023 issue)
                    merged_tables = _merge_tables(tables)

                    for table in merged_tables:
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


def _merge_tables(tables: list[list]) -> list[list]:
    """
    Merge fragmented tables on a page.

    Some PDFs (like Netze BW 2023) return each row as a separate table.
    This function groups tables by column count and merges them if they appear
    to be part of the same structure (e.g. one has a header).
    """
    if not tables:
        return []

    # Group tables by column count
    grouped_tables = {}  # col_count -> list of tables

    for table in tables:
        if not table or not table[0]:
            continue

        col_count = len(table[0])
        if col_count not in grouped_tables:
            grouped_tables[col_count] = []
        grouped_tables[col_count].append(table)

    merged_results = []

    for _, table_group in grouped_tables.items():
        # Check if this group looks like an HLZF table
        # We need at least one row to look like a header (contains Season keywords)
        has_header = False
        header_keywords = ["winter", "frühling", "fruehling", "sommer", "herbst"]

        full_merged_table = []

        for table in table_group:
            # Add all rows from this fragment
            full_merged_table.extend(table)

            # Check for header in this fragment
            for row in table:
                row_str = " ".join(str(c or "").lower() for c in row)
                if any(k in row_str for k in header_keywords):
                    has_header = True

        # If we found a header in this group, return it as one merged table
        # Otherwise, return the fragments as is (or ignore? Better to keep them as is for safety)
        if has_header and len(full_merged_table) > 1:
            merged_results.append(full_merged_table)
        else:
            # If no clear header, keep original fragments
            merged_results.extend(table_group)

    return merged_results


def _parse_hlzf_table(table: list[list], page_num: int) -> list[dict[str, Any]]:
    """
    Parse HLZF data from a table.

    Handles TWO table orientations:
    1. Standard: Voltage levels as rows, seasons as columns
    2. Inverted: Seasons as rows, voltage levels as columns (e.g., Stadtwerke Norderstedt)
    """
    records = []

    if not table or len(table) < 2:
        return records

    # First, detect table orientation by checking header row
    header_row = table[0]
    header_str = " ".join(str(cell or "").lower() for cell in header_row)

    # Check if header contains voltage level names (inverted table)
    voltage_keywords = ["mittelspannung", "niederspannung", "hochspannung", "umspannung", "msp", "nsp"]
    season_keywords = ["winter", "frühling", "fruehling", "sommer", "herbst"]

    has_voltage_in_header = any(kw in header_str for kw in voltage_keywords)
    has_season_in_header = any(kw in header_str for kw in season_keywords)

    if has_voltage_in_header and not has_season_in_header:
        # INVERTED TABLE: Voltage levels as columns, seasons as rows
        logger.debug("HLZF table detected as INVERTED (voltage levels as columns)")
        return _parse_hlzf_table_inverted(table, page_num)
    else:
        # STANDARD TABLE: Seasons as columns, voltage levels as rows
        logger.debug("HLZF table detected as STANDARD (seasons as columns)")
        return _parse_hlzf_table_standard(table, page_num)


def _parse_hlzf_table_inverted(table: list[list], page_num: int) -> list[dict[str, Any]]:
    """
    Parse HLZF table where voltage levels are columns and seasons are rows.

    Example format (Stadtwerke Norderstedt):
    |           | Mittelspannung | Umspannung MSP/NSP | Niederspannung |
    |-----------|----------------|---------------------|----------------|
    | Frühling  | 17:30-20:30    | k.A.                | 18:00-20:00    |
    | Sommer    | k.A.           | k.A.                | k.A.           |
    | Herbst    | 16:45-19:30    | k.A.                | 16:45-19:30    |
    | Winter    | 16:30-19:45    | k.A.                | 16:30-19:30    |
    """
    records_dict = {}  # voltage_level -> {winter: ..., fruehling: ..., etc.}

    # Parse header row to get voltage level columns
    header_row = table[0]
    voltage_columns = {}  # column_index -> normalized voltage level

    for col_idx, cell in enumerate(header_row):
        cell_str = str(cell or "").strip()
        cell_lower = cell_str.lower()

        # Check if this column is a voltage level
        if any(kw in cell_lower for kw in ["spannung", "msp", "nsp", "umspann"]):
            vl = normalize_voltage_level(cell_str)
            if vl:
                voltage_columns[col_idx] = vl
                records_dict[vl] = {"voltage_level": vl, "winter": None, "fruehling": None, "sommer": None, "herbst": None, "source_page": page_num}

    if not voltage_columns:
        return []

    # Parse data rows (seasons)
    for row in table[1:]:
        if not row or len(row) < 2:
            continue

        first_col = str(row[0] or "").lower()

        # Determine which season this row represents
        season_key = None
        if "winter" in first_col:
            season_key = "winter"
        elif "frühling" in first_col or "fruehling" in first_col or "frühjahr" in first_col:
            season_key = "fruehling"
        elif "sommer" in first_col:
            season_key = "sommer"
        elif "herbst" in first_col:
            season_key = "herbst"

        if not season_key:
            continue

        # Extract values for each voltage level column
        for col_idx, vl in voltage_columns.items():
            if col_idx < len(row):
                time_value = _clean_time_value(row[col_idx])
                records_dict[vl][season_key] = time_value

    return list(records_dict.values())


def _parse_hlzf_table_standard(table: list[list], page_num: int) -> list[dict[str, Any]]:
    """
    Parse HLZF table where seasons are columns and voltage levels are rows.

    Example format (most DNOs):
    |                    | Winter        | Frühling | Sommer | Herbst      |
    |--------------------|---------------|----------|--------|-------------|
    | Hochspannung       | 07:30-15:30   | -        | -      | 11:15-14:00 |
    | Mittelspannung     | 08:00-16:00   | -        | -      | 12:00-14:30 |
    """
    records = []

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
        if any(v in first_col for v in ["spannung", "netz", "umspann", "msp", "nsp"]):
            voltage_level = normalize_voltage_level(str(row[0]).strip())

            # Extract seasonal values using the column mapping from header
            def get_season_value(season_key, row=row):
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
        - Cleaned time string like "08:15-18:00" or "12:15-13:15\\n16:45-19:45"
        - "-" if marked as not applicable (entfällt, k.A., etc.)
        - None if empty or missing
    """
    if value is None:
        return None

    s = str(value).strip()

    # Handle empty values
    if s in {"", "-"}:
        return None

    # Handle "no value" markers - return "-" for consistency
    s_lower = s.lower()
    if "entfällt" in s_lower or "k.a." in s_lower or "keine angabe" in s_lower:
        return "-"

    # Remove "Uhr" suffix (e.g., "16:30 Uhr bis 19:30 Uhr" -> "16:30 bis 19:30")
    s = re.sub(r'\s*[Uu]hr\s*', ' ', s).strip()

    # Replace "bis" with dash (e.g., "16:30 bis 19:30" -> "16:30-19:30")
    s = re.sub(r'\s*bis\s*', '-', s, flags=re.IGNORECASE)

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
