"""
Test 02: Get DNO from Coordinates

Tests the DNO lookup step of the pipeline:
Lat/Lon Coordinates → VNBDigitalClient → DNO Name

Input: Hardcoded Lat/Lon tuple
Action: Call real VNBDigitalClient.resolve_coordinates_to_dno() API
Goal: Assert valid DNO name is returned
"""

import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.vnb_digital import VNBDigitalClient


# =============================================================================
# HARDCODED TEST INPUTS
# =============================================================================

# Coordinates for Köln area - should resolve to RheinEnergie or similar
TEST_LATITUDE = 50.94834
TEST_LONGITUDE = 6.82052

# =============================================================================
# TEST FUNCTION
# =============================================================================

def test_get_dno():
    """
    Test that VNBDigitalClient correctly resolves coordinates to a DNO name.
    
    Uses REAL API call to vnbdigital.de GraphQL endpoint.
    """
    print(f"\n{'='*60}")
    print("TEST 02: Get DNO from Coordinates")
    print(f"{'='*60}")
    print(f"Input Latitude:  {TEST_LATITUDE}")
    print(f"Input Longitude: {TEST_LONGITUDE}")
    print("-" * 60)
    
    # Initialize client
    client = VNBDigitalClient(request_delay=1.0)
    
    # Call real API
    dno_name = client.resolve_coordinates_to_dno(
        latitude=TEST_LATITUDE,
        longitude=TEST_LONGITUDE,
        prefer_electricity=True
    )
    
    # Validate result
    if dno_name is None:
        print("[FAIL] resolve_coordinates_to_dno() returned None")
        print("  - API may be unreachable or no DNO found for coordinates")
        return False
    
    if not isinstance(dno_name, str):
        print(f"[FAIL] Expected string, got {type(dno_name)}")
        print(f"  - Actual value: {dno_name}")
        return False
    
    if len(dno_name) < 2:
        print(f"[FAIL] DNO name too short: '{dno_name}'")
        return False
    
    print("[PASS] Successfully retrieved DNO name")
    print(f"  - DNO Name: {dno_name}")
    
    # Additional info: also test lookup_by_coordinates for more details
    print("-" * 60)
    print("Additional Details (all VNBs at this location):")
    
    coords = f"{TEST_LATITUDE},{TEST_LONGITUDE}"
    vnbs = client.lookup_by_coordinates(coords)
    
    for i, vnb in enumerate(vnbs, 1):
        print(f"  {i}. {vnb.name}")
        print(f"     - Types: {vnb.types}")
        print(f"     - Voltage Types: {vnb.voltage_types}")
        print(f"     - Is Electricity: {vnb.is_electricity}")
    
    return True


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    try:
        success = test_get_dno()
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
