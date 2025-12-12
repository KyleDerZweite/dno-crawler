"""
Services layer for DNO Crawler business logic.

ACTIVE SERVICES:
- vnb_digital: VNB Digital GraphQL API client for DNO lookup (address/coordinates → DNO name)
- dno_resolver: Address → DNO name caching layer
- search_engine: DDGS-based web search for finding PDF URLs and DNO websites
- pdf_downloader: PDF download and validation
- extraction/pdf_extractor: Regex-based PDF data extraction
- extraction/html_extractor: HTML table parsing for website data
- extraction/llm_extractor: LLM-based fallback for PDF extraction (Netzentgelte, HLZF)

DEPRECATED FUNCTIONS:
- extraction/llm_extractor.extract_dno_name() - Use vnb_digital.VNBDigitalClient instead

ARCHITECTURE:
1. DNO Resolution: VNBDigitalClient handles address/coordinate → DNO name lookup
2. PDF/Data Discovery: SearchEngine (DDGS) finds PDF URLs for Netzentgelte/HLZF
3. PDF Processing: PDFDownloader + pdf_extractor (regex) + llm_extractor (AI fallback)
4. Website Scraping: html_extractor for website tables when PDFs unavailable
"""
