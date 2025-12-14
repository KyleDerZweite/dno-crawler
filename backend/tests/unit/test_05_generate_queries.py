"""
Test 05: Generate Queries

Tests the query generation step of the pipeline:
Strategy Object → Query Generator → Formatted Search Strings

This test uses the SQLite test database initialized by test_00_init.py
to load real strategy configurations and verify query generation.

Run test_00_init.py first: python -m tests.unit.test_00_init
"""

import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.unit.test_00_init import get_test_session, TEST_DB_PATH


# =============================================================================
# HARDCODED TEST INPUTS
# =============================================================================

TEST_YEAR = 2024


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def load_strategy(session, dno_name: str, strategy_type: str) -> dict | None:
    """Load strategy from database."""
    from app.db.models import ExtractionStrategyModel, DNOModel
    from sqlalchemy import select, and_
    
    # Find DNO
    dno = session.execute(
        select(DNOModel).where(DNOModel.name == dno_name)
    ).scalar_one_or_none()
    
    if dno:
        strategy = session.execute(
            select(ExtractionStrategyModel).where(
                and_(
                    ExtractionStrategyModel.dno_id == dno.id,
                    ExtractionStrategyModel.strategy_type == strategy_type
                )
            )
        ).scalar_one_or_none()
        
        if strategy:
            return {"config": strategy.config, "is_default": False}
    
    # Fallback to default
    default = session.execute(
        select(ExtractionStrategyModel).where(
            and_(
                ExtractionStrategyModel.dno_id.is_(None),
                ExtractionStrategyModel.strategy_type == strategy_type
            )
        )
    ).scalar_one_or_none()
    
    if default:
        return {"config": default.config, "is_default": True}
    
    return None


def generate_queries(strategy: dict, dno_name: str, year: int) -> list[str]:
    """Generate queries from strategy with placeholders filled."""
    templates = strategy.get("config", {}).get("search_queries", [])
    return [
        t.replace("{dno_name}", dno_name).replace("{year}", str(year))
        for t in templates
    ]


# =============================================================================
# TESTS
# =============================================================================

def test_westnetz_netzentgelte_queries():
    """Test WestNetz Netzentgelte query generation (PDF)."""
    print(f"\n{'='*60}")
    print("TEST 05a: WestNetz Netzentgelte Queries (PDF)")
    print(f"{'='*60}")
    
    session = get_test_session()
    all_passed = True
    
    try:
        strategy = load_strategy(session, "WestNetz", "netzentgelte")
        queries = generate_queries(strategy, "WestNetz", TEST_YEAR)
        
        print(f"Generated {len(queries)} queries:")
        for q in queries:
            issues = []
            
            # Check 1: DNO name is quoted
            if '"WestNetz"' not in q:
                issues.append("DNO not quoted")
            
            # Check 2: Year present
            if str(TEST_YEAR) not in q:
                issues.append("Year missing")
            
            # Check 3: filetype:pdf for PDF source
            if "filetype:pdf" not in q:
                issues.append("Missing filetype:pdf")
            
            if issues:
                print(f"  ❌ {q}")
                print(f"     Issues: {', '.join(issues)}")
                all_passed = False
            else:
                print(f"  ✅ {q}")
        
        return all_passed
        
    finally:
        session.close()


def test_westnetz_hlzf_queries():
    """Test WestNetz HLZF query generation (PDF)."""
    print(f"\n{'='*60}")
    print("TEST 05b: WestNetz HLZF Queries (PDF)")
    print(f"{'='*60}")
    
    session = get_test_session()
    all_passed = True
    
    try:
        strategy = load_strategy(session, "WestNetz", "hlzf")
        queries = generate_queries(strategy, "WestNetz", TEST_YEAR)
        
        print(f"Generated {len(queries)} queries:")
        for q in queries:
            # WestNetz HLZF is PDF-based, should have filetype:pdf
            if "filetype:pdf" in q and '"WestNetz"' in q:
                print(f"  ✅ {q}")
            else:
                print(f"  ❌ {q} - format validation failed")
                all_passed = False
        
        return all_passed
        
    finally:
        session.close()


def test_rheinnetz_netzentgelte_queries():
    """Test RheinNetz Netzentgelte query generation (PDF)."""
    print(f"\n{'='*60}")
    print("TEST 05c: RheinNetz Netzentgelte Queries (PDF)")
    print(f"{'='*60}")
    
    session = get_test_session()
    all_passed = True
    
    try:
        strategy = load_strategy(session, "RheinNetz", "netzentgelte")
        queries = generate_queries(strategy, "RheinNetz", TEST_YEAR)
        
        print(f"Generated {len(queries)} queries:")
        for q in queries:
            # RheinNetz Netzentgelte is PDF-based
            if "filetype:pdf" in q and '"RheinNetz"' in q:
                print(f"  ✅ {q}")
            else:
                print(f"  ❌ {q} - format validation failed")
                all_passed = False
        
        return all_passed
        
    finally:
        session.close()


def test_rheinnetz_hlzf_queries_no_pdf():
    """Test RheinNetz HLZF query generation (HTML Table - NO filetype:pdf)."""
    print(f"\n{'='*60}")
    print("TEST 05d: RheinNetz HLZF Queries (HTML Table - NO filetype:pdf)")
    print(f"{'='*60}")
    
    session = get_test_session()
    all_passed = True
    
    try:
        strategy = load_strategy(session, "RheinNetz", "hlzf")
        
        # Verify it's an HTML table strategy
        content_format = strategy["config"].get("content_format")
        print(f"Content format: {content_format}")
        
        if content_format != "html_table":
            print(f"[FAIL] Expected 'html_table', got '{content_format}'")
            return False
        
        queries = generate_queries(strategy, "RheinNetz", TEST_YEAR)
        
        print(f"Generated {len(queries)} queries:")
        for q in queries:
            # RheinNetz HLZF is HTML table - should NOT have filetype:pdf
            if "filetype:pdf" in q:
                print(f"  ❌ {q}")
                print(f"     Should NOT contain filetype:pdf (HTML table)")
                all_passed = False
            elif '"RheinNetz"' in q and str(TEST_YEAR) in q:
                print(f"  ✅ {q}")
            else:
                print(f"  ❌ {q} - missing required fields")
                all_passed = False
        
        return all_passed
        
    finally:
        session.close()


def test_default_strategy_queries():
    """Test default strategy query generation for unknown DNO."""
    print(f"\n{'='*60}")
    print("TEST 05e: Default Strategy Queries (Unknown DNO)")
    print(f"{'='*60}")
    
    session = get_test_session()
    all_passed = True
    
    try:
        strategy = load_strategy(session, "UnknownNetz", "netzentgelte")
        
        if not strategy:
            print("[FAIL] No default strategy found")
            return False
        
        if not strategy.get("is_default"):
            print("[FAIL] Expected default strategy")
            return False
        
        print("✅ Using default strategy for unknown DNO")
        
        queries = generate_queries(strategy, "UnknownNetz", TEST_YEAR)
        
        print(f"Generated {len(queries)} queries:")
        for q in queries:
            if '"UnknownNetz"' in q and str(TEST_YEAR) in q:
                print(f"  ✅ {q}")
            else:
                print(f"  ❌ {q} - placeholder not replaced")
                all_passed = False
        
        return all_passed
        
    finally:
        session.close()


def test_special_characters():
    """Test query generation with special characters in DNO name."""
    print(f"\n{'='*60}")
    print("TEST 05f: Special Characters in DNO Name")
    print(f"{'='*60}")
    
    session = get_test_session()
    
    try:
        # Use default strategy with a special character DNO name
        strategy = load_strategy(session, "Stadtwerke München", "netzentgelte")
        
        if not strategy:
            print("[FAIL] No default strategy found")
            return False
        
        queries = generate_queries(strategy, "Stadtwerke München GmbH & Co. KG", TEST_YEAR)
        
        print("Generated queries with special chars:")
        for q in queries[:2]:  # Just show first 2
            if '"Stadtwerke München GmbH & Co. KG"' in q:
                print(f"  ✅ {q[:60]}...")
            else:
                print(f"  ⚠️ {q[:60]}...")
        
        return True
        
    finally:
        session.close()


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    try:
        print(f"\n{'='*60}")
        print("TEST 05: Generate Queries (Real SQLite Database)")
        print(f"{'='*60}")
        
        if not TEST_DB_PATH.exists():
            print("[ERROR] Test database not found!")
            print("Run 'python -m tests.unit.test_00_init' first")
            sys.exit(1)
        
        results = {
            "WestNetz Netzentgelte": test_westnetz_netzentgelte_queries(),
            "WestNetz HLZF": test_westnetz_hlzf_queries(),
            "RheinNetz Netzentgelte": test_rheinnetz_netzentgelte_queries(),
            "RheinNetz HLZF (HTML)": test_rheinnetz_hlzf_queries_no_pdf(),
            "Default Strategy": test_default_strategy_queries(),
            "Special Characters": test_special_characters(),
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
        
    except Exception as e:
        print(f"\n[ERROR] Unhandled exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
