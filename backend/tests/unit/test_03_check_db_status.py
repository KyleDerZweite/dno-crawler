"""
Test 03: Check Database Status

Tests the database cache lookup step of the pipeline:
DNO Name → DNOResolver.check_address_mapping() → Cache Hit/Miss

Input: Hardcoded DNO name
Action: Query the database (MOCKED to return None)
Goal: Verify that mocked DB returns None/False ("No Match" logic)
Mock: Database session mocked to always return None
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# =============================================================================
# HARDCODED TEST INPUTS
# =============================================================================

TEST_DNO_NAME = "RheinNetz"
TEST_ZIP_CODE = "50859"
TEST_STREET_NORMALIZED = "anderronne"


# =============================================================================
# TEST FUNCTION
# =============================================================================

def test_check_db_status_no_match():
    """
    Test that DNOResolver correctly handles "No Match" case.
    
    Uses MOCKED database session that returns None (forcing the
    "No Match" / "Search Required" path in the pipeline).
    """
    print(f"\n{'='*60}")
    print("TEST 03: Check Database Status (Mocked - No Match)")
    print(f"{'='*60}")
    print(f"Input DNO Name:      {TEST_DNO_NAME}")
    print(f"Input ZIP Code:      {TEST_ZIP_CODE}")
    print(f"Input Street (norm): {TEST_STREET_NORMALIZED}")
    print("-" * 60)
    
    # Create mock database session
    mock_db = MagicMock()
    
    # Configure mock to return None (no cache hit)
    mock_db.execute.return_value.scalar_one_or_none.return_value = None
    
    # Import and create resolver with mocked DB
    from app.services.dno_resolver import DNOResolver
    resolver = DNOResolver(db_session=mock_db)
    
    # Call the check_address_mapping method
    result = resolver.check_address_mapping(TEST_ZIP_CODE, TEST_STREET_NORMALIZED)
    
    # Validate result
    if result is not None:
        print(f"[FAIL] Expected None, got: {result}")
        print("  - Mock may not be configured correctly")
        return False
    
    print("[PASS] Database returned None (No Match)")
    print("  - This triggers the 'Search' path in the pipeline")
    
    # Verify mock was called correctly
    mock_db.execute.assert_called_once()
    print("-" * 60)
    print("Mock Verification:")
    print("  - db.execute() was called: ✅")
    
    # Additional test: Verify normalize_street function
    print("-" * 60)
    print("Testing normalize_street():")
    
    test_cases = [
        ("Musterstraße 5", "musterstr5"),
        ("Berliner Strasse 10", "berlinerstr10"),
        ("An der Ronne 160", "anderronne160"),
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


def test_check_db_status_cache_hit():
    """
    Test that DNOResolver correctly handles cache hit case.
    
    Uses MOCKED database session that returns a cached entry.
    """
    print(f"\n{'='*60}")
    print("TEST 03b: Check Database Status (Mocked - Cache Hit)")
    print(f"{'='*60}")
    
    # Create mock database session
    mock_db = MagicMock()
    
    # Create a mock cache entry
    mock_entry = MagicMock()
    mock_entry.dno_name = TEST_DNO_NAME
    mock_entry.hit_count = 5
    
    # Configure mock to return the cache entry
    mock_db.execute.return_value.scalar_one_or_none.return_value = mock_entry
    
    # Import and create resolver with mocked DB
    from app.services.dno_resolver import DNOResolver
    resolver = DNOResolver(db_session=mock_db)
    
    # Call the check_address_mapping method
    result = resolver.check_address_mapping(TEST_ZIP_CODE, TEST_STREET_NORMALIZED)
    
    # Validate result
    if result != TEST_DNO_NAME:
        print(f"[FAIL] Expected '{TEST_DNO_NAME}', got: {result}")
        return False
    
    # Verify hit count was incremented
    if mock_entry.hit_count != 6:
        print(f"[FAIL] Expected hit_count=6, got: {mock_entry.hit_count}")
        return False
    
    print("[PASS] Database returned cached DNO name")
    print(f"  - DNO Name: {result}")
    print(f"  - Hit Count incremented: 5 → {mock_entry.hit_count}")
    
    return True


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    try:
        print("\n" + "="*60)
        print("Running Database Status Tests (All Mocked)")
        print("="*60)
        
        # Test 1: No Match case (primary test per requirements)
        success1 = test_check_db_status_no_match()
        
        # Test 2: Cache Hit case (verification that logic works both ways)
        success2 = test_check_db_status_cache_hit()
        
        overall_success = success1 and success2
        
        print(f"\n{'='*60}")
        print("TEST RESULTS:")
        print(f"  - No Match Test:  {'✅ PASSED' if success1 else '❌ FAILED'}")
        print(f"  - Cache Hit Test: {'✅ PASSED' if success2 else '❌ FAILED'}")
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
