"""
Test 07: Extract Data (The Extractors)

Tests the data extraction step of the pipeline:
Raw HTML/PDF → Extractors → Structured Data

Input: Hardcoded sample HTML snippet
Action: Run actual extract_hlzf_from_html() extractor
Goal: Verify specific data points are parsed correctly
Mock: None - tests real extraction logic
"""

import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# =============================================================================
# HARDCODED TEST INPUTS
# =============================================================================

# Sample HTML from a real HLZF table (RheinNetz style)
SAMPLE_HLZF_HTML = """
<!DOCTYPE html>
<html>
<head><title>Hochlastzeitfenster</title></head>
<body>
<h3>Stand 01.01.2024 gültig ab 01.01.2024</h3>
<div class="table-wrapper">
    <table>
        <thead>
            <tr>
                <th>Spannungsebene</th>
                <th>Frühling<br/>(01.03. - 31.05.)</th>
                <th>Sommer<br/>(01.06. - 31.08.)</th>
                <th>Herbst<br/>(01.09. - 30.11.)</th>
                <th>Winter<br/>(01.12. - 28./29.02.)</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>Niederspannung (NS)</td>
                <td>07:00 Uhr - 12:00 Uhr<br/>17:00 Uhr - 20:00 Uhr</td>
                <td>10:00 Uhr - 14:00 Uhr</td>
                <td>07:00 Uhr - 12:00 Uhr<br/>17:00 Uhr - 20:00 Uhr</td>
                <td>07:00 Uhr - 12:00 Uhr<br/>17:00 Uhr - 20:00 Uhr</td>
            </tr>
            <tr>
                <td>Mittelspannung (MS)</td>
                <td>08:00 Uhr - 13:00 Uhr<br/>17:00 Uhr - 21:00 Uhr</td>
                <td>11:00 Uhr - 15:00 Uhr</td>
                <td>08:00 Uhr - 13:00 Uhr<br/>17:00 Uhr - 21:00 Uhr</td>
                <td>08:00 Uhr - 13:00 Uhr<br/>17:00 Uhr - 21:00 Uhr</td>
            </tr>
            <tr>
                <td>Hochspannung (HS)</td>
                <td>09:00 Uhr - 14:00 Uhr</td>
                <td>12:00 Uhr - 16:00 Uhr</td>
                <td>09:00 Uhr - 14:00 Uhr</td>
                <td>09:00 Uhr - 14:00 Uhr<br/>18:00 Uhr - 22:00 Uhr</td>
            </tr>
        </tbody>
    </table>
</div>
</body>
</html>
"""

# Expected extracted data
EXPECTED_VOLTAGE_LEVELS = ["Niederspannung (NS)", "Mittelspannung (MS)", "Hochspannung (HS)"]
EXPECTED_RECORD_COUNT = 3


# =============================================================================
# TEST FUNCTIONS
# =============================================================================

def test_extract_hlzf_from_html():
    """
    Test extract_hlzf_from_html() with hardcoded sample HTML.
    
    Uses REAL extraction logic on sample HTML.
    """
    print(f"\n{'='*60}")
    print("TEST 07: Extract Data (HTML Extractor)")
    print(f"{'='*60}")
    print(f"Input: Sample HLZF HTML table ({len(SAMPLE_HLZF_HTML)} bytes)")
    print("-" * 60)
    
    all_passed = True
    
    from app.services.extraction.html_extractor import extract_hlzf_from_html
    
    # Test 1: Basic extraction
    print("\n[Test 7a] Extract HLZF records from HTML")
    
    records = extract_hlzf_from_html(SAMPLE_HLZF_HTML, year=2024)
    
    if records is None or len(records) == 0:
        print("  [FAIL] No records extracted")
        all_passed = False
    else:
        print(f"  [PASS] Extracted {len(records)} records")
        
        if len(records) == EXPECTED_RECORD_COUNT:
            print(f"  [PASS] Record count matches expected ({EXPECTED_RECORD_COUNT})")
        else:
            print(f"  [WARN] Expected {EXPECTED_RECORD_COUNT} records, got {len(records)}")
    
    # Test 2: Verify voltage levels
    print("\n[Test 7b] Verify voltage level extraction")
    
    extracted_levels = [r.get("voltage_level", "") for r in records]
    
    for expected_level in EXPECTED_VOLTAGE_LEVELS:
        # Check if expected level is present (may have slight formatting differences)
        found = any(expected_level in level for level in extracted_levels)
        if found:
            print(f"  ✅ Found: {expected_level}")
        else:
            print(f"  ❌ Missing: {expected_level}")
            all_passed = False
    
    # Test 3: Verify seasonal data extraction
    print("\n[Test 7c] Verify seasonal data")
    
    if records:
        ns_record = records[0]  # Niederspannung
        
        has_fruehling = "fruehling" in ns_record and ns_record["fruehling"]
        has_sommer = "sommer" in ns_record and ns_record["sommer"]
        has_herbst = "herbst" in ns_record and ns_record["herbst"]
        has_winter = "winter" in ns_record and ns_record["winter"]
        
        print(f"  - Frühling: {'✅' if has_fruehling else '❌'} {ns_record.get('fruehling', 'N/A')}")
        print(f"  - Sommer:   {'✅' if has_sommer else '❌'} {ns_record.get('sommer', 'N/A')}")
        print(f"  - Herbst:   {'✅' if has_herbst else '❌'} {ns_record.get('herbst', 'N/A')}")
        print(f"  - Winter:   {'✅' if has_winter else '❌'} {ns_record.get('winter', 'N/A')}")
        
        if not all([has_fruehling, has_sommer, has_herbst, has_winter]):
            print("  [WARN] Some seasonal fields missing")
    
    # Test 4: Display all extracted records
    print("\n[Test 7d] All Extracted Records")
    
    for i, record in enumerate(records, 1):
        print(f"\n  Record {i}:")
        print(f"    Voltage Level: {record.get('voltage_level', 'N/A')}")
        print(f"    Frühling:      {record.get('fruehling', 'N/A')}")
        print(f"    Sommer:        {record.get('sommer', 'N/A')}")
        print(f"    Herbst:        {record.get('herbst', 'N/A')}")
        print(f"    Winter:        {record.get('winter', 'N/A')}")
    
    return all_passed


def test_extract_empty_html():
    """
    Test extraction handles empty/invalid HTML gracefully.
    """
    print(f"\n{'='*60}")
    print("TEST 07b: Edge Cases (Empty/Invalid HTML)")
    print(f"{'='*60}")
    
    all_passed = True
    
    from app.services.extraction.html_extractor import extract_hlzf_from_html
    
    # Test with empty HTML
    print("\n[Test] Empty HTML")
    records = extract_hlzf_from_html("", year=2024)
    
    if records == []:
        print("  [PASS] Returns empty list for empty HTML")
    else:
        print(f"  [FAIL] Expected [], got {records}")
        all_passed = False
    
    # Test with no table
    print("\n[Test] HTML without table")
    records = extract_hlzf_from_html("<html><body><p>No table here</p></body></html>", year=2024)
    
    if records == []:
        print("  [PASS] Returns empty list for HTML without table")
    else:
        print(f"  [FAIL] Expected [], got {records}")
        all_passed = False
    
    return all_passed


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    try:
        print("\n" + "="*60)
        print("Running Data Extraction Tests")
        print("="*60)
        
        success1 = test_extract_hlzf_from_html()
        success2 = test_extract_empty_html()
        
        overall_success = success1 and success2
        
        print(f"\n{'='*60}")
        print("TEST RESULTS:")
        print(f"  - HLZF Extraction:  {'✅ PASSED' if success1 else '❌ FAILED'}")
        print(f"  - Edge Cases:       {'✅ PASSED' if success2 else '❌ FAILED'}")
        print("-" * 60)
        if overall_success:
            print("RESULT: ✅ ALL TESTS PASSED")
        else:
            print("RESULT: ❌ SOME TESTS FAILED")
        print(f"{'='*60}\n")
        sys.exit(0 if overall_success else 1)
    except Exception as e:
        print(f"\n[ERROR] Unhandled exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
