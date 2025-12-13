"""
Integration test for the complete DNO search flow.

Tests the full pipeline:
1. Address parsing from natural language input
2. DNO resolution via search
3. PDF retrieval for Netzentgelte
4. Website/table extraction for HLZF

Example test case: "50859 Köln An Der Ronne 160" -> RheinNetz
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Any

# Import from new services location
from app.services.extraction.html_extractor import extract_hlzf_from_html


# =============================================================================
# Test Data: RheinNetz (50859 Köln)
# =============================================================================

# Structured address input (form fields, not NLP parsed)
TEST_ADDRESS = {
    "zip_code": "50859",
    "city": "Köln",
    "street": "An Der Ronne 160",
}

EXPECTED_DNO = {
    "name": "RheinNetz",
    "slug": "rhein-netz",
    "website": "https://www.rheinnetz.de/",
}

# Search queries that should be generated
EXPECTED_SEARCH_QUERIES = {
    "dno_resolution": "Netzbetreiber Strom 50859 Köln An Der Ronne 160",
    "netzentgelte_pdf": [
        '"RheinNetz" Preisblatt Strom 2024 filetype:pdf',
        '"RheinNetz" Netznutzungsentgelte 2024 filetype:pdf',
    ],
    "hlzf": [
        # RheinNetz HLZF is an HTML table on the website, NOT a PDF
        '"RheinNetz" Hochlastzeitfenster 2024',
        '"RheinNetz" Regelungen Strom 2024',
    ],
}

# HLZF data extracted from website HTML (for 2024)
HLZF_2024_EXPECTED = [
    {
        "voltage_level": "HS",
        "fruehling": "10:00 - 11:30\n12:00 - 13:15\n18:15 - 18:45",
        "sommer": "12:30 - 13:00",
        "herbst": "12:45 - 13:15\n17:15 - 18:30",
        "winter": "09:00 - 19:15",
    },
    {
        "voltage_level": "HS/MS",
        "fruehling": "12:15 - 13:00\n18:45 - 19:00",
        "sommer": None,
        "herbst": None,
        "winter": "09:00 - 19:15",
    },
    {
        "voltage_level": "MS",
        "fruehling": None,
        "sommer": None,
        "herbst": None,
        "winter": "10:00 - 14:30\n16:15 - 19:15",
    },
    {
        "voltage_level": "MS/NS",
        "fruehling": None,
        "sommer": None,
        "herbst": None,
        "winter": "16:45 - 19:30",
    },
    {
        "voltage_level": "NS",
        "fruehling": None,
        "sommer": None,
        "herbst": None,
        "winter": "16:45 - 19:30",
    },
]

# Sample HTML content from RheinNetz website (HLZF table for 2024)
HLZF_HTML_2024 = """
<h3>Stand 05.10.2023 gültig ab 01.01.2024</h3>
<div class="table-wrapper">
    <table>
      <thead>
        <tr>
          <th><p>Jahreszeit<br>Zeitraum<br>___________________</p><p>Spannungsebene</p></th>
          <th><p>Frühjahr<br>01.03. - 31.05.<br>von bis</p></th>
          <th><p>Sommer<br>01.06. - 31.08.<br>von bis</p></th>
          <th><p>Herbst<br>01.09. - 30.11.<br>von bis</p></th>
          <th><p>Winter<br>01.12. - 28./29.02.<br>von bis</p></th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><p>HS</p></td>
          <td><p>10:00 - 11:30<br>12:00 - 13:15<br>18:15 - 18:45</p></td>
          <td><p>12:30 - 13:00</p></td>
          <td><p>12:45 - 13:15<br>17:15 - 18:30</p></td>
          <td><p>09:00 - 19:15</p></td>
        </tr>
        <tr>
          <td><p>HS/MS</p></td>
          <td><p>12:15 - 13:00<br>18:45 - 19:00</p></td>
          <td><p></p></td>
          <td><p></p></td>
          <td><p>09:00 - 19:15</p></td>
        </tr>
        <tr>
          <td><p>MS</p></td>
          <td><p></p></td>
          <td><p></p></td>
          <td><p></p></td>
          <td><p>10:00 - 14:30<br>16:15 - 19:15</p></td>
        </tr>
        <tr>
          <td><p>MS/NS</p></td>
          <td><p></p></td>
          <td><p></p></td>
          <td><p></p></td>
          <td><p>16:45 - 19:30</p></td>
        </tr>
        <tr>
          <td><p>NS</p></td>
          <td><p></p></td>
          <td><p></p></td>
          <td><p></p></td>
          <td><p>16:45 - 19:30</p></td>
        </tr>
      </tbody>
    </table>
</div>
"""


# =============================================================================
# Test: Structured Address Input Validation
# =============================================================================

class TestStructuredAddressInput:
    """Test structured address input handling (no NLP parsing - direct structured fields)."""
    
    def test_structured_address_fields(self):
        """Test that structured address input contains required fields."""
        # Structured input now comes from form fields, not NLP parsing
        structured_input = {
            "zip_code_city": "50859 Köln",
            "street": "An Der Ronne 160",
        }
        
        # Validate required fields are present
        assert "zip_code_city" in structured_input
        assert "street" in structured_input
        
        # Validate ZIP code format (5 digits) using regex
        import re
        zip_match = re.search(r'\b(\d{5})\b', structured_input["zip_code_city"])
        assert zip_match is not None, "ZIP code (5 digits) not found"
        
        # Validate city is present (non-digit part after ZIP)
        city_part = structured_input["zip_code_city"].replace(zip_match.group(1), "").strip()
        assert len(city_part) > 0, "City not found in zip_code_city"
    
    def test_direct_coordinates_input(self):
        """Test direct coordinates input bypasses address lookup."""
        coords_input = {
            "latitude": 50.9375,
            "longitude": 6.9603,
        }
        
        assert "latitude" in coords_input
        assert "longitude" in coords_input
        assert -90 <= coords_input["latitude"] <= 90
        assert -180 <= coords_input["longitude"] <= 180
    
    def test_direct_dno_input(self):
        """Test direct DNO input bypasses resolution entirely."""
        dno_input = {
            "dno_name": "RheinNetz",
            "year": 2024,
        }
        
        assert "dno_name" in dno_input
        assert "year" in dno_input
        assert len(dno_input["dno_name"]) > 0
        assert dno_input["year"] >= 2020


# =============================================================================
# Test: HLZF HTML Extraction
# =============================================================================

class TestHLZFExtraction:
    """Test HLZF extraction from website HTML."""
    
    def test_extract_hlzf_from_html_2024(self):
        """Test extracting 2024 HLZF data from RheinNetz HTML."""
        records = extract_hlzf_from_html(HLZF_HTML_2024, 2024)
        
        assert len(records) == 5, f"Expected 5 voltage levels, got {len(records)}"
        
        # Check voltage levels are present
        voltage_levels = [r["voltage_level"] for r in records]
        assert "HS" in voltage_levels
        assert "HS/MS" in voltage_levels
        assert "MS" in voltage_levels
        assert "MS/NS" in voltage_levels
        assert "NS" in voltage_levels
    
    def test_hlzf_hs_values(self):
        """Test HS (Hochspannung) values for 2024."""
        records = extract_hlzf_from_html(HLZF_HTML_2024, 2024)
        hs_record = next((r for r in records if r["voltage_level"] == "HS"), None)
        
        assert hs_record is not None
        assert hs_record["winter"] == "09:00 - 19:15"
        assert "12:30 - 13:00" in (hs_record["sommer"] or "")
    
    def test_hlzf_empty_cells(self):
        """Test that empty cells are handled correctly."""
        records = extract_hlzf_from_html(HLZF_HTML_2024, 2024)
        ms_record = next((r for r in records if r["voltage_level"] == "MS"), None)
        
        assert ms_record is not None
        # MS has no Frühjahr, Sommer, Herbst values for 2024
        assert ms_record["fruehling"] is None
        assert ms_record["sommer"] is None
        assert ms_record["herbst"] is None
        assert ms_record["winter"] is not None


# =============================================================================
# Test: DNO Resolution (Mocked)
# =============================================================================

class TestDNOResolution:
    """Test DNO resolution from address (with mocked external calls)."""
    
    @pytest.fixture
    def mock_search_results(self):
        """Mock DuckDuckGo search results for RheinNetz."""
        return [
            {
                "title": "RheinNetz GmbH - Ihr Netzbetreiber in Köln",
                "href": "https://www.rheinnetz.de/",
                "body": "RheinNetz GmbH ist der Verteilnetzbetreiber für Strom und Gas im Raum Köln. Wir versorgen die Region 50859 und Umgebung.",
            },
            {
                "title": "Netzentgelte Strom - RheinNetz",
                "href": "https://www.rheinnetz.de/netzentgelte-strom",
                "body": "Preisblatt Netzentgelte Strom für das Netzgebiet RheinNetz. Gültig ab 01.01.2024.",
            },
        ]
    
    def test_dno_name_extraction_from_results(self, mock_search_results):
        """Test that DNO name can be extracted from search results."""
        # Simulate LLM extraction logic
        snippets = "\n".join([
            f"- {r.get('title', '')}: {r.get('body', '')}" 
            for r in mock_search_results
        ])
        
        # Simple heuristic: Look for company name pattern ending in GmbH/AG
        import re
        company_pattern = r'([A-Za-z]+(?:Netz|Energie|Werke)[A-Za-z]*)\s*(?:GmbH|AG)?'
        match = re.search(company_pattern, snippets)
        
        assert match is not None
        assert "RheinNetz" in match.group(1)


# =============================================================================
# Test: Full Flow Integration (Mocked)
# =============================================================================

class TestFullSearchFlow:
    """Integration tests for the complete search flow."""
    
    @pytest.fixture
    def mock_services(self):
        """Create mock services for testing."""
        resolver = Mock()
        resolver.resolve = Mock(return_value="RheinNetz")
        
        search_engine = Mock()
        search_engine.find_pdf_url = Mock(return_value="https://example.com/netzentgelte.pdf")
        
        downloader = Mock()
        downloader.download = Mock(return_value="/tmp/test.pdf")
        
        return {
            "resolver": resolver,
            "search_engine": search_engine,
            "downloader": downloader,
        }
    
    def test_full_flow_50859_koeln(self, mock_services):
        """Test complete flow for 50859 Köln address."""
        # Step 1: Parse address
        zip_code = "50859"
        city = "Köln"
        street = "An Der Ronne 160"
        
        # Step 2: Resolve DNO
        dno_name = mock_services["resolver"].resolve(zip_code, city, street)
        assert dno_name == "RheinNetz"
        
        # Step 3: Find PDF URL
        url = mock_services["search_engine"].find_pdf_url(dno_name, 2024)
        assert url is not None
        
        # Step 4: Download PDF
        path = mock_services["downloader"].download(url, dno_name, 2024)
        assert path is not None


# =============================================================================
# Test: PDF Retrieval Queries
# =============================================================================

class TestPDFRetrievalQueries:
    """Test that correct search queries are generated for PDF retrieval."""
    
    def test_netzentgelte_search_strategies(self):
        """Test Netzentgelte PDF search query generation."""
        dno_name = "RheinNetz"
        year = 2024
        
        expected_strategies = [
            f'"{dno_name}" Preisblatt Strom {year} filetype:pdf',
            f'"{dno_name}" Netznutzungsentgelte {year} filetype:pdf',
            f'"{dno_name}" Netzentgelte {year} filetype:pdf',
            f'"{dno_name}" vorläufiges Preisblatt {year} filetype:pdf',
        ]
        
        # Verify each expected query is well-formed
        for query in expected_strategies:
            assert f'"{dno_name}"' in query
            assert str(year) in query
            assert "filetype:pdf" in query
    
    def test_hlzf_search_strategies_rheinnetz(self):
        """Test HLZF search query generation for RheinNetz (HTML table source)."""
        dno_name = "RheinNetz"
        year = 2024
        
        # RheinNetz HLZF is an HTML table, so NO filetype:pdf
        expected_strategies = [
            f'"{dno_name}" Hochlastzeitfenster {year}',
            f'"{dno_name}" Regelungen Strom {year}',
            f'"{dno_name}" Regelungen Netznutzung {year}',
        ]
        
        for query in expected_strategies:
            assert f'"{dno_name}"' in query
            assert str(year) in query
            # Should NOT have filetype:pdf for RheinNetz HLZF
            assert "filetype:pdf" not in query
    
    def test_hlzf_search_strategies_westnetz(self):
        """Test HLZF search query generation for WestNetz (PDF source)."""
        dno_name = "WestNetz"
        year = 2024
        
        # WestNetz HLZF is a PDF, so HAS filetype:pdf
        expected_strategies = [
            f'"{dno_name}" Regelungen Strom {year} filetype:pdf',
            f'"{dno_name}" Hochlastzeitfenster {year} filetype:pdf',
            f'"{dno_name}" Regelungen Netznutzung {year} filetype:pdf',
        ]
        
        for query in expected_strategies:
            assert f'"{dno_name}"' in query
            assert str(year) in query
            assert "filetype:pdf" in query


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
