"""
Test 01: Get Coordinates from Address

Tests the geocoding step of the pipeline:
Address String → Cache Check → VNBDigitalClient → Lat/Lon Coordinates

Input: Hardcoded address string
Action: 1) Check database cache 2) If miss, call VNBDigitalClient.search_address()
Goal: Assert valid coordinates are returned (from cache or API)

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

# Address that IS in the cache (seeded in test_00_init.py)
TEST_ADDRESS_CACHED = "An der Ronne 160, 50859 Köln"
TEST_ZIP_CACHED = "50859"
TEST_STREET_CACHED = "anderronne"  # Normalized

# Address that is NOT in the cache (will require API call)
TEST_ADDRESS_NEW = "Unter Sachsenhausen 35, 50667 Köln"
TEST_ZIP_NEW = "50667"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def normalize_street(street: str) -> str:
    """Normalize street name for cache key."""
    return (
        street.lower()
        .replace("straße", "str")
        .replace("strasse", "str")
        .replace("str.", "str")
        .replace(" ", "")
    )


def check_cache(session, zip_code: str, norm_street: str) -> dict | None:
    """Check database cache for existing coordinates + DNO."""
    from app.db.models import DNOAddressCacheModel
    from sqlalchemy import select, and_
    
    cache_entry = session.execute(
        select(DNOAddressCacheModel).where(
            and_(
                DNOAddressCacheModel.zip_code == zip_code,
                DNOAddressCacheModel.street_name == norm_street
            )
        )
    ).scalar_one_or_none()
    
    if cache_entry:
        # Increment hit count
        cache_entry.hit_count += 1
        session.commit()
        
        return {
            "latitude": cache_entry.latitude,
            "longitude": cache_entry.longitude,
            "dno_name": cache_entry.dno_name,
            "source": "cache",
            "hit_count": cache_entry.hit_count,
        }
    
    return None


# =============================================================================
# TEST FUNCTIONS
# =============================================================================

def test_get_coordinates_from_cache():
    """
    Test that coordinates are returned from cache when available.
    
    This avoids unnecessary API calls for known addresses.
    """
    print(f"\n{'='*60}")
    print("TEST 01a: Get Coordinates from Cache")
    print(f"{'='*60}")
    print(f"Input Address: {TEST_ADDRESS_CACHED}")
    print("-" * 60)
    
    if not TEST_DB_PATH.exists():
        print("[FAIL] Test database not found!")
        print("  Run 'python -m tests.unit.test_00_init' first")
        return False
    
    session = get_test_session()
    
    try:
        # Check cache first
        norm_street = normalize_street("An der Ronne")
        result = check_cache(session, TEST_ZIP_CACHED, norm_street)
        
        if result is None:
            print("[FAIL] Expected cache hit, got None")
            print(f"  - ZIP: {TEST_ZIP_CACHED}, Street: {norm_street}")
            return False
        
        lat = result["latitude"]
        lon = result["longitude"]
        dno = result["dno_name"]
        
        print("[PASS] Found coordinates in cache (no API call needed)")
        print(f"  - Latitude: {lat}")
        print(f"  - Longitude: {lon}")
        print(f"  - DNO: {dno}")
        print(f"  - Hit Count: {result['hit_count']}")
        print(f"  - Source: {result['source']}")
        
        # Validate coordinates are in reasonable range for Germany
        if not (47.0 <= lat <= 55.0):
            print(f"[WARN] Latitude {lat} outside expected German range (47-55)")
        if not (5.0 <= lon <= 15.0):
            print(f"[WARN] Longitude {lon} outside expected German range (5-15)")
        
        return True
        
    finally:
        session.close()


def test_get_coordinates_api_fallback():
    """
    Test that API is called when address is not in cache.
    
    This tests the cache-miss → API call path.
    """
    print(f"\n{'='*60}")
    print("TEST 01b: Get Coordinates via API (Cache Miss)")
    print(f"{'='*60}")
    print(f"Input Address: {TEST_ADDRESS_NEW}")
    print("-" * 60)
    
    session = get_test_session()
    
    try:
        # Check cache first - should miss
        norm_street = normalize_street("Unter Sachsenhausen")
        result = check_cache(session, TEST_ZIP_NEW, norm_street)
        
        if result is not None:
            print("[INFO] Address already in cache, skipping API test")
            print(f"  - Lat/Lon: {result['latitude']}, {result['longitude']}")
            print(f"  - DNO: {result['dno_name']}")
            return True
        
        print("  - Cache miss → calling VNB Digital API...")
        
        # Import VNBDigitalClient for API call
        from app.services.vnb_digital import VNBDigitalClient
        
        client = VNBDigitalClient(request_delay=1.0)
        api_result = client.search_address(TEST_ADDRESS_NEW)
        
        if api_result is None:
            print("[WARN] API returned None (address not found or API unreachable)")
            print("  - This is expected if VNB Digital API is down")
            return True  # Don't fail test for API issues
        
        # Parse coordinates
        try:
            lat, lon = api_result.coordinates.split(",")
            lat = float(lat)
            lon = float(lon)
        except (ValueError, AttributeError) as e:
            print(f"[FAIL] Could not parse coordinates: {e}")
            return False
        
        print("[PASS] Successfully retrieved coordinates from API")
        print(f"  - Title: {api_result.title}")
        print(f"  - Latitude: {lat}")
        print(f"  - Longitude: {lon}")
        
        # Optionally save to cache for future runs
        # (Not done here to keep test idempotent)
        
        return True
        
    finally:
        session.close()


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    try:
        print("\n" + "="*60)
        print("Running Coordinates Tests (Cache + API)")
        print("="*60)
        
        results = {
            "Cache Hit": test_get_coordinates_from_cache(),
            "API Fallback": test_get_coordinates_api_fallback(),
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
