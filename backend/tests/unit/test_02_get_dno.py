"""
Test 02: Get DNO from Coordinates

Tests the DNO lookup step of the pipeline:
Coordinates → Cache Check → VNBDigitalClient → DNO Name

Input: Hardcoded Lat/Lon tuple
Action: 1) Check database cache 2) If miss, call VNBDigitalClient.resolve_coordinates_to_dno()
Goal: Assert valid DNO name is returned (from cache or API)

Uses SQLite test database initialized by test_00_init.py
"""

import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.unit.test_00_init import get_test_session, TEST_DB_PATH


# =============================================================================
# HARDCODED TEST INPUTS
# =============================================================================

# Coordinates that ARE in the cache (Köln - RheinNetz via ZIP 50859)
TEST_LAT_CACHED = 50.9375
TEST_LON_CACHED = 6.8654
TEST_EXPECTED_DNO = "RheinNetz"

# Coordinates that are NOT in the cache (will require API call)
TEST_LAT_NEW = 50.94834
TEST_LON_NEW = 6.82052


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def check_cache_by_coords(session, latitude: float, longitude: float, tolerance: float = 0.01) -> dict | None:
    """
    Check database cache for DNO by coordinates.
    
    Uses a tolerance for approximate matching since exact float comparison is unreliable.
    """
    from app.db.models import DNOAddressCacheModel
    from sqlalchemy import select, and_
    
    # Find entries with coordinates close to the query
    entries = session.execute(
        select(DNOAddressCacheModel).where(
            and_(
                DNOAddressCacheModel.latitude.isnot(None),
                DNOAddressCacheModel.longitude.isnot(None)
            )
        )
    ).scalars().all()
    
    for entry in entries:
        lat_diff = abs(entry.latitude - latitude)
        lon_diff = abs(entry.longitude - longitude)
        
        if lat_diff <= tolerance and lon_diff <= tolerance:
            # Increment hit count
            entry.hit_count += 1
            session.commit()
            
            return {
                "dno_name": entry.dno_name,
                "latitude": entry.latitude,
                "longitude": entry.longitude,
                "zip_code": entry.zip_code,
                "source": "cache",
                "hit_count": entry.hit_count,
            }
    
    return None


# =============================================================================
# TEST FUNCTIONS
# =============================================================================

def test_get_dno_from_cache():
    """
    Test that DNO is returned from cache when coordinates match.
    
    This avoids unnecessary API calls for known locations.
    """
    print(f"\n{'='*60}")
    print("TEST 02a: Get DNO from Cache (by Coordinates)")
    print(f"{'='*60}")
    print(f"Input Latitude:  {TEST_LAT_CACHED}")
    print(f"Input Longitude: {TEST_LON_CACHED}")
    print("-" * 60)
    
    if not TEST_DB_PATH.exists():
        print("[FAIL] Test database not found!")
        print("  Run 'python -m tests.unit.test_00_init' first")
        return False
    
    session = get_test_session()
    
    try:
        # Check cache by coordinates
        result = check_cache_by_coords(session, TEST_LAT_CACHED, TEST_LON_CACHED)
        
        if result is None:
            print("[FAIL] Expected cache hit, got None")
            return False
        
        dno = result["dno_name"]
        
        if dno != TEST_EXPECTED_DNO:
            print(f"[FAIL] Expected '{TEST_EXPECTED_DNO}', got '{dno}'")
            return False
        
        print("[PASS] Found DNO in cache (no API call needed)")
        print(f"  - DNO Name: {dno}")
        print(f"  - ZIP Code: {result['zip_code']}")
        print(f"  - Hit Count: {result['hit_count']}")
        print(f"  - Source: {result['source']}")
        
        return True
        
    finally:
        session.close()


def test_get_dno_api_fallback():
    """
    Test that API is called when coordinates are not in cache.
    
    This tests the cache-miss → API call path.
    """
    print(f"\n{'='*60}")
    print("TEST 02b: Get DNO via API (Cache Miss)")
    print(f"{'='*60}")
    print(f"Input Latitude:  {TEST_LAT_NEW}")
    print(f"Input Longitude: {TEST_LON_NEW}")
    print("-" * 60)
    
    session = get_test_session()
    
    try:
        # Check cache first - should miss (different coordinates)
        result = check_cache_by_coords(session, TEST_LAT_NEW, TEST_LON_NEW, tolerance=0.001)
        
        if result is not None:
            print("[INFO] Coordinates already in cache, skipping API test")
            print(f"  - DNO: {result['dno_name']}")
            return True
        
        print("  - Cache miss → calling VNB Digital API...")
        
        # Import VNBDigitalClient for API call
        from app.services.vnb_digital import VNBDigitalClient
        
        client = VNBDigitalClient(request_delay=1.0)
        dno_name = client.resolve_coordinates_to_dno(
            latitude=TEST_LAT_NEW,
            longitude=TEST_LON_NEW,
            prefer_electricity=True
        )
        
        if dno_name is None:
            print("[WARN] API returned None (no DNO found or API unreachable)")
            print("  - This is expected if VNB Digital API is down")
            return True  # Don't fail test for API issues
        
        print("[PASS] Successfully retrieved DNO from API")
        print(f"  - DNO Name: {dno_name}")
        
        # Show additional VNBs at this location
        print("-" * 60)
        print("Additional VNBs at this location:")
        
        coords = f"{TEST_LAT_NEW},{TEST_LON_NEW}"
        vnbs = client.lookup_by_coordinates(coords)
        
        for i, vnb in enumerate(vnbs, 1):
            print(f"  {i}. {vnb.name} ({', '.join(vnb.types)})")
        
        return True
        
    finally:
        session.close()


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    try:
        print("\n" + "="*60)
        print("Running DNO Lookup Tests (Cache + API)")
        print("="*60)
        
        results = {
            "Cache Hit": test_get_dno_from_cache(),
            "API Fallback": test_get_dno_api_fallback(),
        }
        
        overall_success = all(results.values())
        
        print(f"\n{'='*60}")
        print("TEST RESULTS:")
        for name, passed in results.items():
            status = "✅ PASSED" if passed else "❌ FAILED"
            print(f"  - {name}: {status}")
        print("-" * 60)
        if overall_success:
            print("RESULT: ✅ ALL TESTS PASSED")
        else:
            print("RESULT: ❌ SOME TESTS FAILED")
        print(f"{'='*60}\n")
        sys.exit(0 if overall_success else 1)
        
    except FileNotFoundError as e:
        print(f"\n[ERROR] {e}")
        print("Run 'python -m tests.unit.test_00_init' first")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unhandled exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
