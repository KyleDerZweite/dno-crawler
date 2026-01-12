"""
HTML Stripper Service

Strips HTML files to essential content (tables + year headers) and
optionally splits multi-year pages into year-specific files for cache compatibility.

Usage:
    from app.services.extraction.html_stripper import HtmlStripper

    stripper = HtmlStripper()
    years_found = stripper.strip_and_split(
        html_content="<html>...",
        output_dir=Path("data/downloads/rheinnetz"),
        slug="rheinnetz",
        data_type="hlzf"
    )
"""

import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag


class HtmlStripper:
    """
    Strips HTML files to essential content for data extraction.

    Removes:
    - <head>, <style>, <script> elements
    - Navigation, footer, header elements
    - Inline styles and unnecessary attributes

    Keeps:
    - <table> elements with their headers
    - <h2>, <h3> headers that identify years/sections
    - Essential structure for parsing
    """

    # Pattern to find year indicators in headers
    YEAR_PATTERN = re.compile(r'gültig ab 01\.01\.(\d{4})')

    # Elements to completely remove
    REMOVE_TAGS = [
        'head', 'style', 'script', 'noscript', 'header', 'footer',
        'nav', 'aside', 'form', 'button', 'input', 'iframe',
        'svg', 'meta', 'link'
    ]

    # Attributes to remove from remaining elements
    REMOVE_ATTRS = [
        'style', 'class', 'id', 'onclick', 'onload', 'data-v-',
        'aria-', 'role', 'tabindex', 'xmlns'
    ]

    def strip_html(self, html: str) -> tuple[str, list[int]]:
        """
        Strip HTML to essential content.

        Args:
            html: Raw HTML content

        Returns:
            Tuple of (stripped_html, years_found)
        """
        soup = BeautifulSoup(html, 'html.parser')

        # Find tables and their associated headers BEFORE removing elements
        essential_content = []
        years_found = set()

        # Look for headers with year patterns and their associated tables
        for header in soup.find_all(['h2', 'h3']):
            header_text = header.get_text()
            year_match = self.YEAR_PATTERN.search(header_text)

            if year_match:
                year = int(year_match.group(1))
                years_found.add(year)

                # Find the next table after this header (can be nested in same parent)
                table = self._find_next_table(header)
                if table:
                    # Clean the table
                    clean_table = self._clean_element(table)
                    clean_header = self._clean_element(header)

                    essential_content.append({
                        'year': year,
                        'header': str(clean_header),
                        'table': str(clean_table)
                    })

        # If no year-specific content found, try to find any tables
        if not essential_content:
            for table in soup.find_all('table'):
                clean_table = self._clean_element(table)
                essential_content.append({
                    'year': None,
                    'header': '',
                    'table': str(clean_table)
                })

        # Build minimal HTML
        stripped_html = self._build_minimal_html(essential_content)

        return stripped_html, sorted(years_found)

    def strip_and_split(
        self,
        html_content: str,
        output_dir: Path,
        slug: str,
        data_type: str
    ) -> list[tuple[int, Path]]:
        """
        Strip HTML and split into year-specific files.

        Args:
            html_content: Raw HTML content
            output_dir: Directory to save files
            slug: DNO slug for filename
            data_type: Data type (hlzf, netzentgelte)

        Returns:
            List of (year, file_path) tuples for created files
        """
        soup = BeautifulSoup(html_content, 'html.parser')

        # Find year-specific content BEFORE removing elements
        year_content: dict[int, list[dict[str, Any]]] = {}

        for header in soup.find_all(['h2', 'h3']):
            header_text = header.get_text()
            year_match = self.YEAR_PATTERN.search(header_text)

            if year_match:
                year = int(year_match.group(1))
                table = self._find_next_table(header)

                if table:
                    if year not in year_content:
                        year_content[year] = []

                    year_content[year].append({
                        'header': str(self._clean_element(header)),
                        'table': str(self._clean_element(table))
                    })

        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save year-specific files
        created_files = []

        for year, content_list in year_content.items():
            file_content = self._build_year_html(year, content_list)
            file_path = output_dir / f"{slug}-{data_type}-{year}.html"
            file_path.write_text(file_content, encoding='utf-8')
            created_files.append((year, file_path))

        return created_files

    def _find_next_table(self, header: Tag) -> Tag | None:
        """Find the next table element after a header.

        Uses find_next() to handle cases where the table is nested
        within a sibling div (e.g., accordion structures).
        """
        # Use find_next() which searches descendants too, not just siblings
        next_elem = header.find_next()

        while next_elem:
            # Found a table
            if next_elem.name == 'table':
                return next_elem

            # Check if it's a wrapper div containing a table
            if next_elem.name == 'div':
                table = next_elem.find('table')
                if table:
                    return table

            # Stop if we hit the next year header
            if next_elem.name in ['h2', 'h3']:
                text = next_elem.get_text()
                if self.YEAR_PATTERN.search(text):
                    break

            next_elem = next_elem.find_next()

        return None

    def _clean_element(self, element: Tag) -> Tag:
        """Remove unnecessary attributes from an element and its children."""
        # Create a copy to avoid modifying original
        element = BeautifulSoup(str(element), 'html.parser').find(element.name)

        if element is None:
            return Tag(name='div')

        for tag in element.find_all(True):
            # Remove attributes that match patterns
            attrs_to_remove = []
            for attr in tag.attrs:
                if any(attr.startswith(pattern.rstrip('-')) for pattern in self.REMOVE_ATTRS) or attr in ['style', 'class', 'id', 'onclick', 'onload']:
                    attrs_to_remove.append(attr)

            for attr in attrs_to_remove:
                del tag[attr]

            # Remove empty class attributes
            if 'class' in tag.attrs and not tag['class']:
                del tag['class']

        return element

    def _build_minimal_html(self, content_list: list[dict]) -> str:
        """Build minimal HTML from extracted content."""
        parts = ['<!DOCTYPE html>', '<html>', '<body>']

        for item in content_list:
            if item.get('header'):
                parts.append(item['header'])
            parts.append(item['table'])

        parts.extend(['</body>', '</html>'])
        return '\n'.join(parts)

    def _build_year_html(self, year: int, content_list: list[dict]) -> str:
        """Build year-specific HTML file."""
        parts = [
            '<!DOCTYPE html>',
            '<html>',
            '<head>',
            '<meta charset="utf-8">',
            f'<title>Data for {year}</title>',
            '</head>',
            '<body>',
        ]

        for item in content_list:
            if item.get('header'):
                parts.append(item['header'])
            parts.append(item['table'])

        parts.extend(['</body>', '</html>'])
        return '\n'.join(parts)


def get_file_size_kb(path: Path) -> float:
    """Get file size in KB."""
    return path.stat().st_size / 1024
