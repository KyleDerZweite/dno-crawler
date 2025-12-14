"""
Services layer for DNO Crawler business logic.

SERVICES:
- vnb_digital: VNB Digital GraphQL API client for DNO lookup (address/coordinates → DNO)
- dno_resolver: Address → DNO caching layer (check/save mappings)
- search_engine: DDGS-based web search for finding PDF URLs
- pdf_downloader: PDF download and validation
- extraction/pdf_extractor: Regex-based PDF data extraction
- extraction/html_extractor: HTML table parsing for website data
- extraction/llm_extractor: LLM-based fallback for PDF extraction (Netzentgelte, HLZF)

ARCHITECTURE:
1. DNO Resolution: VNBDigitalClient → address/coords → DNO name
2. PDF Discovery: SearchEngine (DDGS) → find Netzentgelte/HLZF PDFs
3. PDF Processing: PDFDownloader → pdf_extractor (regex) + llm_extractor (AI fallback)
4. Website Scraping: html_extractor for tables when PDFs unavailable
"""
