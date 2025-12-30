"""
Discovery Module for DNO Crawler.

Provides unified discovery services for finding data files on DNO websites.

Main components:
- DiscoveryManager: Orchestrates discovery strategies
- SitemapDiscovery: Fast discovery via sitemap.xml
- Scorer: Unified URL scoring algorithm

Usage:
    from app.services.discovery import DiscoveryManager
    
    async with httpx.AsyncClient() as client:
        manager = DiscoveryManager(client)
        result = await manager.discover(
            base_url="https://www.rheinnetz.de",
            data_type="netzentgelte",
            target_year=2025,
        )
        
        for doc in result.documents[:5]:
            print(f"{doc.score}: {doc.url}")
"""

from app.services.discovery.base import (
    DiscoveredDocument,
    DiscoveryResult,
    DiscoveryStrategy,
    FileType,
)
from app.services.discovery.manager import DiscoveryManager
from app.services.discovery.scorer import score_url, score_html_for_data, detect_file_type
from app.services.discovery.sitemap import discover_via_sitemap

__all__ = [
    # Main manager
    "DiscoveryManager",
    
    # Result types
    "DiscoveredDocument",
    "DiscoveryResult",
    "DiscoveryStrategy",
    "FileType",
    
    # Utilities
    "score_url",
    "score_html_for_data",
    "detect_file_type",
    "discover_via_sitemap",
]
