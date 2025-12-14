"""
HTML Extractor service for extracting data from HTML tables.

Extracted from tests/flow_test.py - this is production code that was
mistakenly placed in a test file.
"""

from typing import Any

from bs4 import BeautifulSoup


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
