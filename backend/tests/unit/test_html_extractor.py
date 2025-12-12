"""
Unit tests for HTML Extractor service.
"""

import pytest

from app.services.extraction.html_extractor import (
    extract_hlzf_from_html,
    _clean_cell_text,
    _clean_time_cell,
)


# Sample HTML from RheinNetz website for 2024
SAMPLE_HTML_2024 = """
<h3>Stand 05.10.2023 gültig ab 01.01.2024</h3>
<div class="table-wrapper">
    <table>
      <thead>
        <tr>
          <th><p>Spannungsebene</p></th>
          <th><p>Frühjahr</p></th>
          <th><p>Sommer</p></th>
          <th><p>Herbst</p></th>
          <th><p>Winter</p></th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><p>HS</p></td>
          <td><p>10:00 - 11:30<br>12:00 - 13:15</p></td>
          <td><p>12:30 - 13:00</p></td>
          <td><p></p></td>
          <td><p>09:00 - 19:15</p></td>
        </tr>
        <tr>
          <td><p>MS</p></td>
          <td><p></p></td>
          <td><p></p></td>
          <td><p></p></td>
          <td><p>10:00 - 14:30</p></td>
        </tr>
      </tbody>
    </table>
</div>
"""

SAMPLE_HTML_NO_TABLE = """
<h3>No HLZF data available</h3>
<p>Please check back later.</p>
"""


class TestExtractHLZFFromHTML:
    """Test HLZF extraction from HTML tables."""
    
    def test_extract_basic_table(self):
        """Test extracting from basic HLZF table."""
        records = extract_hlzf_from_html(SAMPLE_HTML_2024, 2024)
        
        assert len(records) == 2
        
        # Check HS record
        hs = next((r for r in records if r["voltage_level"] == "HS"), None)
        assert hs is not None
        assert hs["winter"] == "09:00 - 19:15"
        assert "12:30 - 13:00" in (hs["sommer"] or "")
    
    def test_extract_empty_cells(self):
        """Test empty cells are handled as None."""
        records = extract_hlzf_from_html(SAMPLE_HTML_2024, 2024)
        
        ms = next((r for r in records if r["voltage_level"] == "MS"), None)
        assert ms is not None
        assert ms["fruehling"] is None
        assert ms["sommer"] is None
        assert ms["herbst"] is None
    
    def test_extract_no_table(self):
        """Test extraction from HTML without table."""
        records = extract_hlzf_from_html(SAMPLE_HTML_NO_TABLE, 2024)
        assert records == []
    
    def test_extract_empty_html(self):
        """Test extraction from empty HTML."""
        records = extract_hlzf_from_html("", 2024)
        assert records == []
    
    def test_extract_multiline_times(self):
        """Test extraction of multiline time values."""
        records = extract_hlzf_from_html(SAMPLE_HTML_2024, 2024)
        
        hs = next((r for r in records if r["voltage_level"] == "HS"), None)
        assert hs is not None
        # Frühjahr has multiple time windows
        fruehling = hs["fruehling"]
        assert fruehling is not None
        assert "10:00 - 11:30" in fruehling
        assert "12:00 - 13:15" in fruehling


class TestCleanCellText:
    """Test cell text cleaning helper."""
    
    def test_clean_simple_text(self):
        """Test cleaning simple text."""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup("<td><p>HS</p></td>", "html.parser")
        cell = soup.find("td")
        
        result = _clean_cell_text(cell)
        assert result == "HS"
    
    def test_clean_text_with_whitespace(self):
        """Test cleaning text with extra whitespace."""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup("<td><p>  Hochspannung   </p></td>", "html.parser")
        cell = soup.find("td")
        
        result = _clean_cell_text(cell)
        assert result == "Hochspannung"


class TestCleanTimeCell:
    """Test time cell cleaning helper."""
    
    def test_clean_single_time(self):
        """Test cleaning single time value."""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup("<td><p>09:00 - 17:00</p></td>", "html.parser")
        cell = soup.find("td")
        
        result = _clean_time_cell(cell)
        assert result == "09:00 - 17:00"
    
    def test_clean_multiple_times(self):
        """Test cleaning multiple time values with <br>."""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup("<td><p>09:00 - 12:00<br>14:00 - 17:00</p></td>", "html.parser")
        cell = soup.find("td")
        
        result = _clean_time_cell(cell)
        assert "09:00 - 12:00" in result
        assert "14:00 - 17:00" in result
    
    def test_clean_empty_cell(self):
        """Test cleaning empty cell returns None."""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup("<td><p></p></td>", "html.parser")
        cell = soup.find("td")
        
        result = _clean_time_cell(cell)
        assert result is None


class TestHLZFDataIntegrity:
    """Test data integrity of extracted HLZF data."""
    
    def test_all_voltage_levels_present(self):
        """Test that all voltage levels are extracted."""
        html = """
        <table>
          <tbody>
            <tr><td>HS</td><td>09:00</td><td></td><td></td><td>10:00</td></tr>
            <tr><td>HS/MS</td><td></td><td></td><td></td><td>11:00</td></tr>
            <tr><td>MS</td><td></td><td></td><td></td><td>12:00</td></tr>
            <tr><td>MS/NS</td><td></td><td></td><td></td><td>13:00</td></tr>
            <tr><td>NS</td><td></td><td></td><td></td><td>14:00</td></tr>
          </tbody>
        </table>
        """
        records = extract_hlzf_from_html(html, 2024)
        
        voltage_levels = {r["voltage_level"] for r in records}
        expected = {"HS", "HS/MS", "MS", "MS/NS", "NS"}
        assert voltage_levels == expected
