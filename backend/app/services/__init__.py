"""
Services layer for DNO Crawler business logic.

MODULES:
- vnb/: VNB Digital API client + skeleton service
- discovery/: Data discovery (sitemap + BFS strategies)
- extraction/: Data extraction (PDF, HTML, AI)

STANDALONE SERVICES:
- web_crawler: BFS web crawler for discovering data sources
- robots_parser: Robots.txt parsing and crawlability detection
- html_content_detector: HTML embedded data detection
- url_utils: URL normalization and validation
- content_verifier: Pre-download content verification
- pdf_downloader: PDF download and validation
- impressum_extractor: Impressum page parsing

ARCHITECTURE:
1. DNO Resolution: vnb.VNBDigitalClient → address/coords → DNO name
2. Skeleton Creation: vnb.skeleton_service → DNO + crawlability info
3. Data Discovery: discovery.DiscoveryManager → sitemap-first + BFS fallback
4. Data Extraction: extraction/pdf_extractor + ai_extractor
"""
