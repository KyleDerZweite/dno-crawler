"""
Search Engine service for PDF/website discovery via DDGS.

STILL ACTIVE: Used for finding PDF URLs for Netzentgelte/HLZF data.
NOT used for DNO name resolution (that's now handled by VNBDigitalClient).

Functions:
- safe_search(): General web search with rate limiting
- find_pdf_url(): Targeted search for DNO PDF documents
"""

import time
from typing import Optional

import structlog
from ddgs import DDGS

from app.core.config import settings

logger = structlog.get_logger()


class SearchEngine:
    """
    Web search abstraction with rate limiting.
    
    Uses DuckDuckGo Search (DDGS) with configurable delays
    to prevent rate limiting.
    """
    
    def __init__(self):
        """Initialize the search engine."""
        self.ddgs = DDGS(timeout=settings.ddgs_timeout)
        self.log = logger.bind(component="SearchEngine")
    
    def safe_search(self, query: str, max_results: int = 4) -> list[dict]:
        """
        Perform web search with rate limiting.
        
        Enforces a delay BEFORE every search to be rate-limit friendly.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            
        Returns:
            List of search result dictionaries with 'title', 'href', 'body'
        """
        self._sleep(settings.ddgs_request_delay_seconds, "rate limit")
        
        try:
            self.log.info("Executing DDGS search", query=query)
            results = self.ddgs.text(query, max_results=max_results)
            return list(results) if results else []
        except Exception as e:
            self.log.error("DDGS search failed", error=str(e))
            # Check for rate limit errors
            if "429" in str(e) or "418" in str(e) or "rate" in str(e).lower():
                self.log.warning("Rate limit hit! Cooling down...")
                self._sleep(settings.ddgs_rate_limit_cooldown, "rate limit cooldown")
            return []
    
    def find_pdf_url(
        self, 
        dno_name: str, 
        year: int, 
        pdf_type: str = "netzentgelte"
    ) -> Optional[str]:
        """
        Search for PDF URL for a specific DNO.
        
        Tries multiple search strategies to find the PDF.
        
        Args:
            dno_name: Name of the DNO
            year: Year to search for
            pdf_type: Type of PDF ("netzentgelte" or "regelungen")
            
        Returns:
            PDF URL if found, None otherwise
        """
        if pdf_type == "netzentgelte":
            strategies = [
                f'"{dno_name}" Preisblatt Strom {year} filetype:pdf',
                f'"{dno_name}" Netznutzungsentgelte {year} filetype:pdf',
                f'"{dno_name}" Netzentgelte {year} filetype:pdf',
                f'"{dno_name}" vorläufiges Preisblatt {year} filetype:pdf',
            ]
        else:  # regelungen / hlzf
            strategies = [
                f'"{dno_name}" Regelungen Strom {year} filetype:pdf',
                f'"{dno_name}" Hochlastzeitfenster {year} filetype:pdf',
                f'"{dno_name}" Regelungen Netznutzung {year} filetype:pdf',
            ]
        
        for strategy in strategies:
            self.log.info("Trying search strategy", query=strategy)
            results = self.safe_search(strategy, max_results=3)
            
            for result in results:
                url = result.get('href', '')
                if url.endswith('.pdf'):
                    self.log.info("Found PDF URL", url=url)
                    return url
        
        return None
    
    def _sleep(self, seconds: int, reason: str = "") -> None:
        """Blocking sleep with logging."""
        self.log.debug(f"Sleeping {seconds}s", reason=reason)
        time.sleep(seconds)
