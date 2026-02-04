#!/usr/bin/env python
"""
Debug script for Netze BW HLZF extraction issue.

Investigates why only 8 out of 10 expected HLZF records are extracted.
Expected: 5 voltage levels x 2 years = 10 records
Actual: 8 records (missing "Umspannung zur Mittelspannung" for both years)

Usage:
    cd /home/kyle/CodingProjects/dno-crawler/backend
    python -m tests.manual.debug_netze_bw_hlzf
"""

import asyncio
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Load .env file BEFORE importing app modules
from dotenv import load_dotenv

env_file = Path(__file__).parent.parent.parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"✅ Loaded .env from: {env_file}")
else:
    print(f"⚠️  No .env file found at: {env_file}")


def build_hlzf_prompt(dno_name: str, year: int) -> str:
    """Same prompt used in step_04_extract.py"""
    return f"""Extract HLZF (Hochlastzeitfenster) data from this German electricity grid document.

DNO: {dno_name}
Year: {year}

IMPORTANT: This table typically has 5 voltage levels (Entnahmeebene/Spannungsebene). Extract ALL of them:
1. Hochspannungsnetz / Hochspannung → use "HS"
2. Umspannung zur Mittelspannung / Umspannung Hoch-/Mittelspannung / HS/MS → use "HS/MS"
3. Mittelspannungsnetz / Mittelspannung → use "MS"
4. Mittelspannungsnetz / Mittelspannung → use "MS"
5. Niederspannungsnetz / Niederspannung → use "NS"

TABLE STRUCTURE: The columns are ordered left-to-right as:
- Column 1 (Winter): months like "Jan., Feb., Dez." or "Januar, Februar, Dezember"
- Column 2 (Frühling): months like "Mrz. – Mai" or "März bis Mai"
- Column 3 (Sommer): months like "Jun. – Aug." or "Juni bis August"
- Column 4 (Herbst): months like "Sept. – Nov." or "September bis November"

For each voltage level, extract the time windows:
- winter: First seasonal column (leftmost) - Time window(s) or null if "entfällt"
- fruehling: Second seasonal column - Time window(s) or null if "entfällt"
- sommer: Third seasonal column - Time window(s) or null if "entfällt"
- herbst: Fourth seasonal column (rightmost) - Time window(s) or null if "entfällt"

Time format: "HH:MM-HH:MM" (e.g., "07:30-15:30"). Multiple windows separated by newlines.

Return valid JSON with exactly 5 voltage level records:
{{
  "success": true,
  "data_type": "hlzf",
  "source_page": <page number>,
  "notes": "<any observations>",
  "data": [
    {{"voltage_level": "HS", "winter": "07:30-15:30\\n17:15-19:15", "fruehling": null, "sommer": null, "herbst": "11:15-14:00"}},
    {{"voltage_level": "HS/MS", "winter": "...", "fruehling": "...", "sommer": "...", "herbst": "..."}},
    {{"voltage_level": "MS", "winter": "...", "fruehling": "...", "sommer": "...", "herbst": "..."}},
    {{"voltage_level": "MS/NS", "winter": "...", "fruehling": "...", "sommer": "...", "herbst": "..."}},
    {{"voltage_level": "NS", "winter": "...", "fruehling": "...", "sommer": "...", "herbst": "..."}}
  ]
}}
"""


async def extract_pdf(file_path: Path, dno_name: str, year: int):
    """Extract HLZF data from a PDF file."""
    from app.services.extraction.ai_extractor import get_ai_extractor

    print(f"\n📄 Processing: {file_path.name}")
    print(f"   DNO: {dno_name}, Year: {year}")

    if not file_path.exists():
        print("   ❌ File not found!")
        return None

    print(f"   Size: {file_path.stat().st_size:,} bytes")

    # Check PDF content with PyMuPDF
    try:
        import fitz
        doc = fitz.open(file_path)
        print(f"   Pages: {len(doc)}")

        # Extract text from all pages to see what the AI sees
        for page_num, page in enumerate(doc):
            text = page.get_text()
            print(f"\n   --- Page {page_num + 1} Text Preview (first 1500 chars) ---")
            print(text[:1500])
            print("   --- End Preview ---")
        doc.close()
    except Exception as e:
        print(f"   ⚠️  Could not read PDF with PyMuPDF: {e}")

    # Build prompt
    prompt = build_hlzf_prompt(dno_name, year)

    print("\n🚀 Starting AI extraction...")

    try:
        extractor = get_ai_extractor()
        if extractor is None:
            print("   ❌ AI not configured")
            return None

        result = await extractor.extract(file_path, prompt)

        print("\n✅ Extraction Result:")
        print(f"   Success: {result.get('success')}")
        print(f"   Notes: {result.get('notes', 'N/A')}")
        print(f"   Records: {len(result.get('data', []))}")

        data = result.get("data", [])
        voltage_levels_found = [r.get("voltage_level") for r in data]
        print(f"   Voltage levels: {voltage_levels_found}")

        # Print detailed records
        for i, record in enumerate(data, 1):
            print(f"\n   [{i}] {record.get('voltage_level', 'Unknown')}")
            print(f"       Winter:    {record.get('winter', '-')}")
            print(f"       Frühjahr:  {record.get('fruehling', '-')}")
            print(f"       Sommer:    {record.get('sommer', '-')}")
            print(f"       Herbst:    {record.get('herbst', '-')}")

        # Check for missing voltage levels
        expected = {"HS", "HS/MS", "MS", "MS/NS", "NS"}
        found = set(voltage_levels_found)
        missing = expected - found
        if missing:
            print(f"\n   ⚠️  MISSING voltage levels: {missing}")

        return result

    except Exception as e:
        print(f"\n❌ Extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    from app.core.config import settings

    print("\n" + "=" * 70)
    print("NETZE BW HLZF EXTRACTION DEBUG")
    print("=" * 70)

    print("\n📋 Configuration:")
    print(f"   AI_API_URL: {settings.ai_api_url}")
    print(f"   AI_MODEL:   {settings.ai_model}")
    print(f"   AI_ENABLED: {settings.ai_enabled}")

    if not settings.ai_enabled:
        print("\n❌ AI is not enabled. Set AI_API_URL and AI_MODEL in .env")
        return

    base_path = Path("/home/kyle/CodingProjects/dno-crawler/data/downloads/netze-bw-gmbh")
    dno_name = "Netze BW GmbH"

    # Test both years
    files = [
        (base_path / "netze-bw-gmbh-hlzf-2024.pdf", 2024),
        (base_path / "netze-bw-gmbh-hlzf-2025.pdf", 2025),
    ]

    all_results = []
    for file_path, year in files:
        result = await extract_pdf(file_path, dno_name, year)
        if result:
            all_results.append((year, result))

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    total_records = sum(len(r.get("data", [])) for _, r in all_results)
    print(f"\nTotal records extracted: {total_records} (expected: 10)")

    for year, result in all_results:
        data = result.get("data", [])
        voltage_levels = [r.get("voltage_level") for r in data]
        print(f"\n{year}: {len(data)} records - {voltage_levels}")

        expected = {"HS", "HS/MS", "MS", "MS/NS", "NS"}
        found = set(voltage_levels)
        missing = expected - found
        if missing:
            print(f"   ⚠️  Missing: {missing}")

    print("\n" + "=" * 70)
    print("DEBUG COMPLETE")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
