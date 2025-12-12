"""
Search job handler for the ARQ worker.

This job orchestrates the services layer for search requests.
Supports both legacy crawl jobs and new natural language search with Timeline UI.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

import structlog

from app.db import get_db_session
from app.services.dno_resolver import DNOResolver
from app.services.search_engine import SearchEngine
from app.services.pdf_downloader import PDFDownloader
from app.services.extraction import extract_netzentgelte_from_pdf, extract_hlzf_from_pdf
from app.services.extraction.llm_extractor import LLMExtractor

logger = structlog.get_logger()


async def job_process_search_request(
    ctx: dict, 
    # Structured payload format (from batch search)
    payload: Optional[dict] = None,
    # NL search format
    job_id: Optional[str] = None,
    prompt: Optional[str] = None,
    filters: Optional[dict] = None,
) -> dict:
    """
    ARQ job function for processing search requests.
    
    Runs strictly one at a time due to max_jobs=1 in WorkerSettings.
    
    Supports two modes:
    1. Structured: payload dict with 'type' field (address/dno/coordinates) + job_id
    2. NL Search: job_id + prompt + filters for Timeline UI
    """
    log = logger.bind(job_id=job_id)
    
    # Mode 1: Structured payload from batch search (has job_id and payload with type)
    if job_id is not None and payload is not None:
        payload_type = payload.get("type")
        if payload_type in ("address", "dno", "coordinates"):
            return await _process_structured_search(ctx, job_id, payload, filters or {})
        else:
            log.error("Unknown payload type", payload_type=payload_type)
            return {"status": "error", "message": f"Unknown payload type: {payload_type}"}
    
    # Mode 2: NL search (job_id + prompt)
    if job_id is not None and prompt is not None:
        return await _process_nl_search(ctx, job_id, prompt, filters or {})
    
    return {"status": "error", "message": "Invalid job parameters"}


async def _process_nl_search(
    ctx: dict,
    job_id: str,
    prompt: str,
    filters: dict,
) -> dict:
    """
    Process natural language search with Timeline UI integration.
    
    Updates SearchJobModel in DB for frontend polling.
    Uses new services layer for all operations.
    """
    log = logger.bind(job_id=job_id, prompt=prompt[:50])
    log.info("Processing NL search request")
    
    # Get DB session and update job status
    async with get_db_session() as db:
        from sqlalchemy import select
        from app.db.models import SearchJobModel
        
        # Mark job as running
        result = await db.execute(
            select(SearchJobModel).where(SearchJobModel.id == job_id)
        )
        job = result.scalar_one_or_none()
        
        if not job:
            log.error("Job not found", job_id=job_id)
            return {"status": "error", "message": "Job not found"}
        
        job.status = "running"
        job.started_at = datetime.utcnow()
        await db.commit()
    
    # Process with synchronous services (using sync DB session)
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.core.config import settings
    from app.services.vnb_digital import VNBDigitalClient
    
    # Create sync engine for services
    sync_engine = create_engine(str(settings.database_url).replace("+asyncpg", ""))
    
    with Session(sync_engine) as sync_db:
        # Initialize services
        resolver = DNOResolver(db_session=sync_db)
        search_engine = SearchEngine()
        downloader = PDFDownloader()
        llm_extractor = LLMExtractor()
        vnb_client = VNBDigitalClient(request_delay=1.0)
        
        # Parse filters
        years = filters.get("years", [2024, 2025])
        types = filters.get("types", ["netzentgelte", "hlzf"])
        
        # Step 1: Parse the prompt (simplified - assumes address format)
        _report_step(sync_db, job_id, "Analyzing Input", "running", f"Parsing: {prompt[:50]}...")
        
        # Extract address components using _parse_plz_city
        import re
        
        zip_match = re.search(r'\b(\d{5})\b', prompt)
        zip_code = zip_match.group(1) if zip_match else ""
        
        if zip_code and zip_match:
            after_zip = prompt[zip_match.end():].strip()
            city_match = re.match(r'^([A-Za-zäöüÄÖÜß\s-]+)', after_zip)
            city = city_match.group(1).strip() if city_match else ""
            street = prompt[:zip_match.start()].rstrip(', ').strip()
        else:
            parts = [p.strip() for p in prompt.split(',')]
            if len(parts) >= 2:
                street = parts[0]
                zip_city = parts[1].strip().split()
                zip_code = zip_city[0] if zip_city and zip_city[0].isdigit() else ""
                city = " ".join(zip_city[1:]) if len(zip_city) > 1 else ""
            else:
                street = prompt
                city = ""
        
        if zip_code and city:
            _report_step(sync_db, job_id, "Analyzing Input", "done", f"ZIP={zip_code}, City={city}, Street={street}")
        else:
            _report_step(sync_db, job_id, "Analyzing Input", "done", f"Partial parse: ZIP={zip_code or 'N/A'}, City={city or 'N/A'}")
        
        # Step 2: Resolve DNO - first check cache, then VNB Digital API
        _report_step(sync_db, job_id, "Checking Cache", "running", f"Looking for {zip_code}")
        
        # Check existing address → DNO mapping in database
        norm_street = resolver.normalize_street(street)
        existing_dno = resolver.check_address_mapping(zip_code, norm_street)
        
        if existing_dno:
            dno_name = existing_dno
            _report_step(sync_db, job_id, "Checking Cache", "done", f"Found: {existing_dno}")
        else:
            _report_step(sync_db, job_id, "Checking Cache", "done", "No cached mapping")
            
            # Use VNB Digital API for address lookup
            _report_step(sync_db, job_id, "External Search", "running", "Querying VNB Digital API...")
            
            dno_name = vnb_client.resolve_address_to_dno(prompt)
            
            if dno_name:
                resolver.save_address_mapping(zip_code, norm_street, dno_name)
                _report_step(sync_db, job_id, "External Search", "done", f"Found: {dno_name}")
            else:
                _report_step(sync_db, job_id, "External Search", "failed", "VNB Digital API returned no results")
                await _mark_job_failed(job_id, f"Could not find DNO for: {prompt}")
                return {"status": "not_found", "message": "Could not resolve DNO"}
        
        # Step 3: Process for each year and type
        all_results = {
            "dno_name": dno_name,
            "netzentgelte": {},
            "hlzf": {},
        }
        
        for year in years:
            if "netzentgelte" in types:
                result = _find_and_process_pdf(
                    sync_db, job_id, dno_name, year,
                    search_engine, downloader, llm_extractor
                )
                if result.get("status") == "success":
                    all_results["netzentgelte"][year] = result.get("records", [])
            
            if "hlzf" in types:
                result = _extract_hlzf(
                    sync_db, job_id, dno_name, year,
                    search_engine, downloader, llm_extractor
                )
                if result.get("status") == "success":
                    all_results["hlzf"][year] = result.get("records", [])
        
        # Mark job as completed
        async with get_db_session() as db:
            from sqlalchemy import select
            from app.db.models import SearchJobModel
            
            result = await db.execute(
                select(SearchJobModel).where(SearchJobModel.id == job_id)
            )
            job = result.scalar_one_or_none()
            if job:
                job.status = "completed"
                job.result = all_results
                job.completed_at = datetime.utcnow()
                await db.commit()
        
        log.info("NL search completed", dno=dno_name)
        return {"status": "completed", "dno_name": dno_name}


async def _process_structured_search(
    ctx: dict,
    job_id: str,
    payload: dict,
    filters: dict,
) -> dict:
    """
    Process structured search from batch submission.
    
    Supports three input types:
    - address: street + plz_city → VNB Digital API → DNO
    - dno: direct DNO name → skip to PDF search
    - coordinates: lat/lon → VNB Digital API → DNO
    """
    payload_type = payload.get("type")
    log = logger.bind(job_id=job_id, type=payload_type)
    log.info("Processing structured search")
    
    # Mark job as running
    async with get_db_session() as db:
        from sqlalchemy import select
        from app.db.models import SearchJobModel
        
        result = await db.execute(
            select(SearchJobModel).where(SearchJobModel.id == job_id)
        )
        job = result.scalar_one_or_none()
        
        if not job:
            log.error("Job not found", job_id=job_id)
            return {"status": "error", "message": "Job not found"}
        
        job.status = "running"
        job.started_at = datetime.utcnow()
        await db.commit()
    
    # Process with synchronous services
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.core.config import settings
    from app.services.vnb_digital import VNBDigitalClient
    
    sync_engine = create_engine(str(settings.database_url).replace("+asyncpg", ""))
    
    with Session(sync_engine) as sync_db:
        resolver = DNOResolver(db_session=sync_db)
        search_engine = SearchEngine()
        downloader = PDFDownloader()
        llm_extractor = LLMExtractor()
        vnb_client = VNBDigitalClient(request_delay=1.0)
        
        years = filters.get("years", [2024, 2025])
        types = filters.get("types", ["netzentgelte", "hlzf"])
        
        dno_name = None
        
        # ================================================================
        # Route based on input type
        # ================================================================
        
        if payload_type == "address":
            # Parse address input
            addr_data = payload.get("address", {})
            street = addr_data.get("street", "").strip()
            plz_city = addr_data.get("plz_city", "").strip()
            
            _report_step(sync_db, job_id, "Analyzing Input", "running", f"Parsing: {street}, {plz_city}")
            
            # Flexible PLZ + City parsing
            zip_code, city = _parse_plz_city(plz_city)
            
            if zip_code and city:
                _report_step(sync_db, job_id, "Analyzing Input", "done", f"ZIP={zip_code}, City={city}, Street={street}")
            else:
                _report_step(sync_db, job_id, "Analyzing Input", "done", f"Partial parse: ZIP={zip_code or 'N/A'}, City={city or 'N/A'}")
            
            # Check cache first
            _report_step(sync_db, job_id, "Checking Cache", "running", f"Looking for {zip_code}")
            
            norm_street = resolver.normalize_street(street)
            existing_dno = resolver.check_address_mapping(zip_code, norm_street)
            
            if existing_dno:
                dno_name = existing_dno
                _report_step(sync_db, job_id, "Checking Cache", "done", f"Found: {existing_dno}")
            else:
                _report_step(sync_db, job_id, "Checking Cache", "done", "No cached mapping")
                
                # Use VNB Digital API for address lookup
                _report_step(sync_db, job_id, "External Search", "running", "Querying VNB Digital API...")
                
                # Build full address string
                full_address = f"{street}, {plz_city}"
                dno_name = vnb_client.resolve_address_to_dno(full_address)
                
                if dno_name:
                    # Cache the result
                    resolver.save_address_mapping(zip_code, norm_street, dno_name)
                    _report_step(sync_db, job_id, "External Search", "done", f"Found: {dno_name}")
                else:
                    _report_step(sync_db, job_id, "External Search", "failed", "VNB Digital API returned no results")
                    await _mark_job_failed(job_id, f"Could not find DNO for: {street}, {plz_city}")
                    return {"status": "not_found", "message": "Could not resolve DNO"}
        
        elif payload_type == "dno":
            # Direct DNO name - skip geocoding
            dno_data = payload.get("dno", {})
            dno_name = dno_data.get("dno_name", "").strip()
            
            _report_step(sync_db, job_id, "Analyzing Input", "running", f"Using DNO: {dno_name}")
            _report_step(sync_db, job_id, "Analyzing Input", "done", f"DNO: {dno_name}")
            _report_step(sync_db, job_id, "Checking Cache", "done", "Direct DNO input - skipped")
        
        elif payload_type == "coordinates":
            # Coordinates - use VNB Digital API directly
            coords_data = payload.get("coordinates", {})
            lat = coords_data.get("latitude")
            lon = coords_data.get("longitude")
            
            _report_step(sync_db, job_id, "Analyzing Input", "running", f"Coordinates: ({lat}, {lon})")
            _report_step(sync_db, job_id, "Analyzing Input", "done", f"Lat={lat}, Lon={lon}")
            
            # Use VNB Digital API for coordinate lookup
            _report_step(sync_db, job_id, "External Search", "running", "Querying VNB Digital API by coordinates...")
            
            dno_name = vnb_client.resolve_coordinates_to_dno(lat, lon)
            
            if dno_name:
                _report_step(sync_db, job_id, "External Search", "done", f"Found: {dno_name}")
            else:
                _report_step(sync_db, job_id, "External Search", "failed", "VNB Digital API returned no results")
                await _mark_job_failed(job_id, f"Could not find DNO for coordinates: ({lat}, {lon})")
                return {"status": "not_found", "message": "Could not resolve DNO from coordinates"}
        
        else:
            await _mark_job_failed(job_id, f"Unknown payload type: {payload_type}")
            return {"status": "error", "message": f"Unknown payload type: {payload_type}"}
        
        # ================================================================
        # Process PDFs for the identified DNO
        # ================================================================
        
        if not dno_name:
            await _mark_job_failed(job_id, "No DNO name resolved")
            return {"status": "error", "message": "No DNO name resolved"}
        
        all_results = {
            "dno_name": dno_name,
            "netzentgelte": {},
            "hlzf": {},
        }
        
        for year in years:
            if "netzentgelte" in types:
                result = _find_and_process_pdf(
                    sync_db, job_id, dno_name, year,
                    search_engine, downloader, llm_extractor
                )
                if result.get("status") == "success":
                    all_results["netzentgelte"][year] = result.get("records", [])
            
            if "hlzf" in types:
                result = _extract_hlzf(
                    sync_db, job_id, dno_name, year,
                    search_engine, downloader, llm_extractor
                )
                if result.get("status") == "success":
                    all_results["hlzf"][year] = result.get("records", [])
        
        # Mark job as completed
        async with get_db_session() as db:
            from sqlalchemy import select
            from app.db.models import SearchJobModel
            
            result = await db.execute(
                select(SearchJobModel).where(SearchJobModel.id == job_id)
            )
            job = result.scalar_one_or_none()
            if job:
                job.status = "completed"
                job.result = all_results
                job.completed_at = datetime.utcnow()
                await db.commit()
        
        log.info("Structured search completed", dno=dno_name)
        return {"status": "completed", "dno_name": dno_name}


def _parse_plz_city(plz_city: str) -> tuple[str, str]:
    """
    Parse PLZ + City from various formats.
    
    Handles:
    - "50859 Köln"
    - "Köln 50859"
    - "50859, Köln"
    - "Köln, 50859"
    """
    import re
    
    # Clean up the input
    text = plz_city.strip()
    text = re.sub(r'\s*,\s*', ' ', text)  # Replace comma with space
    text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
    
    # Find the 5-digit PLZ
    plz_match = re.search(r'\b(\d{5})\b', text)
    if not plz_match:
        # No PLZ found, try to guess
        return "", text
    
    plz = plz_match.group(1)
    
    # Remove PLZ from text to get city
    city = text[:plz_match.start()] + text[plz_match.end():]
    city = city.strip()
    
    # Clean up city name (remove extra spaces, leading/trailing punctuation)
    city = re.sub(r'^[\s,.-]+|[\s,.-]+$', '', city)
    
    return plz, city

def _find_and_process_pdf(
    db: "Session",
    job_id: str,
    dno_name: str,
    year: int,
    search_engine: SearchEngine,
    downloader: PDFDownloader,
    llm_extractor: LLMExtractor,
) -> dict:
    """Find and process Netzentgelte PDF using services."""
    log = logger.bind(dno=dno_name, year=year)
    
    # Check known PDF URLs first
    from app.services.extraction.pdf_extractor import find_pdf_url_for_dno
    
    _report_step(db, job_id, "Finding PDF", "running", f"Checking known URLs for {dno_name}...")
    known_url = find_pdf_url_for_dno(dno_name, year, "netzentgelte")
    
    if known_url:
        _report_step(db, job_id, "Finding PDF", "done", "Known URL found")
        pdf_path = _download_and_extract(db, job_id, known_url, dno_name, year, downloader, llm_extractor)
        if pdf_path:
            return pdf_path
    
    # Search for PDF
    _report_step(db, job_id, "Searching Web", "running", "Trying multiple search strategies...")
    url = search_engine.find_pdf_url(dno_name, year, "netzentgelte")
    
    if url:
        _report_step(db, job_id, "Searching Web", "done", "Found PDF URL")
        result = _download_and_extract(db, job_id, url, dno_name, year, downloader, llm_extractor)
        if result:
            return result
    
    _report_step(db, job_id, "Searching Web", "failed", "No valid PDF found")
    return {"dno": dno_name, "year": year, "status": "not_found"}


def _download_and_extract(
    db: "Session",
    job_id: str,
    url: str,
    dno_name: str,
    year: int,
    downloader: PDFDownloader,
    llm_extractor: LLMExtractor,
) -> Optional[dict]:
    """Download PDF and extract data."""
    _report_step(db, job_id, "Downloading PDF", "running", "Fetching document...")
    pdf_path = downloader.download(url, dno_name, year)
    
    if not pdf_path:
        _report_step(db, job_id, "Downloading PDF", "failed", "Download failed")
        return None
    
    _report_step(db, job_id, "Downloading PDF", "done", "Download complete")
    
    # Validate
    _report_step(db, job_id, "Validating PDF", "running", "Checking document contents...")
    if not downloader.validate_content(pdf_path, dno_name, year, llm_extractor):
        _report_step(db, job_id, "Validating PDF", "failed", "Wrong document")
        return None
    
    _report_step(db, job_id, "Validating PDF", "done", "Document verified")
    
    # Extract
    _report_step(db, job_id, "Extracting Data", "running", "Processing PDF...")
    data = extract_netzentgelte_from_pdf(pdf_path)
    
    if not data:
        data = llm_extractor.extract_netzentgelte(pdf_path, dno_name, year)
    
    if data:
        _report_step(db, job_id, "Extracting Data", "done", f"Extracted {len(data)} records")
        return {
            "dno": dno_name,
            "year": year,
            "status": "success",
            "source_url": url,
            "records": data,
        }
    
    return None


def _extract_hlzf(
    db: "Session",
    job_id: str,
    dno_name: str,
    year: int,
    search_engine: SearchEngine,
    downloader: PDFDownloader,
    llm_extractor: LLMExtractor,
) -> dict:
    """Extract HLZF data for a DNO."""
    from app.services.extraction.pdf_extractor import find_pdf_url_for_dno
    
    known_url = find_pdf_url_for_dno(dno_name, year, "regelungen")
    
    if known_url:
        pdf_path = downloader.download(known_url, dno_name, year, pdf_type="regelungen")
        if pdf_path:
            try:
                data = extract_hlzf_from_pdf(pdf_path)
                if data:
                    return {"dno": dno_name, "year": year, "status": "success", "records": data}
            except Exception:
                pass
    
    # Search for HLZF PDF
    url = search_engine.find_pdf_url(dno_name, year, "regelungen")
    if url:
        pdf_path = downloader.download(url, dno_name, year, pdf_type="regelungen")
        if pdf_path:
            try:
                data = extract_hlzf_from_pdf(pdf_path)
                if data:
                    return {"dno": dno_name, "year": year, "status": "success", "records": data}
            except Exception:
                pass
    
    return {"dno": dno_name, "year": year, "status": "not_found"}


def _report_step(db: "Session", job_id: str, label: str, status: str, detail: str = "") -> None:
    """Update job progress in DB for frontend polling."""
    if not job_id or not db:
        return
    
    try:
        from sqlalchemy import select
        from app.db.models import SearchJobModel
        
        job = db.execute(
            select(SearchJobModel).where(SearchJobModel.id == job_id)
        ).scalar_one_or_none()
        
        if not job:
            return
        
        now = datetime.now().isoformat()
        
        if status == "running":
            step_num = len(job.steps_history) + 1
            new_step = {
                "step": step_num,
                "label": label,
                "status": status,
                "detail": detail,
                "started_at": now,
            }
            job.steps_history = [*job.steps_history, new_step]
            job.current_step = label
            job.status = "running"
        else:
            if job.steps_history:
                updated_history = list(job.steps_history)
                updated_history[-1] = {
                    **updated_history[-1],
                    "status": status,
                    "detail": detail,
                    "completed_at": now,
                }
                job.steps_history = updated_history
            
            if status == "failed":
                job.status = "failed"
                job.error_message = detail
        
        db.commit()
        
    except Exception as e:
        logger.error("Failed to report step", error=str(e))
        try:
            db.rollback()
        except:
            pass


async def _mark_job_failed(job_id: str, message: str) -> None:
    """Mark job as failed in database."""
    from sqlalchemy import select
    from app.db.models import SearchJobModel
    
    async with get_db_session() as db:
        result = await db.execute(
            select(SearchJobModel).where(SearchJobModel.id == job_id)
        )
        job = result.scalar_one_or_none()
        if job:
            job.status = "failed"
            job.error_message = message
            job.completed_at = datetime.utcnow()
            await db.commit()
