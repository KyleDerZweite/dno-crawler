"""
Test 01: Get Coordinates from Address

Tests the geocoding step of the pipeline:
Address String → VNBDigitalClient → Lat/Lon Coordinates

Input: Hardcoded address string
Action: Call real VNBDigitalClient.search_address() API
Goal: Assert valid coordinates are returned
"""

import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.vnb_digital import VNBDigitalClient


# =============================================================================
# HARDCODED TEST INPUTS
# =============================================================================

# Note: VNBDigitalClient uses German address format, so we use a German address
# "10 Downing Street, London" won't work with vnbdigital.de (German-only service)
TEST_ADDRESS = "An der Ronne 160, 50859 Köln"


# =============================================================================
# TEST FUNCTION
# =============================================================================

def test_get_coordinates():
    """
    Test that VNBDigitalClient correctly geocodes an address to coordinates.
    
    Uses REAL API call to vnbdigital.de GraphQL endpoint.
    """
    print(f"\n{'='*60}")
    print("TEST 01: Get Coordinates from Address")
    print(f"{'='*60}")
    print(f"Input Address: {TEST_ADDRESS}")
    print("-" * 60)
    
    # Initialize client
    client = VNBDigitalClient(request_delay=1.0)
    
    # Call real API
    result = client.search_address(TEST_ADDRESS)
    
    # Validate result
    if result is None:
        print("[FAIL] search_address() returned None")
        print("  - API may be unreachable or address not found")
        return False
    
    # Check that result has coordinates
    if not hasattr(result, 'coordinates') or not result.coordinates:
        print("[FAIL] Result has no coordinates attribute")
        print(f"  - Actual result: {result}")
        return False
    
    # Parse coordinates (format: "lat,lon")
    try:
        lat, lon = result.coordinates.split(",")
        lat = float(lat)
        lon = float(lon)
    except (ValueError, AttributeError) as e:
        print(f"[FAIL] Could not parse coordinates: {e}")
        print(f"  - Raw coordinates: {result.coordinates}")
        return False
    
    # Validate coordinates are in reasonable range for Germany
    # Germany roughly: Lat 47-55, Lon 5-15
    if not (47.0 <= lat <= 55.0):
        print(f"[WARN] Latitude {lat} outside expected German range (47-55)")
    
    if not (5.0 <= lon <= 15.0):
        print(f"[WARN] Longitude {lon} outside expected German range (5-15)")
    
    print("[PASS] Successfully retrieved coordinates")
    print(f"  - Title: {result.title}")
    print(f"  - Coordinates: {result.coordinates}")
    print(f"  - Lat: {lat}")
    print(f"  - Lon: {lon}")
    
    return True


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    try:
        success = test_get_coordinates()
        print(f"\n{'='*60}")
        if success:
            print("RESULT: ✅ TEST PASSED")
        else:
            print("RESULT: ❌ TEST FAILED")
        print(f"{'='*60}\n")
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] Unhandled exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
