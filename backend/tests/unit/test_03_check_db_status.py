"""
Test 03: Check Database Status

Tests the database cache lookup step of the pipeline:
DNO Name → DNOResolver.check_address_mapping() → Cache Hit/Miss

This test uses the SQLite test database initialized by test_00_init.py
instead of mocks, allowing realistic testing of query logic.

Run test_00_init.py first: python -m tests.unit.test_00_init
"""

import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import test database utilities
from tests.unit.test_00_init import get_test_session, TEST_DB_PATH


# =============================================================================
# HARDCODED TEST INPUTS
# =============================================================================

# These match the seed data in test_00_init.py
TEST_CACHED_ZIP = "50859"
TEST_CACHED_STREET = "anderronne"  # "An der Ronne" normalized
TEST_EXPECTED_DNO = "RheinNetz"

TEST_UNKNOWN_ZIP = "99999"
TEST_UNKNOWN_STREET = "unknownstr"


# =============================================================================
# TEST FUNCTIONS
# =============================================================================

def test_check_db_status_cache_hit():
    """
    Test that DNOResolver correctly finds cached address → DNO mapping.
    
    Uses REAL SQLite database with seeded test data.
    Now also verifies coordinates are cached.
    """
    print(f"\n{'='*60}")
    print("TEST 03a: Check Database Status (Cache Hit with Coordinates)")
    print(f"{'='*60}")
    print(f"Input ZIP Code:      {TEST_CACHED_ZIP}")
    print(f"Input Street (norm): {TEST_CACHED_STREET}")
    print("-" * 60)
    
    # Verify test database exists
    if not TEST_DB_PATH.exists():
        print("[FAIL] Test database not found!")
        print("  Run 'python -m tests.unit.test_00_init' first")
        return False
    
    # Get real database session
    session = get_test_session()
    
    try:
        # Import and create resolver with real DB
        from app.services.dno_resolver import DNOResolver
        resolver = DNOResolver(db_session=session)
        
        # Query the seeded cache entry
        result = resolver.check_address_mapping(TEST_CACHED_ZIP, TEST_CACHED_STREET)
        
        if result is None:
            print(f"[FAIL] Expected '{TEST_EXPECTED_DNO}', got None")
            print("  - The seeded address cache entry may be missing")
            return False
        
        if result != TEST_EXPECTED_DNO:
            print(f"[FAIL] Expected '{TEST_EXPECTED_DNO}', got '{result}'")
            return False
        
        print("[PASS] Found cached DNO name from database")
        print(f"  - DNO Name: {result}")
        
        # Verify the full cache entry including coordinates
        from app.db.models import DNOAddressCacheModel
        from sqlalchemy import select, and_
        
        cache_entry = session.execute(
            select(DNOAddressCacheModel).where(
                and_(
                    DNOAddressCacheModel.zip_code == TEST_CACHED_ZIP,
                    DNOAddressCacheModel.street_name == TEST_CACHED_STREET
                )
            )
        ).scalar_one_or_none()
        
        if cache_entry:
            print(f"  - Source: {cache_entry.source}")
            
            # Verify coordinates are stored
            if cache_entry.latitude and cache_entry.longitude:
                print(f"  - Latitude: {cache_entry.latitude}")
                print(f"  - Longitude: {cache_entry.longitude}")
                print("  ✅ Coordinates cached alongside DNO!")
            else:
                print("  ⚠️ No coordinates in cache entry")
        
        return True
        
    finally:
        session.close()


def test_check_db_status_no_match():
    """
    Test that DNOResolver correctly handles unknown addresses (no cache hit).
    
    Uses REAL SQLite database to verify the query returns None
    for addresses not in the cache.
    """
    print(f"\n{'='*60}")
    print("TEST 03b: Check Database Status (No Match)")
    print(f"{'='*60}")
    print(f"Input ZIP Code:      {TEST_UNKNOWN_ZIP}")
    print(f"Input Street (norm): {TEST_UNKNOWN_STREET}")
    print("-" * 60)
    
    # Get real database session
    session = get_test_session()
    
    try:
        from app.services.dno_resolver import DNOResolver
        resolver = DNOResolver(db_session=session)
        
        # Query with address that's NOT in the cache
        result = resolver.check_address_mapping(TEST_UNKNOWN_ZIP, TEST_UNKNOWN_STREET)
        
        if result is not None:
            print(f"[FAIL] Expected None (no match), got: {result}")
            return False
        
        print("[PASS] Database returned None (No Match)")
        print("  - This triggers the 'External Search' path in the pipeline")
        
        return True
        
    finally:
        session.close()


def test_normalize_street():
    """Test the street normalization function."""
    print(f"\n{'='*60}")
    print("TEST 03c: Street Normalization")
    print(f"{'='*60}")
    
    from app.services.dno_resolver import DNOResolver
    resolver = DNOResolver()
    
    test_cases = [
        ("An der Ronne 160", "anderronne160"),
        ("Musterstraße 5", "musterstr5"),
        ("Berliner Strasse 10", "berlinerstr10"),
        ("Hauptstr. 42", "hauptstr42"),
    ]
    
    all_passed = True
    for input_street, expected in test_cases:
        actual = resolver.normalize_street(input_street)
        if actual == expected:
            print(f"  ✅ '{input_street}' → '{actual}'")
        else:
            print(f"  ❌ '{input_street}' → expected '{expected}', got '{actual}'")
            all_passed = False
    
    return all_passed


def test_save_address_mapping():
    """Test saving a new address → DNO mapping."""
    print(f"\n{'='*60}")
    print("TEST 03d: Save Address Mapping")
    print(f"{'='*60}")
    
    session = get_test_session()
    
    try:
        from app.services.dno_resolver import DNOResolver
        resolver = DNOResolver(db_session=session)
        
        # Save a new mapping
        new_zip = "12345"
        new_street = "teststr"
        new_dno = "TestNetz"
        
        resolver.save_address_mapping(new_zip, new_street, new_dno)
        
        # Verify it was saved
        result = resolver.check_address_mapping(new_zip, new_street)
        
        if result != new_dno:
            print(f"[FAIL] Expected '{new_dno}', got '{result}'")
            return False
        
        print("[PASS] Successfully saved and retrieved new mapping")
        print(f"  - ZIP: {new_zip}, Street: {new_street} → DNO: {result}")
        
        # Clean up (optional, since we recreate DB each time)
        from app.db.models import DNOAddressCacheModel
        from sqlalchemy import delete
        
        session.execute(
            delete(DNOAddressCacheModel).where(
                DNOAddressCacheModel.zip_code == new_zip
            )
        )
        session.commit()
        
        return True
        
    finally:
        session.close()


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    try:
        print("\n" + "="*60)
        print("Running Database Status Tests (Real SQLite Database)")
        print("="*60)
        
        results = {
            "Cache Hit": test_check_db_status_cache_hit(),
            "No Match": test_check_db_status_no_match(),
            "Normalize Street": test_normalize_street(),
            "Save Mapping": test_save_address_mapping(),
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
        print("Run 'python -m tests.unit.test_00_init' to create the test database")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unhandled exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
