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
    # Example: Hochspannungsnetz   26,88  8,58  230,39  0,44
    pattern = r"((?:Hochspannung|Mittelspannung|Niederspannung|Umspannung)[^\n\d]*)\s+([\d,\.]+)\s+([\d,\.]+)\s+([\d,\.]+)\s+([\d,\.]+)"
    
    matches = re.findall(pattern, text, re.IGNORECASE)
    
    for match in matches:
        voltage_level = match[0].strip()
        # Clean up voltage level name
        voltage_level = re.sub(r'\s+', ' ', voltage_level).strip()
        
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
        first_col = str(row[0] or "").lower()
        if any(v in first_col for v in ["spannung", "hs", "ms", "ns", "umspann"]):
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
                records.append({
                    "voltage_level": str(row[0]).strip(),
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
                2024: "https://assets.ctfassets.net/xytfb1vrn7of/01bujLCqkK8CFb4NgKfbnu/12f56b562fab37f09d41cc6924994e3e/regelungen-fuer-die-nutzung-des-stromverteilnetzes-2025.pdf",  # Using 2025 as 2024 not available
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
    header_row = None
    for i, row in enumerate(table):
        if row and any(s in str(row).lower() for s in ["winter", "frühling", "sommer", "herbst"]):
            header_row = i
            break
    
    if header_row is None:
        return records
    
    # Parse data rows after header
    for row in table[header_row + 1:]:
        if not row or len(row) < 2:
            continue
        
        first_col = str(row[0] or "").lower()
        
        # Check if this is a voltage level row
        if any(v in first_col for v in ["spannung", "netz", "umspann"]):
            voltage_level = str(row[0]).strip()
            
            # Extract seasonal values (Winter, Frühling, Sommer, Herbst)
            winter = _clean_time_value(row[1] if len(row) > 1 else None)
            fruehling = _clean_time_value(row[2] if len(row) > 2 else None)
            sommer = _clean_time_value(row[3] if len(row) > 3 else None)
            herbst = _clean_time_value(row[4] if len(row) > 4 else None)
            
            records.append({
                "voltage_level": voltage_level,
                "winter": winter,
                "fruehling": fruehling,
                "sommer": sommer,
                "herbst": herbst,
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
    """Clean and normalize a time window value."""
    if value is None:
        return None
    
    s = str(value).strip()
    
    # Handle "entfällt" (not applicable)
    if "entfällt" in s.lower() or s == "-" or s == "":
        return None
    
    # Clean up whitespace
    s = re.sub(r'\s+', '\n', s).strip()
    
    return s if s else None

