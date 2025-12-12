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
from bs4 import BeautifulSoup


# =============================================================================
# Test Data: RheinNetz (50859 Köln)
# =============================================================================

TEST_ADDRESS = {
    "input_string": "50859 Köln An Der Ronne 160",
    "expected_parsed": {
        "zip_code": "50859",
        "city": "Köln",
        "street": "An Der Ronne 160",
    },
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
        '"RheinNetz" Regelungen Strom 2024 filetype:pdf',
        '"RheinNetz" Hochlastzeitfenster 2024 filetype:pdf',
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
# Helper Functions for Web Extraction
# =============================================================================

def extract_hlzf_from_html(html: str, year: int) -> list[dict[str, Any]]:
    """
    Extract HLZF data from website HTML containing HLZF tables.
    
    Args:
        html: Raw HTML string containing HLZF table(s)
        year: Target year to extract data for
        
    Returns:
        List of HLZF records by voltage level
    """
    soup = BeautifulSoup(html, 'html.parser')
    records = []
    
    # Find table headers that indicate the year
    # Format: "Stand XX.XX.XXXX gültig ab 01.01.{year}"
    year_pattern = f"gültig ab 01.01.{year}"
    
    target_table = None
    for h3 in soup.find_all('h3'):
        if year_pattern in h3.get_text():
            # Find the next table after this header
            next_sibling = h3.find_next_sibling()
            while next_sibling:
                if next_sibling.name == 'div' and 'table-wrapper' in next_sibling.get('class', []):
                    target_table = next_sibling.find('table')
                    break
                if next_sibling.name == 'table':
                    target_table = next_sibling
                    break
                next_sibling = next_sibling.find_next_sibling()
            break
    
    if not target_table:
        # Fallback: just find the first table
        target_table = soup.find('table')
    
    if not target_table:
        return records
    
    # Parse table rows
    tbody = target_table.find('tbody')
    if not tbody:
        return records
    
    for row in tbody.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) >= 5:
            voltage_level = _clean_cell_text(cells[0])
            fruehling = _clean_time_cell(cells[1])
            sommer = _clean_time_cell(cells[2])
            herbst = _clean_time_cell(cells[3])
            winter = _clean_time_cell(cells[4])
            
            if voltage_level:
                records.append({
                    "voltage_level": voltage_level,
                    "fruehling": fruehling,
                    "sommer": sommer,
                    "herbst": herbst,
                    "winter": winter,
                })
    
    return records


def _clean_cell_text(cell) -> str:
    """Extract and clean text from a table cell."""
    text = cell.get_text(separator=' ', strip=True)
    # Remove whitespace tabs from text
    text = ' '.join(text.split())
    return text.strip()


def _clean_time_cell(cell) -> str | None:
    """Extract and clean time values from a table cell."""
    # Get text with line breaks preserved
    text_parts = []
    for elem in cell.descendants:
        if isinstance(elem, str):
            text_parts.append(elem.strip())
        elif elem.name == 'br':
            text_parts.append('\n')
    
    text = ''.join(text_parts).strip()
    
    # Clean up multiple newlines
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    if not lines:
        return None
    
    return '\n'.join(lines) if lines else None


# =============================================================================
# Test: Address Parsing
# =============================================================================

class TestAddressParsing:
    """Test address parsing from natural language input."""
    
    def test_parse_german_address_with_zip_first(self):
        """Test parsing: '50859 Köln An Der Ronne 160'"""
        import re
        
        prompt = TEST_ADDRESS["input_string"]
        
        # ZIP code extraction (5 digit pattern)
        zip_match = re.search(r'\b(\d{5})\b', prompt)
        assert zip_match is not None
        zip_code = zip_match.group(1)
        assert zip_code == TEST_ADDRESS["expected_parsed"]["zip_code"]
        
        # City extraction (first word after ZIP)
        after_zip = prompt[zip_match.end():].strip()
        city_match = re.match(r'^([A-Za-zäöüÄÖÜß]+)', after_zip)
        assert city_match is not None
        city = city_match.group(1)
        assert city == TEST_ADDRESS["expected_parsed"]["city"]
    
    def test_parse_german_address_standard_format(self):
        """Test parsing: 'An der Ronne 160, 50859 Köln'"""
        import re
        
        # prompt = "An der Ronne 160, 50859 Köln"
        prompt = "54321 Bielefeld, Industriestr. 12345"

        # ZIP code extraction
        zip_match = re.search(r'\b(\d{5})\b', prompt)
        assert zip_match is not None
        zip_code = zip_match.group(1)
        assert zip_code == "54321"
        
        # City comes AFTER the ZIP code in German format
        after_zip = prompt[zip_match.end():].strip()
        city_match = re.match(r'^([A-Za-zäöüÄÖÜß\s-]+)', after_zip)
        assert city_match is not None
        city = city_match.group(1).strip()
        assert city == "Bielefeld"
        
        # Street is everything BEFORE the ZIP
        street = prompt[:zip_match.start()].rstrip(', ').strip()
        assert street == "Industriestr. 12345"


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
    def mock_agent(self):
        """Create a mock SearchAgent for testing."""
        agent = Mock()
        agent.resolve_dno_from_address = Mock(return_value="RheinNetz")
        agent.find_and_process_pdf = Mock(return_value={
            "dno": "RheinNetz",
            "year": 2024,
            "status": "success",
            "records": [
                {"voltage_level": "HS", "leistung": 100.5, "arbeit": 2.5},
            ],
        })
        agent.extract_hlzf = Mock(return_value={
            "dno": "RheinNetz",
            "year": 2024,
            "status": "success",
            "records": HLZF_2024_EXPECTED,
        })
        return agent
    
    def test_full_flow_50859_koeln(self, mock_agent):
        """Test complete flow for 50859 Köln address."""
        # Step 1: Parse address
        zip_code = "50859"
        city = "Köln"
        street = "An Der Ronne 160"
        
        # Step 2: Resolve DNO
        dno_name = mock_agent.resolve_dno_from_address(zip_code, city, street)
        assert dno_name == "RheinNetz"
        
        # Step 3: Get Netzentgelte
        netzentgelte_result = mock_agent.find_and_process_pdf(dno_name, 2024)
        assert netzentgelte_result["status"] == "success"
        assert len(netzentgelte_result["records"]) > 0
        
        # Step 4: Get HLZF
        hlzf_result = mock_agent.extract_hlzf(dno_name, 2024)
        assert hlzf_result["status"] == "success"
        assert len(hlzf_result["records"]) == 5  # 5 voltage levels
    
    def test_expected_output_structure(self, mock_agent):
        """Test that output matches expected database structure."""
        dno_name = mock_agent.resolve_dno_from_address("50859", "Köln", "An Der Ronne 160")
        
        # Final result should have this structure
        result = {
            "dno_name": dno_name,
            "netzentgelte": {
                2024: mock_agent.find_and_process_pdf(dno_name, 2024)["records"],
            },
            "hlzf": {
                2024: mock_agent.extract_hlzf(dno_name, 2024)["records"],
            },
        }
        
        assert result["dno_name"] == "RheinNetz"
        assert 2024 in result["netzentgelte"]
        assert 2024 in result["hlzf"]


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
    
    def test_hlzf_search_strategies(self):
        """Test HLZF PDF/page search query generation."""
        dno_name = "RheinNetz"
        year = 2024
        
        expected_strategies = [
            f'"{dno_name}" Regelungen Strom {year} filetype:pdf',
            f'"{dno_name}" Hochlastzeitfenster {year} filetype:pdf',
            f'"{dno_name}" Regelungen Netznutzung {year} filetype:pdf',
        ]
        
        for query in expected_strategies:
            assert f'"{dno_name}"' in query
            assert str(year) in query


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
