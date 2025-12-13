"""
Test 04: Get Strategies

Tests the strategy loading step of the pipeline:
DNO Name + Match Status → Load Default/Learned Strategy

Input: Hardcoded DNO name + "No Match" flag
Action: Load strategy configuration
Goal: Assert correct DefaultStrat or LoadStrat is returned
Mock: None - tests strategy selection logic

NOTE: The project doesn't have a formal "Strategy" module, so this test
demonstrates the strategy patterns used in SearchEngine.find_pdf_url()
which generates different search query strategies based on pdf_type.
"""

import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# =============================================================================
# HARDCODED TEST INPUTS
# =============================================================================

TEST_DNO_NAME = "RheinNetz"
TEST_YEAR = 2024
TEST_MATCH_STATUS = "no_match"  # Options: "no_match", "partial_match", "complete_match"


# =============================================================================
# DNO-SPECIFIC STRATEGY CONFIGURATIONS
# =============================================================================

# DNO configurations specifying source types for each data category
# source_type: "pdf" = document is a PDF, "html_table" = data is in website table
DNO_CONFIGS = {
    "WestNetz": {
        "netzentgelte": {"source_type": "pdf"},
        "hlzf": {"source_type": "pdf"},
    },
    "RheinNetz": {
        "netzentgelte": {"source_type": "pdf"},
        "hlzf": {"source_type": "html_table"},  # HLZF is displayed as table on website
    },
}


# =============================================================================
# STRATEGY DEFINITIONS
# =============================================================================

class BaseStrategy:
    """Base strategy class for data retrieval."""
    
    def __init__(self, dno_name: str, year: int):
        self.dno_name = dno_name
        self.year = year
        self.config = DNO_CONFIGS.get(dno_name, {
            "netzentgelte": {"source_type": "pdf"},
            "hlzf": {"source_type": "pdf"},
        })
    
    def get_search_queries(self) -> list[str]:
        """Return list of search queries for this strategy."""
        raise NotImplementedError
    
    def get_netzentgelte_source_type(self) -> str:
        """Get the source type for Netzentgelte data."""
        return self.config.get("netzentgelte", {}).get("source_type", "pdf")
    
    def get_hlzf_source_type(self) -> str:
        """Get the source type for HLZF data."""
        return self.config.get("hlzf", {}).get("source_type", "pdf")


class DefaultStrategy(BaseStrategy):
    """
    Default strategy for DNOs with no cached data.
    Uses broad search patterns to find initial PDFs or HTML pages.
    """
    
    def get_netzentgelte_queries(self) -> list[str]:
        """Get search queries for Netzentgelte PDFs."""
        # Netzentgelte is always PDF-based
        return [
            f'"{self.dno_name}" Preisblatt Strom {self.year} filetype:pdf',
            f'"{self.dno_name}" Netznutzungsentgelte {self.year} filetype:pdf',
            f'"{self.dno_name}" Netzentgelte {self.year} filetype:pdf',
            f'"{self.dno_name}" vorläufiges Preisblatt {self.year} filetype:pdf',
        ]
    
    def get_hlzf_queries(self) -> list[str]:
        """Get search queries for HLZF/Regelungen data."""
        source_type = self.get_hlzf_source_type()
        
        if source_type == "html_table":
            # For HTML tables, we search for the webpage without filetype:pdf
            return [
                f'"{self.dno_name}" Hochlastzeitfenster {self.year}',
                f'"{self.dno_name}" Regelungen Strom {self.year}',
                f'"{self.dno_name}" Regelungen Netznutzung {self.year}',
            ]
        else:
            # Default: PDF-based HLZF
            return [
                f'"{self.dno_name}" Regelungen Strom {self.year} filetype:pdf',
                f'"{self.dno_name}" Hochlastzeitfenster {self.year} filetype:pdf',
                f'"{self.dno_name}" Regelungen Netznutzung {self.year} filetype:pdf',
            ]


class LearnedStrategy(BaseStrategy):
    """
    Strategy for DNOs with existing cached data.
    Uses specific patterns learned from previous successful extractions.
    """
    
    def __init__(self, dno_name: str, year: int, known_url_pattern: str = None):
        super().__init__(dno_name, year)
        self.known_url_pattern = known_url_pattern
    
    def get_netzentgelte_queries(self) -> list[str]:
        """Get refined search queries based on learned patterns."""
        # For learned strategy, we might try direct URL first
        queries = []
        if self.known_url_pattern:
            queries.append(f"site:{self.known_url_pattern} Preisblatt {self.year}")
        
        # Fall back to targeted searches
        queries.extend([
            f'"{self.dno_name}" Preisblatt Netznutzungsentgelte {self.year} filetype:pdf',
        ])
        return queries
    
    def get_hlzf_queries(self) -> list[str]:
        """Get refined search queries for HLZF based on source type."""
        source_type = self.get_hlzf_source_type()
        
        queries = []
        if self.known_url_pattern:
            queries.append(f"site:{self.known_url_pattern} Hochlastzeitfenster {self.year}")
        
        if source_type == "html_table":
            queries.append(f'"{self.dno_name}" Hochlastzeitfenster {self.year}')
        else:
            queries.append(f'"{self.dno_name}" Hochlastzeitfenster {self.year} filetype:pdf')
        
        return queries


def load_strategy(dno_name: str, year: int, match_status: str) -> BaseStrategy:
    """
    Load the appropriate strategy based on match status.
    
    Args:
        dno_name: Name of the DNO
        year: Target year
        match_status: One of "no_match", "partial_match", "complete_match"
        
    Returns:
        Appropriate strategy object
    """
    if match_status == "complete_match":
        # No search needed, data exists
        return None
    
    if match_status == "partial_match":
        # Use learned patterns from previous extractions
        known_patterns = {
            "RheinNetz": "www.rheinnetz.de",
            "WestNetz": "www.westnetz.de",
        }
        return LearnedStrategy(dno_name, year, known_url_pattern=known_patterns.get(dno_name))
    
    # Default: no_match
    return DefaultStrategy(dno_name, year)


# =============================================================================
# TEST FUNCTION
# =============================================================================

def test_get_strategies():
    """
    Test that correct strategy is loaded based on match status.
    """
    print(f"\n{'='*60}")
    print("TEST 04: Get Strategies")
    print(f"{'='*60}")
    print(f"Input DNO Name:    {TEST_DNO_NAME}")
    print(f"Input Year:        {TEST_YEAR}")
    print(f"Input Match Status: {TEST_MATCH_STATUS}")
    print("-" * 60)
    
    all_passed = True
    
    # Test 1: No Match → DefaultStrategy
    print("\n[Test 4a] No Match → DefaultStrategy")
    strategy = load_strategy(TEST_DNO_NAME, TEST_YEAR, "no_match")
    
    if not isinstance(strategy, DefaultStrategy):
        print(f"  [FAIL] Expected DefaultStrategy, got {type(strategy)}")
        all_passed = False
    else:
        print("  [PASS] Loaded DefaultStrategy correctly")
        queries = strategy.get_netzentgelte_queries()
        print(f"  - Generated {len(queries)} Netzentgelte queries:")
        for q in queries:
            print(f"    • {q}")
    
    # Test 2: Partial Match → LearnedStrategy
    print("\n[Test 4b] Partial Match → LearnedStrategy")
    strategy = load_strategy(TEST_DNO_NAME, TEST_YEAR, "partial_match")
    
    if not isinstance(strategy, LearnedStrategy):
        print(f"  [FAIL] Expected LearnedStrategy, got {type(strategy)}")
        all_passed = False
    else:
        print("  [PASS] Loaded LearnedStrategy correctly")
        print(f"  - Known URL Pattern: {strategy.known_url_pattern}")
        queries = strategy.get_netzentgelte_queries()
        print(f"  - Generated {len(queries)} refined queries:")
        for q in queries:
            print(f"    • {q}")
    
    # Test 3: Complete Match → None (no search needed)
    print("\n[Test 4c] Complete Match → None")
    strategy = load_strategy(TEST_DNO_NAME, TEST_YEAR, "complete_match")
    
    if strategy is not None:
        print(f"  [FAIL] Expected None, got {type(strategy)}")
        all_passed = False
    else:
        print("  [PASS] Returned None (no search needed)")
    
    # Test 4: Verify HLZF queries generation for RheinNetz (html_table)
    print("\n[Test 4d] RheinNetz HLZF Query Generation (HTML Table)")
    strategy = load_strategy("RheinNetz", TEST_YEAR, "no_match")
    
    hlzf_queries = strategy.get_hlzf_queries()
    if len(hlzf_queries) >= 2:
        print("  [PASS] Generated HLZF queries")
        for q in hlzf_queries:
            print(f"    • {q}")
    else:
        print(f"  [FAIL] Expected at least 2 queries, got {len(hlzf_queries)}")
        all_passed = False
    
    # Verify RheinNetz HLZF does NOT have filetype:pdf (since it's an HTML table)
    print("\n[Test 4e] RheinNetz HLZF: No filetype:pdf (HTML Table Source)")
    for q in hlzf_queries:
        if "filetype:pdf" in q:
            print(f"  [FAIL] RheinNetz HLZF query should NOT contain filetype:pdf: {q}")
            all_passed = False
            break
    else:
        print("  [PASS] RheinNetz HLZF queries do NOT contain filetype:pdf")
        print(f"    - Source type: {strategy.get_hlzf_source_type()}")
    
    # Test 5: WestNetz - All PDF source types
    print("\n[Test 4f] WestNetz Strategy: All PDF Sources")
    strategy = load_strategy("WestNetz", TEST_YEAR, "no_match")
    
    # Verify WestNetz source types
    netz_source = strategy.get_netzentgelte_source_type()
    hlzf_source = strategy.get_hlzf_source_type()
    
    if netz_source == "pdf" and hlzf_source == "pdf":
        print("  [PASS] WestNetz configured for PDF sources")
        print(f"    - Netzentgelte source: {netz_source}")
        print(f"    - HLZF source: {hlzf_source}")
    else:
        print(f"  [FAIL] Expected both PDF sources, got netzentgelte={netz_source}, hlzf={hlzf_source}")
        all_passed = False
    
    # Test 6: WestNetz Netzentgelte has filetype:pdf
    print("\n[Test 4g] WestNetz Netzentgelte: Has filetype:pdf")
    netzentgelte_queries = strategy.get_netzentgelte_queries()
    all_have_pdf = all("filetype:pdf" in q for q in netzentgelte_queries)
    
    if all_have_pdf:
        print("  [PASS] All WestNetz Netzentgelte queries have filetype:pdf")
        for q in netzentgelte_queries:
            print(f"    • {q}")
    else:
        print("  [FAIL] Not all queries have filetype:pdf")
        all_passed = False
    
    # Test 7: WestNetz HLZF has filetype:pdf
    print("\n[Test 4h] WestNetz HLZF: Has filetype:pdf")
    hlzf_queries = strategy.get_hlzf_queries()
    all_have_pdf = all("filetype:pdf" in q for q in hlzf_queries)
    
    if all_have_pdf:
        print("  [PASS] All WestNetz HLZF queries have filetype:pdf")
        for q in hlzf_queries:
            print(f"    • {q}")
    else:
        print("  [FAIL] Not all queries have filetype:pdf")
        all_passed = False
    
    # Test 8: RheinNetz Netzentgelte has filetype:pdf (still PDF-based)
    print("\n[Test 4i] RheinNetz Netzentgelte: Has filetype:pdf")
    rhein_strategy = load_strategy("RheinNetz", TEST_YEAR, "no_match")
    netzentgelte_queries = rhein_strategy.get_netzentgelte_queries()
    all_have_pdf = all("filetype:pdf" in q for q in netzentgelte_queries)
    
    if all_have_pdf:
        print("  [PASS] All RheinNetz Netzentgelte queries have filetype:pdf")
        for q in netzentgelte_queries:
            print(f"    • {q}")
    else:
        print("  [FAIL] Not all queries have filetype:pdf")
        all_passed = False
    
    return all_passed


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    try:
        success = test_get_strategies()
        print(f"\n{'='*60}")
        if success:
            print("RESULT: ✅ ALL TESTS PASSED")
        else:
            print("RESULT: ❌ SOME TESTS FAILED")
        print(f"{'='*60}\n")
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] Unhandled exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
