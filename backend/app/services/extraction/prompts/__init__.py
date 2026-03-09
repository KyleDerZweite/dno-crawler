"""
AI Extraction Prompts

Centralized prompt templates for AI-based data extraction.
These prompts are used by the extraction step to guide AI models
in extracting structured data from PDF/HTML documents.
"""

import re


def _sanitize_prompt_value(value: str, max_len: int = 120) -> str:
    """Sanitize untrusted values before inserting into prompts."""
    cleaned = re.sub(r"[\r\n\t]+", " ", str(value or "")).strip()
    cleaned = re.sub(r"[{}<>`]+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        return "Unknown DNO"
    return cleaned[:max_len]


def build_netzentgelte_prompt(dno_name: str, year: int) -> str:
    """Build the AI extraction prompt for Netzentgelte data."""
    safe_dno_name = _sanitize_prompt_value(dno_name)

    return f"""Extract Netzentgelte (network tariffs) data from this document.

DNO: {safe_dno_name}
Year: {year}

IMPORTANT: Extract ALL voltage levels present in the document - the number varies by DNO:
- Large DNOs typically have 5 levels: HS, HS/MS, MS, MS/NS, NS
- Small municipal utilities often only have 3 levels: MS, MS/NS, NS (no high voltage infrastructure)
- TSOs may have HöS (Höchstspannung) instead of NS

Map these voltage level names to standardized abbreviations:
- Hochspannung / Hochspannungsnetz / "inHS" / "HS" / "110 kV" → output as "HS"
- Umspannung Hoch-/Mittelspannung / "ausHS" / "HS/MS" / "110/20 kV" / "110/10 kV" → output as "HS/MS"
- Mittelspannung / Mittelspannungsnetz / "inMS" / "MS" / "MSP" / "20 kV" / "10 kV" → output as "MS"
- Umspannung Mittel-/Niederspannung / "ausMS" / "MS/NS" / "MSP/NSP" / "20/0,4 kV" / "10/0,4 kV" → output as "MS/NS"
- Niederspannung / Niederspannungsnetz / "inNS" / "NS" / "NSP" / "0,4 kV" → output as "NS"
- Höchstspannung / "HöS" / "220 kV" / "380 kV" → output as "HöS" (rare, TSO only)
- Umspannung Höchst-/Hochspannung / "ausHöS" / "HöS/HS" → output as "HöS/HS" (rare, TSO only)

NOTE: Some DNOs label voltage levels using kV values instead of names (e.g. "Umspannung 20/0,4kV" = MS/NS).
Standard German grid voltages: NS=0,4kV, MS=10/20kV, HS=110kV, HöS=220/380kV.

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

IMPORTANT formatting rules:
- Use decimal POINT for numbers (e.g., "26.88" NOT "26,88")
- Use "-" for any of these markers:
  - "k.A." or "keine Angabe" (no information)
  - "entfällt" (not applicable)
  - "n/a", empty cells, or missing data
- Do NOT use null - always use "-" for missing values

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
    safe_dno_name = _sanitize_prompt_value(dno_name)

    return f"""Extract HLZF (Hochlastzeitfenster) data from this German electricity grid document.

DNO: {safe_dno_name}
Year: {year}

IMPORTANT: Extract ALL voltage levels present in the document - the number varies by DNO:
- Note: "Umspannung MSP/NSP" maps to "MS/NS".
- Large DNOs typically have 5 levels: HS, HS/MS, MS, MS/NS, NS
- Small municipal utilities often only have 3 levels: MS, MS/NS, NS (no high voltage infrastructure)
- TSOs may have HöS (Höchstspannung) instead of NS

Map these voltage level names to standardized abbreviations:
- Hochspannung / Hochspannungsnetz / "inHS" / "HS" / "110 kV" → output as "HS"
- Umspannung Hoch-/Mittelspannung / "ausHS" / "HS/MS" / "110/20 kV" / "110/10 kV" → output as "HS/MS"
- Mittelspannung / Mittelspannungsnetz / "inMS" / "MS" / "MSP" / "20 kV" / "10 kV" → output as "MS"
- Umspannung Mittel-/Niederspannung / "ausMS" / "MS/NS" / "MSP/NSP" / "20/0,4 kV" / "10/0,4 kV" → output as "MS/NS"
- Niederspannung / Niederspannungsnetz / "inNS" / "NS" / "NSP" / "0,4 kV" → output as "NS"
- Höchstspannung / "HöS" / "220 kV" / "380 kV" → output as "HöS" (rare, TSO only)
- Umspannung Höchst-/Hochspannung / "ausHöS" / "HöS/HS" → output as "HöS/HS" (rare, TSO only)

NOTE: Some DNOs label voltage levels using kV values instead of names (e.g. "Umspannung 20/0,4kV" = MS/NS).
Standard German grid voltages: NS=0,4kV, MS=10/20kV, HS=110kV, HöS=220/380kV.

SKIP any upstream TSO entries if extracting for a DNO (not TSO).

CRITICAL: Output exactly ONE row per voltage level. If the document has separate tables
per voltage level or repeats the same level in different sections, COMBINE all time windows
for the same level into a single row.

NOTE: In PDF tables, voltage level names may be split across multiple lines.
The document may have ONE combined table OR SEPARATE tables per voltage level.
Season columns may appear in any order (Frühling, Sommer, Herbst, Winter).
Time columns may use "von/bis" format or direct time ranges.

For EACH voltage level found, extract:
- winter: Time window(s) for Dec-Feb
- fruehling: Time window(s) for Mar-May
- sommer: Time window(s) for Jun-Aug
- herbst: Time window(s) for Sep-Nov

SEASON VALUE FORMAT — use JSON arrays:
- Each season is a JSON array of time range objects: [{{"start": "HH:MM", "end": "HH:MM"}}]
- Multiple windows: [{{"start": "07:30", "end": "13:00"}}, {{"start": "17:00", "end": "19:30"}}]
- No peak load times: null (for "entfällt", "k.A.", "keine Angabe", empty cells)
- Note: It is NORMAL for Spring (Frühling) and Summer (Sommer) to have no peak times (use null)

Return the structure:
{{
  "success": true,
  "data_type": "hlzf",
  "source_page": <page number where table was found>,
  "notes": "<observations about the table format and which voltage levels were found>",
  "voltage_levels_found": <number of voltage levels>,
  "data": [
    {{"voltage_level": "HS", "winter": [{{"start": "07:30", "end": "15:30"}}, {{"start": "17:15", "end": "19:15"}}], "fruehling": null, "sommer": null, "herbst": [{{"start": "11:15", "end": "14:00"}}]}},
    {{"voltage_level": "HS/MS", "winter": [{{"start": "07:30", "end": "15:45"}}, {{"start": "16:30", "end": "18:15"}}], "fruehling": null, "sommer": null, "herbst": [{{"start": "16:45", "end": "17:30"}}]}},
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
