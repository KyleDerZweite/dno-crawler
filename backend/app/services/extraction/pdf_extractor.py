"""
PDF extraction utilities for DNO data extraction.

Uses pdfplumber to extract text and tables from Netzentgelte PDFs.
"""

import asyncio
import re
from pathlib import Path
from typing import Any

import pdfplumber
import structlog

from app.core.constants import normalize_voltage_level
from app.core.parsers import parse_german_number

logger = structlog.get_logger()


def _parse_number_or_log(raw: str, field: str, page_num: int, voltage_level: str) -> float:
    """Parse numeric values and log malformed entries instead of silently skipping."""
    value = parse_german_number(raw)
    if value is None:
        logger.warning(
            "pdf_number_parse_failed",
            field=field,
            raw_value=raw,
            source_page=page_num,
            voltage_level=voltage_level,
        )
        raise ValueError(f"Invalid number: {raw}")
    return value


async def extract_netzentgelte_from_pdf_async(pdf_path: str | Path) -> list[dict[str, Any]]:
    """Async wrapper for extract_netzentgelte_from_pdf.

    Wraps the synchronous pdfplumber operations in asyncio.to_thread()
    to avoid blocking the event loop.
    """
    return await asyncio.to_thread(extract_netzentgelte_from_pdf, pdf_path)


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
            log.info("pdf_opened", page_count=len(pdf.pages))

            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""

                # Look for Netzentgelte data patterns
                if "netzentgelt" in text.lower() or "leistungspreis" in text.lower():
                    log.info("potential_data_found", page=page_num)

                    # Try to extract structured data from text
                    page_records = _parse_netzentgelte_text(text, page_num)
                    records.extend(page_records)

                    # Also try table extraction
                    tables = page.extract_tables()
                    for table in tables:
                        table_records = _parse_netzentgelte_table(table, page_num)
                        records.extend(table_records)

    except Exception as e:
        log.error("pdf_extraction_error", error=str(e))
        raise

    # Deduplicate records based on voltage_level
    seen = set()
    unique_records = []
    for record in records:
        vl = record.get("voltage_level", "")
        if vl and vl not in seen:
            seen.add(vl)
            unique_records.append(record)

    log.info("netzentgelte_extracted", record_count=len(unique_records))
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

    # Pattern 1: Standard four-number row format.
    # Why: larger DNO tariff sheets often render one voltage row with four values
    # (unter/über 2500h x Leistung/Arbeit) on a single line after PDF text extraction.
    # Example: Hochspannungsnetz   26,88  8,58  230,39  0,44
    # Also matches kV-based names: "Umspannung 20/0,4kV   26,88  8,58  230,39  0,44"
    pattern1 = r"((?:Hochspannung|Mittelspannung|Niederspannung|Umspannung|MSP|NSP|HS|MS|NS)(?:\s+\d+(?:[,\.]\d+)?(?:\s*/\s*\d+(?:[,\.]\d+)?)?\s*kV)?[^\n\d]*)\s+([\d,\.]+)\s+([\d,\.]+)\s+([\d,\.]+)\s+([\d,\.]+)"

    # Pattern 2 fallback is section-based extraction with embedded units.
    # Why: many municipal utility PDFs split "bis/über 2.500 Stunden" into separate
    # sections and include units inline; simple row regex then misses combinations.

    # Try Pattern 1 first
    matches = re.findall(pattern1, text, re.IGNORECASE)

    for match in matches:
        voltage_level_raw = match[0].strip()
        voltage_level_raw = re.sub(r"\s+", " ", voltage_level_raw).strip()
        voltage_level = normalize_voltage_level(voltage_level_raw)

        try:
            lp_unter = _parse_number_or_log(
                match[1], "leistung_unter_2500h", page_num, voltage_level
            )
            ap_unter = _parse_number_or_log(match[2], "arbeit_unter_2500h", page_num, voltage_level)
            lp = _parse_number_or_log(match[3], "leistung", page_num, voltage_level)
            ap = _parse_number_or_log(match[4], "arbeit", page_num, voltage_level)

            records.append(
                {
                    "voltage_level": voltage_level,
                    "leistung_unter_2500h": lp_unter,
                    "arbeit_unter_2500h": ap_unter,
                    "leistung": lp,
                    "arbeit": ap,
                    "source_page": page_num,
                }
            )
        except (ValueError, IndexError) as e:
            logger.warning(
                "pdf_parse_row_failed",
                raw_match=match,
                source_page=page_num,
                error=str(e),
            )
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
    unter_match = re.search(
        r"bis\s+(?:zu\s+)?2\.?500\s+Stunden[^\n]*\n(.*?)(?=über\s+2\.?500\s+Stunden|$)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    uber_match = re.search(
        r"über\s+2\.?500\s+Stunden[^\n]*\n(.*?)(?=bis\s+(?:zu\s+)?2\.?500\s+Stunden|$)",
        text,
        re.IGNORECASE | re.DOTALL,
    )

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
        lines = section_text.split("\n")

        for line in lines:
            for vl_pattern, vl_abbrev in voltage_patterns:
                if re.search(vl_pattern, line, re.IGNORECASE):
                    # Extract Leistungspreis (EUR/kW)
                    lp_match = re.search(r"([\d,\.]+)\s*(?:EUR|€)\s*/\s*kW", line, re.IGNORECASE)
                    # Extract Arbeitspreis (Ct/kWh)
                    ap_match = re.search(r"([\d,\.]+)\s*(?:Ct|ct)\s*/\s*kWh", line, re.IGNORECASE)

                    lp = float(lp_match.group(1).replace(",", ".")) if lp_match else None
                    ap = float(ap_match.group(1).replace(",", ".")) if ap_match else None

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

        records.append(
            {
                "voltage_level": vl,
                "leistung_unter_2500h": unter_lp,
                "arbeit_unter_2500h": unter_ap,
                "leistung": uber_lp,
                "arbeit": uber_ap,
                "source_page": page_num,
            }
        )

    return records


def _parse_netzentgelte_table(table: list[list], page_num: int) -> list[dict[str, Any]]:
    """Parse Netzentgelte data from a table.

    Handles two table layouts:
    1. Standard: voltage level in column 0, 4 price columns
    2. Split sections: unter/über 2500h as separate sub-tables within one table,
       voltage level in column 1 (column 0 is a row number like "4", "5"), 2 prices each
       (e.g. EWE NETZ format)
    """
    if not table or len(table) < 2:
        return []

    # Long keywords safe for substring matching
    _VL_KEYWORDS_LONG = ["spannung", "umspann", "netz"]
    # Short keywords need word boundary matching to avoid false positives
    # (e.g. "hs" in "Verbrauchseinrichtung", "ns" in "sonstige")
    _VL_KEYWORDS_SHORT_RE = re.compile(r"\b(?:hs|ms|ns|msp|nsp|kv)\b")

    def _find_voltage_col(row: list) -> int | None:
        """Find the column index containing a voltage level keyword."""
        for ci, cell in enumerate(row):
            cell_lower = str(cell or "").lower()
            if any(v in cell_lower for v in _VL_KEYWORDS_LONG):
                return ci
            if _VL_KEYWORDS_SHORT_RE.search(cell_lower):
                return ci
        return None

    def _extract_numbers(row: list, start_col: int) -> list[float]:
        """Extract numeric values from columns starting at start_col."""
        numbers = []
        for cell in row[start_col:]:
            if cell:
                cell_str = str(cell).replace(",", ".").strip()
                try:
                    numbers.append(float(cell_str))
                except ValueError:
                    continue
        return numbers

    # Track unter/über 2500h sections for split-table format
    current_section: str | None = None  # "unter" or "uber"
    vl_data: dict[str, dict[str, Any]] = {}

    # Track pending multi-row voltage labels: some PDFs (e.g. EWR Netz)
    # split the voltage label across two rows:
    #   Row 1: "Umspannung"    + prices (42,20 / 5,55 / 169,09 / 0,48)
    #   Row 2: "110 kV / 20 kV" (no prices)
    # We hold numbers from row 1 and resolve the label on row 2.
    pending_numbers: list[float] | None = None

    for row in table:
        if not row or len(row) < 2:
            continue

        row_text = " ".join(str(c or "") for c in row).lower()

        # Detect section markers (< 2500h / >= 2500h)
        if "2500" in row_text or "2.500" in row_text:
            if any(m in row_text for m in ["< 2", "bis", "unter"]):
                current_section = "unter"
                continue
            if any(m in row_text for m in ["≥ 2", ">= 2", "über", "ab 2"]):
                current_section = "uber"
                continue

        # Find voltage level in any column
        vl_col = _find_voltage_col(row)
        if vl_col is None:
            continue

        voltage_level = normalize_voltage_level(str(row[vl_col]).strip())
        numbers = _extract_numbers(row, vl_col + 1)

        if not voltage_level:
            # Unresolved label (e.g. just "Umspannung") — hold numbers for next row
            if numbers:
                pending_numbers = numbers
            continue

        # Resolved voltage level — use pending numbers if this row has none
        if not numbers and pending_numbers is not None:
            numbers = pending_numbers
        pending_numbers = None  # Clear regardless

        if not numbers:
            continue

        if voltage_level not in vl_data:
            vl_data[voltage_level] = {
                "voltage_level": voltage_level,
                "leistung_unter_2500h": None,
                "arbeit_unter_2500h": None,
                "leistung": None,
                "arbeit": None,
                "source_page": page_num,
            }

        if len(numbers) >= 4:
            # All 4 prices in one row (standard format)
            vl_data[voltage_level]["leistung_unter_2500h"] = numbers[0]
            vl_data[voltage_level]["arbeit_unter_2500h"] = numbers[1]
            vl_data[voltage_level]["leistung"] = numbers[2]
            vl_data[voltage_level]["arbeit"] = numbers[3]
        elif len(numbers) >= 2:
            # Split format — assign to unter or über section
            if current_section == "unter":
                vl_data[voltage_level]["leistung_unter_2500h"] = numbers[0]
                vl_data[voltage_level]["arbeit_unter_2500h"] = numbers[1]
            elif current_section == "uber":
                vl_data[voltage_level]["leistung"] = numbers[0]
                vl_data[voltage_level]["arbeit"] = numbers[1]
            else:
                # No section detected — assume main prices
                vl_data[voltage_level]["leistung"] = numbers[0]
                vl_data[voltage_level]["arbeit"] = numbers[1]

    return list(vl_data.values())


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


async def extract_hlzf_from_pdf_async(pdf_path: str | Path) -> list[dict[str, Any]]:
    """Async wrapper for extract_hlzf_from_pdf.

    Wraps the synchronous pdfplumber operations in asyncio.to_thread()
    to avoid blocking the event loop.
    """
    return await asyncio.to_thread(extract_hlzf_from_pdf, pdf_path)


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
            log.info("pdf_opened", page_count=len(pdf.pages))

            # Find the HLZF table - typically has "Hochlastzeitfenster" header
            full_text = ""

            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""
                full_text += text + "\n"

                if "hochlast" in text.lower() and "zeitfenster" in text.lower():
                    log.info("hlzf_table_found", page=page_num)

                    # Try to extract table from this page
                    tables = page.extract_tables()

                    # Merge fragmented tables (Netze BW 2023 issue)
                    merged_tables = _merge_tables(tables)

                    for table in merged_tables:
                        hlzf_records = _parse_hlzf_table(table, page_num)
                        if hlzf_records:
                            records.extend(hlzf_records)
                            log.info("hlzf_records_from_table", count=len(hlzf_records))

                    # Fallback: try cross-table parsing for fragmented PDFs
                    # (e.g. season header in one table, data rows in separate tables)
                    if not records and tables:
                        cross_records = _parse_hlzf_fragmented_tables(tables, page_num)
                        if cross_records:
                            records.extend(cross_records)
                            log.info("hlzf_records_from_fragmented", count=len(cross_records))

            # If no table extraction worked, try text-based extraction
            if not records:
                log.info("table_extraction_failed_trying_text")
                records = _parse_hlzf_text(full_text)

    except Exception as e:
        log.error("hlzf_extraction_error", error=str(e))
        raise

    log.info("hlzf_extracted", record_count=len(records))
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


def _parse_hlzf_fragmented_tables(tables: list[list[list]], page_num: int) -> list[dict[str, Any]]:
    """
    Parse HLZF from fragmented tables where season header and data rows
    are in separate pdfplumber tables with different column counts.

    Common pattern: one small header table with season names, then separate
    data tables per voltage level with N columns = 1 label + seasons x (von, bis).
    """
    records = []

    # Step 1: Detect season order from any table that contains season keywords
    season_order: list[str] = []
    season_keywords_map = {
        "winter": "winter",
        "frühling": "fruehling",
        "fruehling": "fruehling",
        "frühjahr": "fruehling",
        "sommer": "sommer",
        "herbst": "herbst",
    }

    for table in tables:
        for row in table:
            row_str = " ".join(str(c or "").lower() for c in row)
            found_seasons: list[tuple[int, str]] = []
            for kw, key in season_keywords_map.items():
                idx = row_str.find(kw)
                if idx >= 0 and key not in [s for _, s in found_seasons]:
                    found_seasons.append((idx, key))
            if len(found_seasons) >= 3:
                found_seasons.sort(key=lambda x: x[0])
                season_order = [s for _, s in found_seasons]
                break
        if season_order:
            break

    if not season_order:
        return records

    num_seasons = len(season_order)

    # Step 2: Collect all data rows from all tables that start with a voltage level
    # Data tables typically have 1 + num_seasons*2 columns (label + von/bis per season)
    expected_cols = 1 + num_seasons * 2

    for table in tables:
        if not table or not table[0]:
            continue

        col_count = len(table[0])
        if col_count != expected_cols:
            continue

        # Parse rows: first col is voltage level label, rest are von/bis pairs
        current_vl: str | None = None
        vl_times: dict[str, list[list[dict[str, str]]]] = {}  # vl -> list of season arrays

        for row in table:
            label = str(row[0] or "").strip()
            label_lower = label.lower()

            # Check if this row starts a new voltage level
            if label and any(
                v in label_lower
                for v in ["spannung", "netz", "umspann", "msp", "nsp", "ms", "ns", "hs", "kv"]
            ):
                current_vl = normalize_voltage_level(label)
                if current_vl and current_vl not in vl_times:
                    vl_times[current_vl] = [[] for _ in range(num_seasons)]

            if not current_vl:
                continue

            # Extract von/bis pairs for each season
            for s_idx in range(num_seasons):
                von_col = 1 + s_idx * 2
                bis_col = 2 + s_idx * 2
                if von_col < len(row) and bis_col < len(row):
                    von = str(row[von_col] or "").strip()
                    bis = str(row[bis_col] or "").strip()
                    if (
                        von
                        and bis
                        and re.match(r"\d{1,2}:\d{2}", von)
                        and re.match(r"\d{1,2}:\d{2}", bis)
                    ):
                        vl_times[current_vl][s_idx].append({"start": von, "end": bis})

        # Build records from collected data
        for vl, times in vl_times.items():
            season_dict: dict[str, list[dict[str, str]] | None] = {
                "winter": None,
                "fruehling": None,
                "sommer": None,
                "herbst": None,
            }
            has_any = False
            for s_idx, s_key in enumerate(season_order):
                if s_idx < len(times) and times[s_idx]:
                    season_dict[s_key] = times[s_idx]
                    has_any = True
            if has_any:
                records.append(
                    {
                        "voltage_level": vl,
                        "source_page": page_num,
                        **season_dict,
                    }
                )

    return records


def _split_hlzf_table_by_year(table: list[list]) -> list[tuple[int, list[list]]] | None:
    """Split a multi-year HLZF table into per-year sub-tables.

    Detects rows containing "Hochlastzeitfenster YYYY" and splits the table
    at those boundaries. Returns None if fewer than 2 year sections found
    (i.e. single-year or no year markers).
    """
    year_indices: list[tuple[int, int]] = []
    for i, row in enumerate(table):
        row_text = " ".join(str(c or "") for c in row)
        match = re.search(r"[Hh]ochlastzeitfenster\s+(\d{4})", row_text)
        if match:
            year_indices.append((i, int(match.group(1))))

    if len(year_indices) < 2:
        return None

    sections = []
    for idx, (start_row, year_val) in enumerate(year_indices):
        end_row = year_indices[idx + 1][0] if idx + 1 < len(year_indices) else len(table)
        sub_table = table[start_row:end_row]
        if len(sub_table) >= 2:  # Need at least header + one data row
            sections.append((year_val, sub_table))

    return sections if sections else None


def _parse_hlzf_table(table: list[list], page_num: int) -> list[dict[str, Any]]:
    """
    Parse HLZF data from a table.

    Handles:
    1. Multi-year tables: splits by "Hochlastzeitfenster YYYY" sections
    2. Standard orientation: Voltage levels as rows, seasons as columns
    3. Inverted orientation: Seasons as rows, voltage levels as columns
    """
    if not table or len(table) < 2:
        return []

    # Check for multi-year sections ("Hochlastzeitfenster YYYY" rows)
    year_sections = _split_hlzf_table_by_year(table)
    if year_sections:
        all_records: list[dict[str, Any]] = []
        for year_val, sub_table in year_sections:
            # Recurse — sub-tables have only 1 year marker so won't split again
            section_records = _parse_hlzf_table(sub_table, page_num)
            for r in section_records:
                r["year"] = year_val
            all_records.extend(section_records)
        return all_records

    # Detect table orientation by checking header row
    header_row = table[0]
    header_str = " ".join(str(cell or "").lower() for cell in header_row)

    voltage_keywords = [
        "mittelspannung",
        "niederspannung",
        "hochspannung",
        "umspannung",
        "msp",
        "nsp",
        "kv",
    ]
    season_keywords = ["winter", "frühling", "fruehling", "sommer", "herbst"]

    has_voltage_in_header = any(kw in header_str for kw in voltage_keywords)
    has_season_in_header = any(kw in header_str for kw in season_keywords)

    # Fallback: try normalizing individual cells for short VL abbreviations
    # (catches "MS", "NS", "U HS/MS", etc. that long keywords miss)
    if not has_voltage_in_header:
        for cell in header_row:
            cell_str = str(cell or "").strip()
            if cell_str and normalize_voltage_level(cell_str):
                has_voltage_in_header = True
                break

    if has_voltage_in_header and not has_season_in_header:
        logger.debug("HLZF table detected as INVERTED (voltage levels as columns)")
        return _parse_hlzf_table_inverted(table, page_num)
    else:
        logger.debug("HLZF table detected as STANDARD (seasons as columns)")
        return _parse_hlzf_table_standard(table, page_num)


def _parse_hlzf_table_inverted(table: list[list], page_num: int) -> list[dict[str, Any]]:
    """
    Parse HLZF table where voltage levels are columns and seasons are rows.

    Handles:
    - Long VL names ("Mittelspannung") and short abbreviations ("MS", "U HS/MS")
    - Single-column times ("07:00-19:30") and paired columns ("07:00" | "19:30")
    - Multiple rows per season (accumulated into time window lists)
    """
    records_dict: dict[str, dict[str, Any]] = {}

    # Parse header row to get voltage level columns
    header_row = table[0]
    voltage_columns: dict[int, str] = {}

    for col_idx, cell in enumerate(header_row):
        cell_str = str(cell or "").strip()
        if not cell_str:
            continue

        # Try normalizing — handles both long names and short abbreviations
        vl = normalize_voltage_level(cell_str)
        if vl and vl not in voltage_columns.values():
            voltage_columns[col_idx] = vl
            records_dict[vl] = {
                "voltage_level": vl,
                "winter": None,
                "fruehling": None,
                "sommer": None,
                "herbst": None,
                "source_page": page_num,
            }

    if not voltage_columns:
        return []

    # Detect paired columns: VL header in col N, data extends to col N+1
    # (e.g., separate "von" and "bis" columns per voltage level)
    paired_columns = False
    if len(voltage_columns) >= 2:
        vl_cols = sorted(voltage_columns.keys())
        gaps = [vl_cols[i + 1] - vl_cols[i] for i in range(len(vl_cols) - 1)]
        paired_columns = all(g == 2 for g in gaps)

    # Parse data rows — track current season across rows for multi-window support
    current_season: str | None = None
    for row in table[1:]:
        if not row or len(row) < 2:
            continue

        # Detect season from first few columns (handles label in any early column)
        row_prefix = " ".join(str(c or "") for c in row[:4]).lower()

        if re.search(r"\bwinter\b", row_prefix):
            current_season = "winter"
        elif re.search(r"\b(?:frühling|fruehling|frühjahr)\b", row_prefix):
            current_season = "fruehling"
        elif re.search(r"\bsommer\b", row_prefix):
            current_season = "sommer"
        elif re.search(r"\bherbst\b", row_prefix):
            current_season = "herbst"

        if not current_season:
            continue

        # Extract values for each voltage level column
        for col_idx, vl in voltage_columns.items():
            if col_idx >= len(row):
                continue

            if paired_columns and col_idx + 1 < len(row):
                # Combine paired columns into a time range
                cell1 = str(row[col_idx] or "").strip()
                cell2 = str(row[col_idx + 1] or "").strip()
                combined = f"{cell1}-{cell2}" if cell1 and cell2 else cell1 or cell2
                time_value = _clean_time_value(combined)
            else:
                time_value = _clean_time_value(row[col_idx])

            # Accumulate time windows (multiple rows per season)
            if time_value:
                if records_dict[vl][current_season] is None:
                    records_dict[vl][current_season] = []
                records_dict[vl][current_season].extend(time_value)

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
    for row in table[header_row_idx + 1 :]:
        if not row or len(row) < 2:
            continue

        first_col = str(row[0] or "").lower()

        # Check if this is a voltage level row
        if any(v in first_col for v in ["spannung", "netz", "umspann", "msp", "nsp", "kv"]):
            voltage_level = normalize_voltage_level(str(row[0]).strip())

            # Extract seasonal values using the column mapping from header
            def get_season_value(season_key, row=row):
                col_idx = season_columns.get(season_key)
                if col_idx is not None and col_idx < len(row):
                    return _clean_time_value(row[col_idx])
                return None

            records.append(
                {
                    "voltage_level": voltage_level,
                    "winter": get_season_value("winter"),
                    "fruehling": get_season_value("fruehling"),
                    "sommer": get_season_value("sommer"),
                    "herbst": get_season_value("herbst"),
                    "source_page": page_num,
                }
            )

    return records


def _split_hlzf_text_by_year(text: str) -> list[tuple[int, str]] | None:
    """Split text into per-year sections at 'Hochlastzeitfenster YYYY' boundaries.

    Returns None if fewer than 2 year sections found (single-year or no markers).
    """
    matches = list(re.finditer(r"[Hh]ochlastzeitfenster\s+(\d{4})", text))
    if len(matches) < 2:
        return None

    sections = []
    for i, m in enumerate(matches):
        year_val = int(m.group(1))
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((year_val, text[start:end]))

    return sections


def _parse_hlzf_text(text: str) -> list[dict[str, Any]]:
    """Parse HLZF data from raw text when table extraction fails.

    Handles multi-year documents by splitting at "Hochlastzeitfenster YYYY"
    boundaries first, then parsing each section independently.

    Uses a two-pass approach per section:
    1. Find voltage level positions in text (full names and abbreviations)
    2. Find time ranges (HH:MM patterns) and associate them with the nearest
       preceding voltage level, mapping to seasons by column position.
    """
    # Check for multi-year sections
    year_sections = _split_hlzf_text_by_year(text)
    if year_sections:
        all_records: list[dict[str, Any]] = []
        for year_val, section_text in year_sections:
            # Recurse — single sections won't trigger splitting again
            records = _parse_hlzf_text(section_text)
            for r in records:
                r["year"] = year_val
            all_records.extend(records)
        return all_records

    records: list[dict[str, Any]] = []

    # Voltage level labels to search for — sorted longest first to avoid
    # short labels (e.g. "MS") claiming positions inside longer ones ("MS/NS")
    voltage_labels = sorted(
        [
            ("Hochspannungsnetz", "HS"),
            ("Hochspannung", "HS"),
            ("Umspannung zur Mittelspannung", "HS/MS"),
            ("Umspannung HS/MS", "HS/MS"),
            ("HS/MS", "HS/MS"),
            ("Mittelspannungsnetz", "MS"),
            ("Mittelspannung", "MS"),
            ("MS", "MS"),
            ("Umspannung zur Niederspannung", "MS/NS"),
            ("Umspannung MS/NS", "MS/NS"),
            ("MS/NS", "MS/NS"),
            ("Niederspannungsnetz", "NS"),
            ("Niederspannung", "NS"),
            ("NS", "NS"),
            ("HS", "HS"),
            # kV-based naming (e.g. EWE)
            ("Umspannung 110/20kV", "HS/MS"),
            ("Umspannung 110/10kV", "HS/MS"),
            ("Umspannung 20/0,4kV", "MS/NS"),
            ("Umspannung 10/0,4kV", "MS/NS"),
            ("110kV", "HS"),
            ("20kV", "MS"),
            ("10kV", "MS"),
        ],
        key=lambda x: len(x[0]),
        reverse=True,
    )

    # Detect season order from headers in the text
    season_names = [
        ("fruehling", r"Fr[üu]h(?:ling|jahr)"),
        ("sommer", r"Sommer"),
        ("herbst", r"Herbst"),
        ("winter", r"Winter"),
    ]

    # Find season header positions to determine column order
    season_order: list[str] = []
    season_positions: list[tuple[int, str]] = []
    for key, pattern in season_names:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            season_positions.append((m.start(), key))
    season_positions.sort(key=lambda x: x[0])
    # Deduplicate (take first occurrence of each)
    seen_seasons: set[str] = set()
    for _, key in season_positions:
        if key not in seen_seasons:
            season_order.append(key)
            seen_seasons.add(key)

    if not season_order:
        # Default order if no season headers found
        season_order = ["winter", "fruehling", "sommer", "herbst"]

    num_seasons = len(season_order)

    # Find all voltage level positions in the text
    vl_positions: list[tuple[int, str]] = []  # (position, normalized_level)
    claimed_ranges: list[tuple[int, int]] = []  # (start, end) of already-claimed matches

    for label, normalized in voltage_labels:
        for m in re.finditer(re.escape(label), text, re.IGNORECASE):
            # Skip if this match overlaps with an already-claimed range
            if any(not (m.end() <= cs or m.start() >= ce) for cs, ce in claimed_ranges):
                continue
            # For short abbreviations (2-5 chars), require word boundaries
            if len(label) <= 5:
                before = text[m.start() - 1] if m.start() > 0 else " "
                after = text[m.end()] if m.end() < len(text) else " "
                if before.isalnum() or after.isalnum():
                    continue
            vl_positions.append((m.start(), normalized))
            claimed_ranges.append((m.start(), m.end()))

    # Sort by position and deduplicate overlapping voltage levels
    vl_positions.sort(key=lambda x: x[0])

    # Deduplicate: if same normalized level appears multiple times, keep first
    seen_vls: set[str] = set()
    unique_vl_positions: list[tuple[int, str]] = []
    for pos, vl in vl_positions:
        if vl not in seen_vls:
            unique_vl_positions.append((pos, vl))
            seen_vls.add(vl)
    vl_positions = unique_vl_positions

    if not vl_positions:
        return records

    # Find all time ranges in the text: HH:MM - HH:MM (with various separators or just whitespace)
    time_range_pattern = r"(\d{1,2}:\d{2})\s*[-–—‐\s]\s*(\d{1,2}:\d{2})"
    time_matches = [
        (m.start(), m.group(1), m.group(2)) for m in re.finditer(time_range_pattern, text)
    ]

    # For each voltage level, collect the time ranges that follow it
    # (up to the next voltage level or end of text)
    for i, (vl_pos, vl_name) in enumerate(vl_positions):
        # Determine the text region for this voltage level
        next_vl_pos = vl_positions[i + 1][0] if i + 1 < len(vl_positions) else len(text)

        # Collect time ranges in this region
        vl_times = [
            (pos, start, end) for pos, start, end in time_matches if vl_pos <= pos < next_vl_pos
        ]

        if not vl_times:
            continue

        # Map time ranges to seasons
        # Each season gets one time range (von-bis), assigned in season_order
        season_values: dict[str, list[dict[str, str]] | None] = dict.fromkeys(
            ["winter", "fruehling", "sommer", "herbst"], None
        )

        for j, (_, start_time, end_time) in enumerate(vl_times):
            if j < num_seasons:
                season_key = season_order[j]
                if season_values[season_key] is None:
                    season_values[season_key] = []
                season_values[season_key].append({"start": start_time, "end": end_time})

        records.append(
            {
                "voltage_level": vl_name,
                "source_page": 0,
                **season_values,
            }
        )

    return records


def _clean_time_value(value: Any) -> list[dict[str, str]] | None:
    """
    Clean and normalize a time window value from a PDF cell.

    Returns a structured list of time range dicts, or None if no valid data.
    """
    if value is None:
        return None

    s = str(value).strip()

    # Handle empty values
    if s in {"", "-"}:
        return None

    # Handle "no value" markers
    s_lower = s.lower()
    if (
        s_lower == "keine"
        or "entfällt" in s_lower
        or "k.a." in s_lower
        or "keine angabe" in s_lower
    ):
        return None

    # Remove "Uhr" suffix
    s = re.sub(r"\s*[Uu]hr\s*", " ", s).strip()

    # Replace "bis" with dash
    s = re.sub(r"\s*bis\s*", "-", s, flags=re.IGNORECASE)

    # Normalize all dash types (including U+2010 HYPHEN from some PDFs)
    s = re.sub(r"\s*[-–—‐]\s*", "-", s)

    # Find all HH:MM-HH:MM patterns
    ranges = []
    for m in re.finditer(r"(\d{1,2}:\d{2})-(\d{1,2}:\d{2})", s):
        ranges.append({"start": m.group(1), "end": m.group(2)})

    return ranges if ranges else None
