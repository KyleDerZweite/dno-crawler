"""
Discovery Module - Base Data Classes.

Shared types used across discovery strategies.
"""

from dataclasses import dataclass, field
from enum import Enum


class DiscoveryStrategy(str, Enum):
    """How the data was discovered."""
    SITEMAP = "sitemap"      # Found via sitemap.xml
    BFS = "bfs"              # Found via BFS crawl
    HINT_URL = "hint_url"    # Found via previous year URL pattern
    MANUAL = "manual"        # Manually provided URL


class FileType(str, Enum):
    """Detected file types."""
    PDF = "pdf"
    XLSX = "xlsx"
    XLS = "xls"
    HTML = "html"
    DOC = "doc"
    UNKNOWN = "unknown"


@dataclass
class DiscoveredDocument:
    """
    A discovered document (file or HTML page with data).
    
    Represents a candidate data source found during discovery.
    """
    url: str
    score: float = 0.0
    file_type: FileType = FileType.UNKNOWN

    # Discovery context
    found_on_page: str = ""  # URL where this was found, or "(sitemap)"
    link_text: str = ""      # Anchor text if from a link

    # Scoring details
    keywords_found: list[str] = field(default_factory=list)
    has_target_year: bool = False

    # For HTML pages with embedded data
    is_html_data: bool = False
    years_in_page: list[int] = field(default_factory=list)

    # External CDN?
    is_external: bool = False


@dataclass
class DiscoveryResult:
    """
    Result of a discovery operation.
    
    Contains all candidates found, sorted by relevance.
    """
    start_url: str
    data_type: str
    target_year: int | None

    # Strategy used
    strategy: DiscoveryStrategy

    # Results
    documents: list[DiscoveredDocument] = field(default_factory=list)

    # Stats
    pages_crawled: int = 0
    sitemap_urls_checked: int = 0

    # Errors/warnings
    errors: list[str] = field(default_factory=list)

    @property
    def top_document(self) -> DiscoveredDocument | None:
        """Get highest-scoring document."""
        if self.documents:
            return max(self.documents, key=lambda d: d.score)
        return None

    @property
    def pdf_documents(self) -> list[DiscoveredDocument]:
        """Get all PDF documents."""
        return [d for d in self.documents if d.file_type == FileType.PDF]

    @property
    def html_documents(self) -> list[DiscoveredDocument]:
        """Get all HTML pages with embedded data."""
        return [d for d in self.documents if d.is_html_data]
