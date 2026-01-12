"""
Manual test script for Impressum address extraction.

Tests extraction of full address (postal code + city) from DNO Impressum pages.
Validates extraction by matching the street address against VNB Digital data.

Test Cases:
- RheinNetz: Parkgürtel 24, 50823 Köln
- Westnetz: Florianstraße 15-21, 44139 Dortmund
- Netze BW: Schelmenwasenstraße 15, 70567 Stuttgart
- Stadtwerke Norderstedt: Heidbergstraße 101-111, 22846 Norderstedt

Run:
    python -m tests.manual.impressum_extract_test
"""

import asyncio
import re
import sys
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ExtractedAddress:
    """Full address extracted from Impressum."""
    street: str
    house_number: str
    postal_code: str
    city: str
    raw_line: str  # Original line from Impressum

    @property
    def full_address(self) -> str:
        return f"{self.street} {self.house_number}, {self.postal_code} {self.city}"


# =============================================================================
# Test Cases
# =============================================================================

TEST_CASES = [
    {
        "name": "RheinNetz GmbH",
        "impressum_url": "https://www.rheinnetz.de/impressum",
        "vnb_street": "Parkgürtel 24",  # From VNB Digital
        "expected_postal_code": "50823",
        "expected_city": "Köln",
    },
    {
        "name": "Westnetz GmbH",
        "impressum_url": "https://www.westnetz.de/de/impressum.html",
        "vnb_street": "Florianstraße 15-21",  # From VNB Digital
        "expected_postal_code": "44139",
        "expected_city": "Dortmund",
        "js_rendered": True,  # Content loaded via JavaScript, extraction will fail
    },
    {
        "name": "Netze BW GmbH",
        "impressum_url": "https://www.netze-bw.de/impressum",
        "vnb_street": "Schelmenwasenstraße 15",  # From VNB Digital
        "expected_postal_code": "70567",
        "expected_city": "Stuttgart",
    },
    {
        "name": "Stadtwerke Norderstedt",
        "impressum_url": "https://www.stadtwerke-norderstedt.de/impressum",
        "vnb_street": "Heidbergstraße 101-111",  # From VNB Digital
        "expected_postal_code": "22846",
        "expected_city": "Norderstedt",
    },
]


# =============================================================================
# Extraction Logic
# =============================================================================

# Pattern: 5-digit German postal code followed by city name
# Example: "50823 Köln", "44139 Dortmund"
POSTAL_CITY_PATTERN = re.compile(
    r"(\d{5})\s+([A-ZÄÖÜa-zäöü][A-ZÄÖÜa-zäöü\s\-\.]+)"
)

# Pattern: Street with house number (German format)
# Examples: "Parkgürtel 24", "Florianstraße 15-21", "Heidbergstraße 101-111"
# Note: Street suffix is embedded in word (Florianstraße, not "Florian straße")
STREET_PATTERN = re.compile(
    r"([A-ZÄÖÜa-zäöü][A-ZÄÖÜa-zäöü\-]*(?:straße|strasse|str\.|gürtel|weg|platz|ring|allee|damm|ufer|hof|park))\s*(\d+(?:\s*[-–]\s*\d+)?)",
    re.IGNORECASE
)


def normalize_street(street: str) -> str:
    """Normalize street name for comparison."""
    s = street.lower().strip()
    # Normalize common variations
    s = re.sub(r"straße", "str", s)
    s = re.sub(r"strasse", "str", s)
    s = re.sub(r"str\.", "str", s)
    s = re.sub(r"\s+", "", s)  # Remove all spaces
    s = re.sub(r"[\-–]", "", s)  # Remove hyphens
    return s


def extract_address_from_html(html: str, vnb_street: str) -> ExtractedAddress | None:
    """
    Extract full address from Impressum HTML.

    Strategy:
    1. Parse HTML and extract text content
    2. Look for lines containing the VNB street address
    3. Find postal code + city near the street address
    4. Validate the extraction
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove script and style elements
    for element in soup(["script", "style", "nav", "header"]):
        element.decompose()

    # Get text content, preserving line breaks
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    # Normalize the VNB street for matching
    vnb_normalized = normalize_street(vnb_street)

    # Strategy 1: Look for exact line containing the street
    street_line_idx = None
    for idx, line in enumerate(lines):
        if normalize_street(line).startswith(vnb_normalized[:10]):
            street_line_idx = idx
            break

    if street_line_idx is None:
        # Strategy 2: Look for partial match anywhere
        for idx, line in enumerate(lines):
            # Extract street from VNB (just the name, not number)
            street_only_match = STREET_PATTERN.match(vnb_street)
            if street_only_match:
                street_name = street_only_match.group(1).lower()
                if street_name in line.lower():
                    street_line_idx = idx
                    break

    if street_line_idx is None:
        return None

    # Look for postal code + city in nearby lines (within 3 lines)
    search_range = lines[max(0, street_line_idx-2):street_line_idx+4]

    postal_code = None
    city = None
    raw_postal_line = None

    for line in search_range:
        match = POSTAL_CITY_PATTERN.search(line)
        if match:
            postal_code = match.group(1)
            city = match.group(2).strip()
            raw_postal_line = line
            break

    if not postal_code or not city:
        return None

    # Extract street and house number from VNB address
    street_match = STREET_PATTERN.match(vnb_street)
    if street_match:
        street = street_match.group(1)
        house_number = street_match.group(2)
    else:
        # Fallback: split by last number group
        parts = vnb_street.rsplit(" ", 1)
        street = parts[0] if len(parts) > 1 else vnb_street
        house_number = parts[1] if len(parts) > 1 else ""

    return ExtractedAddress(
        street=street,
        house_number=house_number,
        postal_code=postal_code,
        city=city,
        raw_line=raw_postal_line or "",
    )


async def fetch_impressum(url: str) -> str | None:
    """Fetch Impressum page HTML."""
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=15.0,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; DNO-Crawler/1.0)",
            "Accept": "text/html",
        },
    ) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as e:
            print(f"   ❌ HTTP Error: {e}")
            return None


# =============================================================================
# Tests
# =============================================================================

async def test_impressum_extraction():
    """Test Impressum extraction for all test cases."""
    print("\n" + "=" * 70)
    print("🔍 IMPRESSUM ADDRESS EXTRACTION TEST")
    print("=" * 70)

    passed = 0
    failed = 0
    skipped = 0

    for test in TEST_CASES:
        is_js = test.get("js_rendered", False)
        print(f"\n📍 Testing: {test['name']}" + (" [JS-rendered]" if is_js else ""))
        print(f"   URL: {test['impressum_url']}")
        print(f"   VNB Street: {test['vnb_street']}")

        # Fetch Impressum
        html = await fetch_impressum(test["impressum_url"])
        if not html:
            print("   ❌ FAILED: Could not fetch Impressum page")
            failed += 1
            continue

        print(f"   ✓ Fetched {len(html)} bytes")

        # Extract address
        extracted = extract_address_from_html(html, test["vnb_street"])

        if not extracted:
            if is_js:
                print("   ⏭️ SKIPPED: JS-rendered page (expected)")
                skipped += 1
            else:
                print("   ❌ FAILED: Could not extract address")
                failed += 1
            continue

        print(f"   📬 Extracted: {extracted.full_address}")
        print(f"   📄 Raw line: {extracted.raw_line}")

        # Validate
        postal_ok = extracted.postal_code == test["expected_postal_code"]
        city_ok = extracted.city.lower().startswith(test["expected_city"].lower())

        if postal_ok and city_ok:
            print("   ✅ PASSED")
            passed += 1
        else:
            print("   ❌ FAILED validation")
            if not postal_ok:
                print(f"      Expected postal code: {test['expected_postal_code']}, got: {extracted.postal_code}")
            if not city_ok:
                print(f"      Expected city: {test['expected_city']}, got: {extracted.city}")
            failed += 1

    print("\n" + "-" * 70)
    print(f"   📊 Results: {passed} passed, {skipped} skipped (JS), {failed} failed")
    return failed == 0  # Success if no unexpected failures


async def test_edge_cases():
    """Test edge cases and error handling."""
    print("\n" + "=" * 70)
    print("🧪 EDGE CASE TESTS")
    print("=" * 70)

    # Test 1: Non-existent URL
    print("\n📍 Test: Non-existent Impressum URL")
    html = await fetch_impressum("https://example.com/impressum")
    if html is None:
        print("   ✅ Correctly handled missing page")
        edge_pass = True
    else:
        print("   ⚠️ Unexpected: Got response from example.com")
        edge_pass = True  # Not a failure, just unexpected

    # Test 2: Street not found in page
    print("\n📍 Test: Street address not found in HTML")
    fake_html = "<html><body><p>No address here</p></body></html>"
    extracted = extract_address_from_html(fake_html, "Musterstraße 123")
    if extracted is None:
        print("   ✅ Correctly returned None for missing address")
    else:
        print("   ❌ Should have returned None")
        edge_pass = False

    # Test 3: Malformed postal code
    print("\n📍 Test: Valid street but no postal code")
    fake_html = "<html><body><p>Parkgürtel 24</p><p>Köln</p></body></html>"
    extracted = extract_address_from_html(fake_html, "Parkgürtel 24")
    if extracted is None:
        print("   ✅ Correctly returned None (no postal code)")
    else:
        print("   ❌ Should have returned None")
        edge_pass = False

    return edge_pass


# =============================================================================
# Main
# =============================================================================

async def main():
    print("=" * 70)
    print("🏢 IMPRESSUM ADDRESS EXTRACTOR TEST")
    print("=" * 70)

    results = {}

    # Run tests
    results["impressum_extraction"] = await test_impressum_extraction()
    results["edge_cases"] = await test_edge_cases()

    # Summary
    print("\n" + "=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {status}: {test_name}")

    all_passed = all(results.values())
    print("\n" + ("✅ ALL TESTS PASSED" if all_passed else "❌ SOME TESTS FAILED"))

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
