"""
SearchAgent: Synchronous, single-threaded agent for DNO discovery.

Designed to be rate-limit friendly with explicit delays between requests.
Uses ARQ queue with max_jobs=1 for sequential processing.
"""

import time
import json
import re
from pathlib import Path
from typing import Optional, Any

import httpx
import pdfplumber
import structlog
from ddgs import DDGS
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.core.config import settings

logger = structlog.get_logger()


class SearchAgent:
    """
    Synchronous, blocking search agent with fixed rate limiting.
    
    Entry Points:
        1. resolve_dno_from_address() - Address → DNO → PDF
        2. process_dno_batch() - Direct DNO list → PDF
    
    Job Tracking:
        Set job_id via set_job_id() to enable real-time progress updates
        for the frontend Timeline UI.
    """
    
    def __init__(self, db_session: Optional[Session] = None):
        """
        Initialize the SearchAgent.
        
        Args:
            db_session: Optional database session for caching and job tracking
        """
        self.db = db_session
        self.job_id: Optional[str] = None  # For progress tracking
        self.ddgs = DDGS(timeout=settings.ddgs_timeout)
        self.log = logger.bind(component="SearchAgent")
    
    def set_job_id(self, job_id: str) -> None:
        """Set job ID for progress tracking in the frontend Timeline UI."""
        self.job_id = job_id
        self.log = self.log.bind(job_id=job_id)
    
    def _report_step(
        self, 
        label: str, 
        status: str, 
        detail: str = ""
    ) -> None:
        """
        Update job progress in DB for frontend polling.
        
        Args:
            label: Step name (e.g., "Checking Cache", "Downloading PDF")
            status: "running", "done", or "failed"
            detail: Optional detail message (e.g., "Cache hit", "Found ZIP: 50667")
        """
        if not self.job_id or not self.db:
            return
        
        try:
            from datetime import datetime
            from app.db.models import SearchJobModel
            
            job = self.db.execute(
                select(SearchJobModel).where(SearchJobModel.id == self.job_id)
            ).scalar_one_or_none()
            
            if not job:
                self.log.warning("Job not found for progress update", job_id=self.job_id)
                return
            
            now = datetime.now().isoformat()
            
            if status == "running":
                # Starting a new step
                step_num = len(job.steps_history) + 1
                new_step = {
                    "step": step_num,
                    "label": label,
                    "status": status,
                    "detail": detail,
                    "started_at": now,
                }
                # Create a new list to ensure SQLAlchemy detects the change
                job.steps_history = [*job.steps_history, new_step]
                job.current_step = label
                job.status = "running"  # Ensure main status is running
            else:
                # Completing/failing the current step
                if job.steps_history:
                    updated_history = list(job.steps_history)
                    updated_history[-1] = {
                        **updated_history[-1],
                        "status": status,
                        "detail": detail,
                        "completed_at": now,
                    }
                    job.steps_history = updated_history
                
                # Sync main job status on failure
                if status == "failed":
                    job.status = "failed"
                    job.error_message = detail
            
            self.db.commit()
            self.log.debug("Step reported", label=label, status=status)
            
        except Exception as e:
            self.log.error("Failed to report step", error=str(e))
            try:
                self.db.rollback()
            except:
                pass
    
    # =========================================================================
    # Entry Point 1: Address Resolution
    # =========================================================================
    
    def resolve_dno_from_address(
        self, 
        zip_code: str, 
        city: str, 
        street: str
    ) -> Optional[str]:
        """
        Determine the DNO name from an address.
        
        Blocking call. Enforces rate limit before search.
        
        Args:
            zip_code: German postal code (PLZ)
            city: City name
            street: Street name
            
        Returns:
            DNO name if found, None otherwise
        """
        log = self.log.bind(zip_code=zip_code, city=city)
        
        # 1. Normalize & Check Cache (Fast)
        self._report_step("Checking Cache", "running", f"Looking for {zip_code}")
        norm_street = self._normalize_street(street)
        cached = self._check_cache(zip_code, norm_street)
        if cached:
            self._report_step("Checking Cache", "done", f"Cache hit: {cached}")
            log.info("Cache hit", dno=cached)
            return cached
        self._report_step("Checking Cache", "done", "Miss (no cached result)")
        
        # 2. Prepare Query
        query = f"Netzbetreiber Strom {zip_code} {city} {street}"
        log.info("Searching external", query=query)
        
        # 3. Search with Hard Rate Limit
        self._report_step("External Search", "running", "Querying DuckDuckGo...")
        results = self._safe_search(query)
        
        if not results:
            self._report_step("External Search", "failed", "No search results found")
            log.warning("No search results found")
            return None
        self._report_step("External Search", "done", f"Found {len(results)} results")
        
        # 4. LLM Extraction (Ministral)
        self._report_step("Analyzing Results", "running", "AI extracting DNO name...")
        dno_name = self._llm_extract_dno_name(results, zip_code)
        
        if dno_name:
            self._save_to_cache(zip_code, norm_street, dno_name)
            self._report_step("Analyzing Results", "done", f"Found: {dno_name}")
            log.info("DNO resolved", dno=dno_name)
            return dno_name
        
        self._report_step("Analyzing Results", "failed", "Could not identify DNO")
        log.warning("Could not extract DNO from results")
        return None
    
    # =========================================================================
    # Entry Point 2: Batch Processing
    # =========================================================================
    
    def process_dno_batch(
        self, 
        dno_names: list[str], 
        year: int = 2025
    ) -> list[dict]:
        """
        Process a list of DNO names directly.
        
        Useful for 'Batch Search' feature. Enforces delays between DNOs.
        
        Args:
            dno_names: List of DNO names to process
            year: Year to fetch data for
            
        Returns:
            List of result dictionaries
        """
        results = []
        self.log.info("Starting batch processing", count=len(dno_names))
        
        for i, dno in enumerate(dno_names):
            self.log.info(f"Processing DNO {i+1}/{len(dno_names)}", dno=dno)
            
            try:
                result = self.find_and_process_pdf(dno, year)
                results.append(result)
            except Exception as e:
                self.log.error("Failed to process DNO", dno=dno, error=str(e))
                results.append({
                    "dno": dno, 
                    "status": "error", 
                    "message": str(e)
                })
            
            # Sleep between DNOs (except after last one)
            if i < len(dno_names) - 1:
                self._sleep(settings.ddgs_batch_delay_seconds, "batch delay")
        
        return results
    
    # =========================================================================
    # Core Logic: PDF Discovery & Extraction
    # =========================================================================
    
    def find_and_process_pdf(self, dno_name: str, year: int) -> dict:
        """
        Core logic: DNO name → Find PDF → Extract Data.
        
        Args:
            dno_name: Name of the DNO
            year: Year to find data for
            
        Returns:
            Dictionary with extracted data or error info
        """
        log = self.log.bind(dno=dno_name, year=year)
        log.info("Finding and processing PDF")
        
        # 1. First check known PDF URLs from pdf_extractor
        self._report_step("Finding PDF", "running", f"Checking known URLs for {dno_name}...")
        from app.crawler.pdf_extractor import find_pdf_url_for_dno
        known_url = find_pdf_url_for_dno(dno_name, year, "netzentgelte")
        
        if known_url:
            log.info("Found known PDF URL", url=known_url)
            self._report_step("Finding PDF", "done", "Known URL found")
            
            self._report_step("Downloading PDF", "running", "Fetching document...")
            pdf_path = self._download_pdf(known_url, dno_name, year)
            if pdf_path:
                self._report_step("Downloading PDF", "done", "Download complete")
                
                self._report_step("Extracting Data", "running", "Processing PDF...")
                data = self._smart_extract(pdf_path, dno_name, year)
                if data:
                    self._report_step("Extracting Data", "done", f"Extracted {len(data)} records")
                    log.info("Successfully extracted from known URL", records=len(data))
                    return {
                        "dno": dno_name,
                        "year": year,
                        "status": "success",
                        "source_url": known_url,
                        "source_type": "known_url",
                        "records": data,
                    }
        
        # 2. Multi-strategy search queries
        self._report_step("Searching Web", "running", "Trying multiple search strategies...")
        strategies = [
            f'"{dno_name}" Preisblatt Strom {year} filetype:pdf',
            f'"{dno_name}" Netznutzungsentgelte {year} filetype:pdf',
            f'"{dno_name}" Netzentgelte {year} filetype:pdf',
            f'"{dno_name}" vorläufiges Preisblatt {year} filetype:pdf',
        ]
        
        for i, strategy in enumerate(strategies):
            log.info("Trying search strategy", query=strategy)
            results = self._safe_search(strategy, max_results=3)
            
            for result in results:
                url = result.get('href', '')
                if not url.endswith('.pdf'):
                    continue
                
                log.info("Found PDF URL", url=url)
                self._report_step("Searching Web", "done", f"Found PDF (strategy {i+1})")
                
                # Download PDF
                self._report_step("Downloading PDF", "running", "Fetching document...")
                pdf_path = self._download_pdf(url, dno_name, year)
                if not pdf_path:
                    self._report_step("Downloading PDF", "failed", "Download failed, trying next...")
                    continue
                self._report_step("Downloading PDF", "done", "Download complete")
                
                # Validate PDF ("The Glance")
                self._report_step("Validating PDF", "running", "Checking document contents...")
                if not self._validate_pdf_content(pdf_path, dno_name, year):
                    self._report_step("Validating PDF", "failed", "Wrong document, trying next...")
                    log.warning("PDF validation failed", url=url)
                    continue
                self._report_step("Validating PDF", "done", "Document verified")
                
                # Extract data (hybrid: regex first, LLM fallback)
                self._report_step("Extracting Data", "running", "Processing PDF...")
                data = self._smart_extract(pdf_path, dno_name, year)
                if data:
                    self._report_step("Extracting Data", "done", f"Extracted {len(data)} records")
                    log.info("Successfully extracted data", records=len(data))
                    return {
                        "dno": dno_name,
                        "year": year,
                        "status": "success",
                        "source_url": url,
                        "source_type": "ddgs_search",
                        "records": data,
                    }
        
        self._report_step("Searching Web", "failed", "No valid PDF found")
        log.warning("No valid PDF found")
        return {
            "dno": dno_name,
            "year": year,
            "status": "not_found",
            "message": "No valid PDF found with any search strategy",
        }
    
    # =========================================================================
    # Hybrid Extraction
    # =========================================================================
    
    def _smart_extract(
        self, 
        pdf_path: Path, 
        dno_name: str, 
        year: int
    ) -> list[dict]:
        """
        Hybrid extraction: Fast regex path → LLM fallback.
        
        Uses the proven extraction functions from pdf_extractor.py first,
        then falls back to LLM if regex fails.
        """
        log = self.log.bind(pdf_path=str(pdf_path))
        
        # Try regex extraction first (fast) - using existing proven code
        try:
            from app.crawler.pdf_extractor import extract_netzentgelte_from_pdf
            data = extract_netzentgelte_from_pdf(pdf_path)
            if data:
                log.info("Regex extraction succeeded", records=len(data))
                return data
        except Exception as e:
            log.warning("Regex extraction failed", error=str(e))
        
        # Fallback: LLM extraction (slow but smart)
        log.info("Falling back to LLM extraction")
        return self._llm_extract_table(pdf_path, dno_name, year)
    
    def extract_hlzf(self, dno_name: str, year: int) -> dict:
        """
        Extract HLZF (Hochlastzeitfenster) data for a DNO.
        
        Uses similar flow: known URL → search → download → extract.
        """
        log = self.log.bind(dno=dno_name, year=year, data_type="hlzf")
        log.info("Finding and processing HLZF PDF")
        
        # Check known PDFs first
        from app.crawler.pdf_extractor import find_pdf_url_for_dno, extract_hlzf_from_pdf
        known_url = find_pdf_url_for_dno(dno_name, year, "regelungen")
        
        if known_url:
            log.info("Found known Regelungen URL", url=known_url)
            pdf_path = self._download_pdf(known_url, dno_name, year, pdf_type="regelungen")
            if pdf_path:
                try:
                    data = extract_hlzf_from_pdf(pdf_path)
                    if data:
                        log.info("Successfully extracted HLZF", records=len(data))
                        return {
                            "dno": dno_name,
                            "year": year,
                            "status": "success",
                            "source_url": known_url,
                            "records": data,
                        }
                except Exception as e:
                    log.error("HLZF extraction failed", error=str(e))
        
        # Search for Regelungen PDF
        strategies = [
            f'"{dno_name}" Regelungen Strom {year} filetype:pdf',
            f'"{dno_name}" Hochlastzeitfenster {year} filetype:pdf',
            f'"{dno_name}" Regelungen Netznutzung {year} filetype:pdf',
        ]
        
        for strategy in strategies:
            log.info("Trying HLZF search strategy", query=strategy)
            results = self._safe_search(strategy, max_results=3)
            
            for result in results:
                url = result.get('href', '')
                if not url.endswith('.pdf'):
                    continue
                
                pdf_path = self._download_pdf(url, dno_name, year, pdf_type="regelungen")
                if not pdf_path:
                    continue
                
                try:
                    data = extract_hlzf_from_pdf(pdf_path)
                    if data:
                        log.info("Successfully extracted HLZF", records=len(data))
                        return {
                            "dno": dno_name,
                            "year": year,
                            "status": "success",
                            "source_url": url,
                            "records": data,
                        }
                except Exception as e:
                    log.warning("HLZF extraction failed for URL", url=url, error=str(e))
        
        return {
            "dno": dno_name,
            "year": year,
            "status": "not_found",
            "message": "No valid HLZF data found",
        }
    
    # =========================================================================
    # Search & Rate Limiting
    # =========================================================================
    
    def _safe_search(self, query: str, max_results: int = 4) -> list[dict]:
        """
        Wrapper that enforces hard-coded delay BEFORE every search.
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
    
    def _sleep(self, seconds: int, reason: str = ""):
        """Blocking sleep with logging."""
        self.log.debug(f"Sleeping {seconds}s", reason=reason)
        time.sleep(seconds)
    
    # =========================================================================
    # Cache Helpers (Implemented)
    # =========================================================================
    
    def _normalize_street(self, street: str) -> str:
        """Normalize street name for cache key."""
        return (
            street.lower()
            .replace("straße", "str")
            .replace("strasse", "str")
            .replace("str.", "str")
            .replace(" ", "")
        )
    
    def _check_cache(self, zip_code: str, norm_street: str) -> Optional[str]:
        """Check DB cache for existing DNO mapping."""
        if not self.db:
            return None
        
        try:
            from app.db.models import DNOAddressCacheModel
            
            query = select(DNOAddressCacheModel).where(
                and_(
                    DNOAddressCacheModel.zip_code == zip_code,
                    DNOAddressCacheModel.street_name == norm_street
                )
            )
            result = self.db.execute(query)
            cache_entry = result.scalar_one_or_none()
            
            if cache_entry:
                # Update hit count
                cache_entry.hit_count += 1
                self.db.commit()
                return cache_entry.dno_name
                
        except Exception as e:
            self.log.warning("Cache lookup failed", error=str(e))
        
        return None
    
    def _save_to_cache(
        self, 
        zip_code: str, 
        norm_street: str, 
        dno_name: str,
        confidence: float = 0.9
    ) -> None:
        """Save DNO mapping to cache."""
        if not self.db:
            return
        
        try:
            from app.db.models import DNOAddressCacheModel
            
            # Check if entry already exists
            existing = self.db.execute(
                select(DNOAddressCacheModel).where(
                    and_(
                        DNOAddressCacheModel.zip_code == zip_code,
                        DNOAddressCacheModel.street_name == norm_street
                    )
                )
            ).scalar_one_or_none()
            
            if existing:
                # Update existing entry
                existing.dno_name = dno_name
                existing.confidence = confidence
                existing.hit_count += 1
            else:
                # Create new entry
                cache_entry = DNOAddressCacheModel(
                    zip_code=zip_code,
                    street_name=norm_street,
                    dno_name=dno_name,
                    confidence=confidence,
                    source="ddgs",
                    hit_count=1,
                )
                self.db.add(cache_entry)
            
            self.db.commit()
            self.log.info("Saved to cache", zip=zip_code, dno=dno_name)
            
        except Exception as e:
            self.log.warning("Cache save failed", error=str(e))
            try:
                self.db.rollback()
            except:
                pass
    
    # =========================================================================
    # PDF Helpers
    # =========================================================================
    
    def _download_pdf(
        self, 
        url: str, 
        dno_name: str, 
        year: int,
        pdf_type: str = "netzentgelte"
    ) -> Optional[Path]:
        """Download PDF to local storage."""
        log = self.log.bind(url=url)
        
        # Create safe filename
        safe_name = re.sub(r'[^a-zA-Z0-9]', '-', dno_name.lower())
        downloads_dir = Path(settings.downloads_path) / safe_name
        downloads_dir.mkdir(parents=True, exist_ok=True)
        
        pdf_path = downloads_dir / f"{pdf_type}-{year}.pdf"
        
        try:
            with httpx.Client(follow_redirects=True, timeout=60.0) as client:
                response = client.get(url)
                response.raise_for_status()
                
                # Verify it's actually a PDF
                if not response.content.startswith(b'%PDF'):
                    log.warning("Downloaded file is not a valid PDF")
                    return None
                
                pdf_path.write_bytes(response.content)
                log.info("PDF downloaded", path=str(pdf_path), size=len(response.content))
                return pdf_path
                
        except Exception as e:
            log.error("PDF download failed", error=str(e))
            return None
    
    def _validate_pdf_content(
        self, 
        pdf_path: Path, 
        dno_name: str, 
        year: int
    ) -> bool:
        """
        "The Glance" - Read page 1 to verify this is the correct document.
        Uses LLM for smart validation.
        """
        try:
            with pdfplumber.open(pdf_path) as pdf:
                first_page_text = pdf.pages[0].extract_text() or ""
            
            # Quick keyword check
            if str(year) not in first_page_text:
                self.log.debug("Year not found in PDF")
                return False
            
            # Check for Netzentgelte keywords
            keywords = ["netzentgelt", "leistungspreis", "arbeitspreis", "preisblatt"]
            if not any(kw in first_page_text.lower() for kw in keywords):
                self.log.debug("No Netzentgelte keywords found")
                return False
            
            # LLM verification (optional - can be skipped if keywords match)
            prompt = f"""Is this text from a German electricity price sheet (Preisblatt/Netzentgelte) 
for the company '{dno_name}'? Respond with only YES or NO.

Text:
{first_page_text[:1500]}"""
            
            response = self._call_ollama(prompt, model=settings.ollama_fast_model)
            return "YES" in response.upper() if response else True  # Default to True if LLM fails
            
        except Exception as e:
            self.log.error("PDF validation error", error=str(e))
            return False
    
    # =========================================================================
    # LLM Helpers
    # =========================================================================
    
    def _llm_extract_dno_name(
        self, 
        search_results: list[dict], 
        zip_code: str
    ) -> Optional[str]:
        """Use LLM to analyze search snippets and identify the DNO."""
        if not search_results:
            return None
        
        snippets = "\n".join([
            f"- {r.get('title', '')}: {r.get('body', '')}" 
            for r in search_results
        ])
        
        prompt = f"""Analyze these search results for the German Grid Operator (Netzbetreiber) for ZIP {zip_code}.
Return ONLY the company name, nothing else. If unsure, return "UNKNOWN".

Results:
{snippets}"""
        
        response = self._call_ollama(prompt, model=settings.ollama_fast_model)
        
        if response and response.strip() != "UNKNOWN":
            # Clean up the response
            name = response.strip().strip('"').strip("'")
            # Remove any thinking or extra text
            if "\n" in name:
                name = name.split("\n")[0]
            # Basic validation - should be a reasonable company name
            if len(name) > 2 and len(name) < 100:
                return name
        
        return None
    
    def _llm_extract_table(
        self, 
        pdf_path: Path, 
        dno_name: str, 
        year: int
    ) -> list[dict]:
        """Use LLM to extract Netzentgelte table from PDF."""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                # Get text from first 5 pages
                text = "\n".join([
                    p.extract_text() or "" 
                    for p in pdf.pages[:5]
                ])
            
            prompt = f"""Extract the Netzentgelte (network charges) from this text for {dno_name} {year}.

Look for a table with voltage levels and prices:
- Voltage levels: Hochspannung, Umspannung HS/MS, Mittelspannung, Umspannung MS/NS, Niederspannung
- Price columns: Leistungspreis (€/kW), Arbeitspreis (ct/kWh)
- Some tables have 4 price columns: LP <2500h, AP <2500h, LP >=2500h, AP >=2500h

Return ONLY valid JSON, no explanation:
{{"records": [{{"voltage_level": "...", "leistung": ..., "arbeit": ..., "leistung_unter_2500h": ..., "arbeit_unter_2500h": ...}}]}}

Text:
{text[:4000]}"""
            
            response = self._call_ollama(prompt, model=settings.ollama_model)
            
            if response:
                # Try to parse JSON from response
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    records = data.get("records", [])
                    self.log.info("LLM extraction succeeded", records=len(records))
                    return records
                    
        except json.JSONDecodeError as e:
            self.log.warning("Failed to parse LLM JSON response", error=str(e))
        except Exception as e:
            self.log.error("LLM table extraction failed", error=str(e))
        
        return []
    
    def _call_ollama(
        self, 
        prompt: str, 
        model: Optional[str] = None
    ) -> Optional[str]:
        """Call Ollama API synchronously."""
        model = model or settings.ollama_model
        
        try:
            with httpx.Client(timeout=settings.ollama_timeout) as client:
                response = client.post(
                    f"{settings.ollama_url}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": False},
                )
                
                if response.status_code == 200:
                    return response.json().get("response", "")
                else:
                    self.log.warning("Ollama request failed", status=response.status_code)
                    
        except Exception as e:
            self.log.error("Ollama call failed", error=str(e))
        
        return None

