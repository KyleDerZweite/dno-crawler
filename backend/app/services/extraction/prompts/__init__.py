"""
AI Extraction Prompts

Centralized prompt templates for AI-based data extraction.
These prompts are used by the extraction step to guide AI models
in extracting structured data from PDF/HTML documents.
"""


def build_netzentgelte_prompt(dno_name: str, year: int) -> str:
    """Build the AI extraction prompt for Netzentgelte data."""
    return f"""Extract Netzentgelte (network tariffs) data from this document.

DNO: {dno_name}
Year: {year}

IMPORTANT: Extract ALL voltage levels present in the document - the number varies by DNO:
- Large DNOs typically have 5 levels: HS, HS/MS, MS, MS/NS, NS
- Small municipal utilities often only have 3 levels: MS, MS/NS, NS (no high voltage infrastructure)
- TSOs may have HöS (Höchstspannung) instead of NS

Map these voltage level names to standardized abbreviations:
- Hochspannung / Hochspannungsnetz / "inHS" / "HS" → output as "HS"
- Umspannung Hoch-/Mittelspannung / "ausHS" / "HS/MS" → output as "HS/MS"
- Mittelspannung / Mittelspannungsnetz / "inMS" / "MS" / "MSP" → output as "MS"
- Umspannung Mittel-/Niederspannung / "ausMS" / "MS/NS" / "MSP/NSP" → output as "MS/NS"
- Niederspannung / Niederspannungsnetz / "inNS" / "NS" / "NSP" → output as "NS"
- Höchstspannung / "HöS" → output as "HöS" (rare, TSO only)
- Umspannung Höchst-/Hochspannung / "ausHöS" / "HöS/HS" → output as "HöS/HS" (rare, TSO only)

SKIP any "ausHÖS" or upstream TSO entries if extracting for a DNO (not TSO).

NOTE: The document may have ONE combined table OR SEPARATE tables per voltage level.
Voltage level names may be split across multiple lines in PDFs.

German electricity tariffs often have TWO sets of prices based on annual usage:
- "< 2.500 h/a" or "unter 2500h" (under 2500 hours/year usage)
- "≥ 2.500 h/a" or "über 2500h" (2500+ hours/year usage)

For EACH voltage level found, extract:
- voltage_level: Standardized abbreviation (HS, HS/MS, MS, MS/NS, NS)
- leistung_unter_2500h: Capacity price (Leistungspreis) for < 2500h in €/kW/a, or "-" if not available
- arbeit_unter_2500h: Work price (Arbeitspreis) for < 2500h in ct/kWh, or "-" if not available
- leistung: Capacity price (Leistungspreis) for ≥ 2500h in €/kW/a, or "-" if not available
- arbeit: Work price (Arbeitspreis) for ≥ 2500h in ct/kWh, or "-" if not available

If only one set of prices exists (no usage distinction), use leistung and arbeit fields only.
Use "-" for any price that doesn't exist for this DNO/voltage level (not null).

Return the structure:
{{
  "success": true,
  "data_type": "netzentgelte",
  "source_page": <page number>,
  "notes": "<observations about the table format and which voltage levels were found>",
  "voltage_levels_found": <number of voltage levels>,
  "data": [
    {{"voltage_level": "HS", "leistung_unter_2500h": "26.88", "arbeit_unter_2500h": "8.58", "leistung": "230.39", "arbeit": "0.44"}},
    {{"voltage_level": "HS/MS", ...}},
    ...
  ]
}}
"""


def build_hlzf_prompt(dno_name: str, year: int) -> str:
    """Build the AI extraction prompt for HLZF data."""
    return f"""Extract HLZF (Hochlastzeitfenster) data from this German electricity grid document.

DNO: {dno_name}
Year: {year}

IMPORTANT: Extract ALL voltage levels present in the document - the number varies by DNO:
- Large DNOs typically have 5 levels: HS, HS/MS, MS, MS/NS, NS
- Small municipal utilities often only have 3 levels: MS, MS/NS, NS (no high voltage infrastructure)
- TSOs may have HöS (Höchstspannung) instead of NS

Map these voltage level names to standardized abbreviations:
- Hochspannung / Hochspannungsnetz / "inHS" / "HS" → output as "HS"
- Umspannung Hoch-/Mittelspannung / "ausHS" / "HS/MS" → output as "HS/MS"
- Mittelspannung / Mittelspannungsnetz / "inMS" / "MS" / "MSP" → output as "MS"
- Umspannung Mittel-/Niederspannung / "ausMS" / "MS/NS" / "MSP/NSP" → output as "MS/NS"
- Niederspannung / Niederspannungsnetz / "inNS" / "NS" / "NSP" → output as "NS"
- Höchstspannung / "HöS" → output as "HöS" (rare, TSO only)
- Umspannung Höchst-/Hochspannung / "ausHöS" / "HöS/HS" → output as "HöS/HS" (rare, TSO only)

SKIP any upstream TSO entries if extracting for a DNO (not TSO).

NOTE: In PDF tables, voltage level names may be split across multiple lines.
The document may have ONE combined table OR SEPARATE tables per voltage level.
Season columns may appear in any order (Frühling, Sommer, Herbst, Winter).
Time columns may use "von/bis" format or direct time ranges.

For EACH voltage level found, extract:
- winter: Time window(s) for Dec-Feb
- fruehling: Time window(s) for Mar-May
- sommer: Time window(s) for Jun-Aug
- herbst: Time window(s) for Sep-Nov

Values for each season:
- Time window format: "HH:MM-HH:MM" (e.g., "07:30-15:30")
- Multiple windows: Separate with "\\n" (e.g., "07:30-13:00\\n17:00-19:30")
- No peak load times: Use "-" if explicitly marked as "entfällt" or no times for that season
- Note: It is NORMAL for Spring (Frühling) and Summer (Sommer) to have no peak times (use "-")

Return the structure:
{{
  "success": true,
  "data_type": "hlzf",
  "source_page": <page number where table was found>,
  "notes": "<observations about the table format and which voltage levels were found>",
  "voltage_levels_found": <number of voltage levels>,
  "data": [
    {{"voltage_level": "HS", "winter": "07:30-15:30\\n17:15-19:15", "fruehling": "-", "sommer": "-", "herbst": "11:15-14:00"}},
    {{"voltage_level": "HS/MS", "winter": "07:30-15:45\\n16:30-18:15", "fruehling": "-", "sommer": "-", "herbst": "16:45-17:30"}},
    ...
  ]
}}
"""


def build_extraction_prompt(dno_name: str, year: int, data_type: str) -> str:
    """
    Build the appropriate extraction prompt based on data type.
    
    Args:
        dno_name: Name of the DNO
        year: Year of the data
        data_type: Either "netzentgelte" or "hlzf"
        
    Returns:
        Formatted prompt string for AI extraction
    """
    if data_type == "netzentgelte":
        return build_netzentgelte_prompt(dno_name, year)
    else:  # hlzf
        return build_hlzf_prompt(dno_name, year)
