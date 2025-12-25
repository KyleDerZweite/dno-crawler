"""
Services layer for DNO Crawler business logic.

SERVICES:
- vnb_digital: VNB Digital GraphQL API client for DNO lookup (address/coordinates → DNO)
- dno_resolver: Address → DNO caching layer (check/save mappings)
- web_crawler: BFS web crawler for discovering data sources on DNO websites
- pattern_learner: Cross-DNO URL pattern learning and application
- url_utils: SSRF-safe URL probing, robots.txt compliance, URL normalization
- content_verifier: Pre-download content verification (sniff + keyword analysis)
- pdf_downloader: PDF download and validation
- extraction/pdf_extractor: Regex-based PDF data extraction
- extraction/html_extractor: HTML table parsing for website data
- extraction/ai_extractor: AI-based extraction using OpenAI-compatible APIs

ARCHITECTURE:
1. DNO Resolution: VNBDigitalClient → address/coords → DNO name
2. Data Discovery: WebCrawler (BFS) + PatternLearner → find Netzentgelte/HLZF files
3. PDF Processing: PDFDownloader → pdf_extractor (regex) + llm_extractor (AI fallback)
4. Website Scraping: html_extractor for tables when PDFs unavailable
"""

