"""
Discovery Module - Manager.

Orchestrates discovery strategies:
1. Try sitemap discovery first (fast, low impact)
2. For HLZF, also check HTML pages for embedded tables
3. Fall back to BFS if sitemap unavailable

Uses stored sitemap_urls from DNO record when available.
"""

import httpx
import structlog

from app.services.discovery.base import (
    DiscoveredDocument,
    DiscoveryResult,
    DiscoveryStrategy,
    FileType,
)
from app.services.discovery.sitemap import discover_via_sitemap
from app.services.discovery.scorer import score_html_for_data

logger = structlog.get_logger()


# URL patterns where HLZF data is commonly found as HTML tables
HLZF_HTML_PATTERNS = [
    "/netzentgelte-strom",
    "/netzentgelte",
    "/strom/netzentgelte", 
    "/de/netzentgelte",
    "/netzzugang/netzentgelte",
]


class DiscoveryManager:
    """
    Manages data discovery for a DNO.
    
    Orchestrates multiple discovery strategies and returns
    the best candidates for download.
    """
    
    def __init__(
        self,
        client: httpx.AsyncClient,
        request_delay: float = 0.3,
    ):
        self.client = client
        self.request_delay = request_delay
        self.log = logger.bind(component="DiscoveryManager")
    
    async def discover(
        self,
        base_url: str,
        data_type: str,
        target_year: int | None = None,
        sitemap_urls: list[str] | None = None,
        max_candidates: int = 20,
    ) -> DiscoveryResult:
        """
        Discover data files for a DNO.
        
        Strategy:
        1. Try sitemap discovery (uses stored sitemap_urls if available)
        2. For HLZF, also scan HTML pages for embedded tables
        3. Fall back to BFS if no sitemap
        
        Args:
            base_url: DNO website URL
            data_type: "netzentgelte" or "hlzf"
            target_year: Optional target year
            sitemap_urls: Pre-stored sitemap URLs from DNO record
            max_candidates: Max candidates to return
        
        Returns:
            DiscoveryResult with scored candidates
        """
        self.log.info(
            "Starting discovery",
            base_url=base_url[:40],
            data_type=data_type,
            target_year=target_year,
        )
        
        result = DiscoveryResult(
            start_url=base_url,
            data_type=data_type,
            target_year=target_year,
            strategy=DiscoveryStrategy.SITEMAP,
        )
        
        # Strategy 1: Sitemap discovery
        sitemap_result = await discover_via_sitemap(
            client=self.client,
            base_url=base_url,
            data_type=data_type,
            target_year=target_year,
            max_candidates=max_candidates,
        )
        
        result.documents.extend(sitemap_result.documents)
        result.sitemap_urls_checked = sitemap_result.sitemap_urls_checked
        result.errors.extend(sitemap_result.errors)
        
        # Strategy 2: For HLZF, also check HTML pages for embedded tables
        if data_type == "hlzf" and sitemap_result.documents:
            # Check if any top results are HLZF-specific
            hlzf_keywords = ["hlzf", "hochlast", "zeitfenster"]
            has_hlzf_specific = any(
                any(kw in doc.url.lower() for kw in hlzf_keywords)
                for doc in sitemap_result.documents[:10]
            )
            
            if not has_hlzf_specific:
                self.log.info("No HLZF-specific files in sitemap, checking HTML pages")
                await self._scan_html_for_hlzf(base_url, target_year, result)
        
        # Sort all results by score
        result.documents.sort(key=lambda d: d.score, reverse=True)
        
        # Limit to max_candidates
        result.documents = result.documents[:max_candidates]
        
        self.log.info(
            "Discovery complete",
            strategy=result.strategy.value,
            candidates=len(result.documents),
            top_score=result.documents[0].score if result.documents else 0,
        )
        
        return result
    
    async def _scan_html_for_hlzf(
        self,
        base_url: str,
        target_year: int | None,
        result: DiscoveryResult,
    ):
        """
        Scan common HTML page patterns for embedded HLZF tables.
        
        Many DNOs embed HLZF data directly in HTML tables rather than PDFs.
        """
        from urllib.parse import urlparse
        
        parsed = urlparse(base_url)
        site_base = f"{parsed.scheme}://{parsed.netloc}"
        
        for path in HLZF_HTML_PATTERNS:
            url = site_base + path
            
            try:
                response = await self.client.get(url, timeout=10.0)
                if response.status_code != 200:
                    continue
                
                # Check for embedded data tables
                html_score, years_found = score_html_for_data(
                    response.text, "hlzf", target_year
                )
                
                if html_score > 30:
                    has_target_year = target_year in years_found if target_year else False
                    
                    result.documents.append(DiscoveredDocument(
                        url=url,
                        score=html_score + 50,  # Bonus for confirmed data
                        file_type=FileType.HTML,
                        found_on_page="(html scan)",
                        keywords_found=["hlzf", "strom"],
                        has_target_year=has_target_year,
                        is_html_data=True,
                        years_in_page=years_found,
                    ))
                    
                    self.log.info(
                        "Found HLZF HTML data",
                        url=url,
                        years=years_found,
                        score=html_score + 50,
                    )
                    
            except Exception as e:
                self.log.debug("Error checking HTML page", url=url[:50], error=str(e))
