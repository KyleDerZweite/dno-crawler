"""
Discovery Module - Unified Scoring.

Single scoring algorithm used by all discovery strategies.
Ensures consistent ranking across sitemap and BFS discovery.
"""

from app.services.web_crawler import get_keywords_for_data_type, NEGATIVE_KEYWORDS
from app.services.discovery.base import FileType


# File type scoring bonuses
FILE_TYPE_SCORES = {
    FileType.PDF: 20,
    FileType.XLSX: 15,
    FileType.XLS: 15,
    FileType.DOC: 5,
    FileType.HTML: 0,  # HTML pages scored by content, not extension
}


def detect_file_type(url: str) -> FileType:
    """Detect file type from URL."""
    url_lower = url.lower()
    
    if ".pdf" in url_lower or ".pdfx" in url_lower:
        return FileType.PDF
    elif ".xlsx" in url_lower:
        return FileType.XLSX
    elif ".xls" in url_lower:
        return FileType.XLS
    elif ".docx" in url_lower or ".doc" in url_lower:
        return FileType.DOC
    
    return FileType.UNKNOWN


def score_url(
    url: str,
    data_type: str,
    target_year: int | None = None,
    link_text: str = "",
) -> tuple[float, list[str], bool]:
    """
    Score a URL for relevance to target data type.
    
    Args:
        url: URL to score
        data_type: "netzentgelte" or "hlzf"
        target_year: Optional target year
        link_text: Optional link anchor text
    
    Returns:
        (score, keywords_found, has_target_year)
    """
    url_lower = url.lower()
    link_text_lower = link_text.lower() if link_text else ""
    
    score = 0.0
    keywords_found = []
    has_year = False
    
    # File type bonus
    file_type = detect_file_type(url)
    score += FILE_TYPE_SCORES.get(file_type, 0)
    
    # Positive keywords
    keywords = get_keywords_for_data_type(data_type)
    for kw in keywords:
        kw_lower = kw.lower()
        if kw_lower in url_lower:
            score += 15
            if kw not in keywords_found:
                keywords_found.append(kw)
        if kw_lower in link_text_lower:
            score += 5
            if kw not in keywords_found:
                keywords_found.append(kw)
    
    # Negative keywords
    neg_keywords = NEGATIVE_KEYWORDS.get(data_type, [])
    for neg_kw, penalty in neg_keywords:
        if neg_kw.lower() in url_lower or neg_kw.lower() in link_text_lower:
            score += penalty  # penalty is already negative
    
    # Target year bonus
    if target_year:
        year_str = str(target_year)
        if year_str in url:
            score += 25
            has_year = True
        elif year_str in link_text:
            score += 10
            has_year = True
    
    return score, keywords_found, has_year


def score_html_for_data(
    html_content: str,
    data_type: str,
    target_year: int | None = None,
) -> tuple[float, list[int]]:
    """
    Score HTML page for embedded data tables.
    
    Uses html_content_detector for actual detection.
    
    Returns:
        (score, years_found)
    """
    from app.services.html_content_detector import score_html_page_for_data
    
    score, result = score_html_page_for_data(html_content, data_type, target_year)
    
    return score, result.years_found
