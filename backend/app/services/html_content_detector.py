"""
HTML Content Detector for BFS Discovery.

Lightweight detection of embedded data in HTML pages:
- Tables with year-specific headers
- Data tables matching data type keywords (HLZF, Netzentgelte)

Used during crawling to score pages that contain actual data,
not just links to PDFs.
"""

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup


@dataclass
class EmbeddedDataResult:
    """Result of HTML content analysis."""

    has_data_table: bool = False
    years_found: list[int] = None
    table_count: int = 0
    data_type_confidence: float = 0.0
    keywords_found: list[str] = None

    def __post_init__(self):
        self.years_found = self.years_found or []
        self.keywords_found = self.keywords_found or []


# Data type specific patterns
DATA_PATTERNS = {
    "hlzf": {
        "header_keywords": ["hochlast", "zeitfenster", "hlzf", "winter", "sommer"],
        "table_keywords": ["uhr", "winter", "sommer", "01.11", "31.03", "umspannung", "spannung"],
        "year_patterns": [
            r"gültig ab 01\.01\.(\d{4})",
            r"ab (\d{4})",
            r"(\d{4})",
        ],
    },
    "netzentgelte": {
        "header_keywords": [
            "netzentgelt",
            "preisblatt",
            "entgelt",
            "tarif",
            "arbeitspreis",
            "leistungspreis",
        ],
        "table_keywords": [
            "ct/kwh",
            "eur/kw",
            "niederspannung",
            "mittelspannung",
            "hochspannung",
            "netzebene",
        ],
        "year_patterns": [
            r"gültig ab 01\.01\.(\d{4})",
            r"(\d{4})",
        ],
    },
}


def detect_embedded_data(
    html_content: str,
    data_type: str,
    target_year: int | None = None,
) -> EmbeddedDataResult:
    """
    Analyze HTML content for embedded data tables.

    Args:
        html_content: Raw HTML string
        data_type: "hlzf" or "netzentgelte"
        target_year: Optional target year to look for

    Returns:
        EmbeddedDataResult with detection info
    """
    soup = BeautifulSoup(html_content, "lxml")
    result = EmbeddedDataResult()

    patterns = DATA_PATTERNS.get(data_type, DATA_PATTERNS["netzentgelte"])

    # Get page text for keyword search
    page_text = soup.get_text().lower()

    # Check for header keywords
    for kw in patterns["header_keywords"]:
        if kw.lower() in page_text:
            result.keywords_found.append(kw)

    # Find tables
    tables = soup.find_all("table")
    result.table_count = len(tables)

    if not tables:
        return result

    # Analyze tables for data type relevance
    years_found = set()
    data_table_score = 0.0

    for table in tables:
        table_text = table.get_text().lower()

        # Check for table keywords
        table_keyword_count = 0
        for kw in patterns["table_keywords"]:
            if kw.lower() in table_text:
                table_keyword_count += 1

        # If table has multiple relevant keywords, it's likely a data table
        if table_keyword_count >= 2:
            data_table_score += 0.3
            result.has_data_table = True

        # Look for year patterns in headers above the table
        # Check parent and preceding siblings
        parent = table.parent
        if parent:
            # Get text before table in parent
            parent_text = parent.get_text()
            for pattern in patterns["year_patterns"]:
                matches = re.findall(pattern, parent_text, re.IGNORECASE)
                for match in matches:
                    try:
                        year = int(match)
                        if 2020 <= year <= 2030:
                            years_found.add(year)
                    except ValueError:
                        pass

    # Also check headers (h2, h3) near tables
    for header in soup.find_all(["h2", "h3", "h4"]):
        header_text = header.get_text()
        for pattern in patterns["year_patterns"]:
            match = re.search(pattern, header_text, re.IGNORECASE)
            if match:
                try:
                    year = int(match.group(1))
                    if 2020 <= year <= 2030:
                        years_found.add(year)
                except (ValueError, IndexError):
                    pass

    result.years_found = sorted(years_found)

    # Calculate confidence
    confidence = 0.0
    if result.has_data_table:
        confidence += 0.4
    if result.keywords_found:
        confidence += min(len(result.keywords_found) * 0.1, 0.3)
    if target_year and target_year in result.years_found:
        confidence += 0.3
    elif result.years_found:
        confidence += 0.1

    result.data_type_confidence = min(confidence, 1.0)

    return result


def score_html_page_for_data(
    html_content: str,
    data_type: str,
    target_year: int | None = None,
) -> tuple[float, EmbeddedDataResult]:
    """
    Score an HTML page for embedded data relevance.

    HLZF data is commonly in HTML tables, netzentgelte is mostly in PDFs.

    Returns:
        (score_bonus, result) - score to add to page ranking
    """
    result = detect_embedded_data(html_content, data_type, target_year)

    score = 0.0

    # Has data table with relevant keywords
    if result.has_data_table:
        if data_type == "hlzf":
            score += 50  # HLZF is commonly in HTML tables
        else:
            score += 15  # Netzentgelte is mostly in PDFs

    # Matching keywords - more important for HLZF
    keyword_weight = 7 if data_type == "hlzf" else 3
    score += len(result.keywords_found) * keyword_weight

    # Target year found
    if target_year and target_year in result.years_found:
        score += 25

    return score, result
