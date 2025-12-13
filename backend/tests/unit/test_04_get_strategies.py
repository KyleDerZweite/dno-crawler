"""
Test 04: Get Strategies

Tests the strategy loading step of the pipeline:
DNO Name + Match Status → Load Default/Learned Strategy

This test uses the SQLite test database initialized by test_00_init.py
to load real strategy configurations stored in ExtractionStrategyModel.

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

TEST_DNO_NAME = "RheinNetz"
TEST_YEAR = 2024


# =============================================================================
# HELPER: Load strategy from database
# =============================================================================

def load_strategy_from_db(session, dno_name: str, strategy_type: str) -> dict | None:
    """
    Load an extraction strategy from the database.
    
    Args:
        session: SQLAlchemy session
        dno_name: Name of the DNO (e.g., "RheinNetz")
        strategy_type: "netzentgelte" or "hlzf"
        
    Returns:
        Strategy config dict or None if not found
    """
    from app.db.models import ExtractionStrategyModel, DNOModel
    from sqlalchemy import select, and_
    
    # First, find the DNO
    dno = session.execute(
        select(DNOModel).where(DNOModel.name == dno_name)
    ).scalar_one_or_none()
    
    if dno:
        # Look for DNO-specific strategy
        strategy = session.execute(
            select(ExtractionStrategyModel).where(
                and_(
                    ExtractionStrategyModel.dno_id == dno.id,
                    ExtractionStrategyModel.strategy_type == strategy_type
                )
            )
        ).scalar_one_or_none()
        
        if strategy:
            return {
                "id": strategy.id,
                "dno_id": strategy.dno_id,
                "dno_name": dno_name,
                "strategy_type": strategy_type,
                "config": strategy.config,
                "success_count": strategy.success_count,
                "failure_count": strategy.failure_count,
                "is_default": False,
            }
    
    # Fall back to default strategy (no dno_id)
    default = session.execute(
        select(ExtractionStrategyModel).where(
            and_(
                ExtractionStrategyModel.dno_id.is_(None),
                ExtractionStrategyModel.strategy_type == strategy_type
            )
        )
    ).scalar_one_or_none()
    
    if default:
        return {
            "id": default.id,
            "dno_id": None,
            "dno_name": dno_name,  # Will be used for query generation
            "strategy_type": strategy_type,
            "config": default.config,
            "success_count": default.success_count,
            "failure_count": default.failure_count,
            "is_default": True,
        }
    
    return None


def generate_queries(strategy: dict, dno_name: str, year: int) -> list[str]:
    """
    Generate search queries from a strategy, filling in placeholders.
    
    Placeholders: {dno_name}, {year}
    """
    config = strategy.get("config", {})
    query_templates = config.get("search_queries", [])
    
    queries = []
    for template in query_templates:
        query = template.replace("{dno_name}", dno_name).replace("{year}", str(year))
        queries.append(query)
    
    return queries


# =============================================================================
# TESTS
# =============================================================================

def test_load_westnetz_strategy():
    """Test loading WestNetz strategies from database."""
    print(f"\n{'='*60}")
    print("TEST 04a: Load WestNetz Strategies")
    print(f"{'='*60}")
    
    session = get_test_session()
    all_passed = True
    
    try:
        # Netzentgelte strategy
        netz_strategy = load_strategy_from_db(session, "WestNetz", "netzentgelte")
        
        if not netz_strategy:
            print("[FAIL] WestNetz netzentgelte strategy not found")
            return False
        
        config = netz_strategy["config"]
        print("[PASS] Loaded WestNetz Netzentgelte strategy")
        print(f"  - Content format: {config.get('content_format')}")
        print(f"  - Success count: {netz_strategy['success_count']}")
        print(f"  - Extraction method: {config.get('extraction_method')}")
        
        # Verify it's PDF-based
        if config.get("content_format") != "pdf_table":
            print(f"[FAIL] Expected content_format 'pdf_table', got '{config.get('content_format')}'")
            all_passed = False
        
        # HLZF strategy
        hlzf_strategy = load_strategy_from_db(session, "WestNetz", "hlzf")
        
        if not hlzf_strategy:
            print("[FAIL] WestNetz hlzf strategy not found")
            return False
        
        hlzf_config = hlzf_strategy["config"]
        print("\n[PASS] Loaded WestNetz HLZF strategy")
        print(f"  - Content format: {hlzf_config.get('content_format')}")
        
        # Verify WestNetz HLZF is also PDF-based
        if hlzf_config.get("content_format") != "pdf_table":
            print(f"[FAIL] Expected content_format 'pdf_table', got '{hlzf_config.get('content_format')}'")
            all_passed = False
        
        return all_passed
        
    finally:
        session.close()


def test_load_rheinnetz_strategy():
    """Test loading RheinNetz strategies - HLZF should be HTML table!"""
    print(f"\n{'='*60}")
    print("TEST 04b: Load RheinNetz Strategies (HLZF = HTML Table)")
    print(f"{'='*60}")
    
    session = get_test_session()
    all_passed = True
    
    try:
        # Netzentgelte strategy (PDF)
        netz_strategy = load_strategy_from_db(session, "RheinNetz", "netzentgelte")
        
        if not netz_strategy:
            print("[FAIL] RheinNetz netzentgelte strategy not found")
            return False
        
        netz_config = netz_strategy["config"]
        print("[PASS] Loaded RheinNetz Netzentgelte strategy")
        print(f"  - Content format: {netz_config.get('content_format')}")
        
        if netz_config.get("content_format") != "pdf_table":
            print(f"[FAIL] Expected 'pdf_table', got '{netz_config.get('content_format')}'")
            all_passed = False
        
        # HLZF strategy (HTML Table!)
        hlzf_strategy = load_strategy_from_db(session, "RheinNetz", "hlzf")
        
        if not hlzf_strategy:
            print("[FAIL] RheinNetz hlzf strategy not found")
            return False
        
        hlzf_config = hlzf_strategy["config"]
        print("\n[PASS] Loaded RheinNetz HLZF strategy")
        print(f"  - Content format: {hlzf_config.get('content_format')}")
        print(f"  - CSS selector: {hlzf_config.get('css_selector')}")
        
        # CRITICAL: RheinNetz HLZF uses HTML table, not PDF
        if hlzf_config.get("content_format") != "html_table":
            print(f"[FAIL] Expected 'html_table', got '{hlzf_config.get('content_format')}'")
            all_passed = False
        else:
            print("  ✅ Correctly identified as HTML table source")
        
        return all_passed
        
    finally:
        session.close()


def test_generate_queries_with_placeholders():
    """Test query generation with {dno_name} and {year} placeholders."""
    print(f"\n{'='*60}")
    print("TEST 04c: Query Generation with Placeholders")
    print(f"{'='*60}")
    
    session = get_test_session()
    all_passed = True
    
    try:
        # Load WestNetz netzentgelte strategy
        strategy = load_strategy_from_db(session, "WestNetz", "netzentgelte")
        queries = generate_queries(strategy, "WestNetz", 2024)
        
        print(f"Generated {len(queries)} queries for WestNetz 2024:")
        for q in queries:
            print(f"  • {q}")
            
            # Verify placeholders were replaced
            if "{dno_name}" in q or "{year}" in q:
                print(f"    ❌ Placeholder not replaced!")
                all_passed = False
            
            # Verify WestNetz netzentgelte uses filetype:pdf
            if "filetype:pdf" not in q:
                print(f"    ❌ Missing filetype:pdf")
                all_passed = False
        
        print()
        
        # Load RheinNetz HLZF strategy (should NOT have filetype:pdf)
        hlzf_strategy = load_strategy_from_db(session, "RheinNetz", "hlzf")
        hlzf_queries = generate_queries(hlzf_strategy, "RheinNetz", 2024)
        
        print(f"Generated {len(hlzf_queries)} queries for RheinNetz HLZF 2024:")
        for q in hlzf_queries:
            print(f"  • {q}")
            
            # RheinNetz HLZF is HTML table - should NOT have filetype:pdf
            if "filetype:pdf" in q:
                print(f"    ❌ Should NOT contain filetype:pdf (HTML table)")
                all_passed = False
            else:
                print(f"    ✅ Correctly omits filetype:pdf")
        
        return all_passed
        
    finally:
        session.close()


def test_default_strategy_fallback():
    """Test that unknown DNOs fall back to default strategy."""
    print(f"\n{'='*60}")
    print("TEST 04d: Default Strategy Fallback")
    print(f"{'='*60}")
    
    session = get_test_session()
    
    try:
        # Try loading strategy for a DNO that doesn't have a specific config
        strategy = load_strategy_from_db(session, "UnknownNetz", "netzentgelte")
        
        if not strategy:
            print("[FAIL] No strategy returned (expected default)")
            return False
        
        if not strategy.get("is_default"):
            print(f"[FAIL] Expected default strategy, got DNO-specific")
            return False
        
        print("[PASS] Correctly fell back to default strategy")
        print(f"  - is_default: {strategy['is_default']}")
        print(f"  - content_format: {strategy['config'].get('content_format')}")
        print(f"  - queries: {len(strategy['config'].get('search_queries', []))}")
        
        return True
        
    finally:
        session.close()


def test_strategy_success_rates():
    """Test that success rates are stored in strategy config."""
    print(f"\n{'='*60}")
    print("TEST 04e: Strategy Success Rates")
    print(f"{'='*60}")
    
    session = get_test_session()
    
    try:
        strategy = load_strategy_from_db(session, "WestNetz", "netzentgelte")
        
        if not strategy:
            print("[FAIL] Strategy not found")
            return False
        
        config = strategy["config"]
        success_rates = config.get("query_success_rates", {})
        
        print("[PASS] Loaded strategy with success rates")
        print(f"  - Success count: {strategy['success_count']}")
        print(f"  - Failure count: {strategy['failure_count']}")
        
        if success_rates:
            print("  - Query success rates:")
            for query_template, rate in success_rates.items():
                short_query = query_template[:50] + "..." if len(query_template) > 50 else query_template
                print(f"    • {short_query}: {rate:.0%}")
        
        return True
        
    finally:
        session.close()


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    try:
        print(f"\n{'='*60}")
        print("TEST 04: Get Strategies (Real SQLite Database)")
        print(f"{'='*60}")
        
        if not TEST_DB_PATH.exists():
            print("[ERROR] Test database not found!")
            print("Run 'python -m tests.unit.test_00_init' first")
            sys.exit(1)
        
        results = {
            "WestNetz Strategy": test_load_westnetz_strategy(),
            "RheinNetz Strategy": test_load_rheinnetz_strategy(),
            "Query Generation": test_generate_queries_with_placeholders(),
            "Default Fallback": test_default_strategy_fallback(),
            "Success Rates": test_strategy_success_rates(),
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
