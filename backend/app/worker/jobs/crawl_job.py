"""
Crawl job handlers for the DNO Crawler worker.

These jobs are picked up by the arq worker and execute the crawling workflow.
"""

from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.core.models import JobStatus
from app.db import get_db_session, CrawlJobModel, CrawlJobStepModel, DNOModel

logger = structlog.get_logger()


async def update_job_status(
    job_id: int,
    status: JobStatus,
    *,
    progress: int | None = None,
    current_step: str | None = None,
    error_message: str | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> None:
    """Update the status of a crawl job in the database."""
    async with get_db_session() as db:
        values: dict[str, Any] = {"status": status.value}
        if progress is not None:
            values["progress"] = progress
        if current_step is not None:
            values["current_step"] = current_step
        if error_message is not None:
            values["error_message"] = error_message
        if started_at is not None:
            values["started_at"] = started_at
        if completed_at is not None:
            values["completed_at"] = completed_at

        stmt = update(CrawlJobModel).where(CrawlJobModel.id == job_id).values(**values)
        await db.execute(stmt)
        await db.commit()


async def create_job_step(
    job_id: int,
    step_name: str,
    status: JobStatus = JobStatus.PENDING,
) -> int:
    """Create a new step for a crawl job."""
    async with get_db_session() as db:
        step = CrawlJobStepModel(
            job_id=job_id,
            step_name=step_name,
            status=status.value,
        )
        db.add(step)
        await db.commit()
        await db.refresh(step)
        return step.id


async def update_job_step(
    step_id: int,
    status: JobStatus,
    *,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    duration_seconds: int | None = None,
    details: dict | None = None,
) -> None:
    """Update the status of a job step."""
    async with get_db_session() as db:
        values: dict[str, Any] = {"status": status.value}
        if started_at is not None:
            values["started_at"] = started_at
        if completed_at is not None:
            values["completed_at"] = completed_at
        if duration_seconds is not None:
            values["duration_seconds"] = duration_seconds
        if details is not None:
            values["details"] = details

        stmt = (
            update(CrawlJobStepModel)
            .where(CrawlJobStepModel.id == step_id)
            .values(**values)
        )
        await db.execute(stmt)
        await db.commit()


async def _extract_with_ollama(
    ollama_url: str,
    netzentgelte_path: str | None,
    regelungen_path: str | None,
    dno_name: str,
    year: int,
) -> dict:
    """
    Use Ollama LLM to extract data from PDFs when pdfplumber fails.
    
    Args:
        ollama_url: URL to Ollama API
        netzentgelte_path: Path to Netzentgelte PDF (if extraction needed)
        regelungen_path: Path to Regelungen PDF (if extraction needed)
        dno_name: Name of the DNO
        year: Year to extract data for
        
    Returns:
        Dict with "netzentgelte" and/or "hlzf" lists
    """
    import httpx
    import json
    import pdfplumber
    from pathlib import Path
    
    log = logger.bind(dno=dno_name, year=year)
    results = {"netzentgelte": [], "hlzf": []}
    
    model = "qwen3-vl:2b"  # Vision-capable model for PDF understanding
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Check if Ollama is available
        try:
            health = await client.get(f"{ollama_url}/api/tags")
            if health.status_code != 200:
                log.warning("Ollama not available")
                return results
        except Exception as e:
            log.warning(f"Ollama connection failed: {e}")
            return results
        
        # Extract Netzentgelte with AI
        if netzentgelte_path:
            pdf_path = Path(netzentgelte_path)
            if pdf_path.exists():
                # Extract text from PDF for context
                try:
                    with pdfplumber.open(pdf_path) as pdf:
                        text = "\n".join([p.extract_text() or "" for p in pdf.pages[:5]])
                    
                    prompt = f"""Extract the Netzentgelte (network charges) data from this text for {dno_name} {year}.

Look for a table with voltage levels (Hochspannung, Umspannung HS/MS, Mittelspannung, Umspannung MS/NS, Niederspannung) and 4 price columns:
1. Leistungspreis < 2500h
2. Arbeitspreis < 2500h  
3. Leistungspreis >= 2500h
4. Arbeitspreis >= 2500h

Return JSON only, no other text:
{{"records": [{{"voltage_level": "...", "lp_unter": ..., "ap_unter": ..., "lp": ..., "ap": ...}}]}}

Text:
{text[:4000]}"""

                    response = await client.post(
                        f"{ollama_url}/api/generate",
                        json={"model": model, "prompt": prompt, "stream": False},
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        answer = result.get("response", "")
                        
                        # Try to parse JSON from response
                        try:
                            # Find JSON in response
                            import re
                            json_match = re.search(r'\{.*\}', answer, re.DOTALL)
                            if json_match:
                                data = json.loads(json_match.group())
                                for r in data.get("records", []):
                                    results["netzentgelte"].append({
                                        "voltage_level": r.get("voltage_level", ""),
                                        "leistung_unter_2500h": r.get("lp_unter"),
                                        "arbeit_unter_2500h": r.get("ap_unter"),
                                        "leistung": r.get("lp"),
                                        "arbeit": r.get("ap"),
                                    })
                                log.info(f"AI extracted {len(results['netzentgelte'])} Netzentgelte records")
                        except json.JSONDecodeError:
                            log.warning("Failed to parse AI response as JSON")
                            
                except Exception as e:
                    log.error(f"AI Netzentgelte extraction failed: {e}")
        
        # Extract HLZF with AI
        if regelungen_path:
            pdf_path = Path(regelungen_path)
            if pdf_path.exists():
                try:
                    with pdfplumber.open(pdf_path) as pdf:
                        # Find HLZF section
                        text = ""
                        for page in pdf.pages:
                            page_text = page.extract_text() or ""
                            if "hochlast" in page_text.lower():
                                text += page_text + "\n"
                        
                        if not text:
                            text = "\n".join([p.extract_text() or "" for p in pdf.pages[10:15]])
                    
                    prompt = f"""Extract the Hochlastzeitfenster (HLZF - peak load time windows) from this text for {dno_name} {year}.

Look for a table with:
- Rows: Voltage levels (Hochspannungsnetz, Umspannung zur Mittelspannung, Mittelspannungsnetz, etc.)
- Columns: Seasons (Winter, Frühling, Sommer, Herbst)
- Values: Time windows like "07:30-15:30" or "entfällt" (means null)

Return JSON only:
{{"records": [{{"voltage_level": "...", "winter": "...", "fruehling": null, "sommer": null, "herbst": "..."}}]}}

Text:
{text[:4000]}"""

                    response = await client.post(
                        f"{ollama_url}/api/generate",
                        json={"model": model, "prompt": prompt, "stream": False},
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        answer = result.get("response", "")
                        
                        try:
                            import re
                            json_match = re.search(r'\{.*\}', answer, re.DOTALL)
                            if json_match:
                                data = json.loads(json_match.group())
                                for r in data.get("records", []):
                                    results["hlzf"].append({
                                        "voltage_level": r.get("voltage_level", ""),
                                        "winter": r.get("winter"),
                                        "fruehling": r.get("fruehling"),
                                        "sommer": r.get("sommer"),
                                        "herbst": r.get("herbst"),
                                    })
                                log.info(f"AI extracted {len(results['hlzf'])} HLZF records")
                        except json.JSONDecodeError:
                            log.warning("Failed to parse AI HLZF response as JSON")
                            
                except Exception as e:
                    log.error(f"AI HLZF extraction failed: {e}")
    
    return results


async def crawl_dno_job(ctx: dict, job_id: int) -> dict:
    """
    Main crawl job that orchestrates the DNO data extraction workflow.

    Workflow steps:
    1. Initialize - Load DNO config and validate
    2. Discover - Find source URLs for data (SearXNG or configured URLs)
    3. Fetch - Download pages/PDFs
    4. Parse - Extract structured data from content
    5. Store - Save data to database
    6. Finalize - Update job status and cleanup

    Args:
        ctx: arq context dictionary
        job_id: ID of the CrawlJobModel in the database

    Returns:
        dict with job results
    """
    log = logger.bind(job_id=job_id)
    log.info("Starting crawl job")

    now = datetime.now(timezone.utc)

    try:
        # Mark job as running
        await update_job_status(
            job_id,
            JobStatus.RUNNING,
            progress=0,
            current_step="Initializing",
            started_at=now,
        )

        # Load job details from database
        async with get_db_session() as db:
            query = (
                select(CrawlJobModel)
                .options(selectinload(CrawlJobModel.steps))
                .where(CrawlJobModel.id == job_id)
            )
            result = await db.execute(query)
            job = result.scalar_one_or_none()

            if not job:
                raise ValueError(f"Job {job_id} not found")

            # Load DNO
            dno_query = select(DNOModel).where(DNOModel.id == job.dno_id)
            dno_result = await db.execute(dno_query)
            dno = dno_result.scalar_one_or_none()

            if not dno:
                raise ValueError(f"DNO {job.dno_id} not found")

        log = log.bind(dno_slug=dno.slug, year=job.year, data_type=job.data_type)
        log.info("Loaded job configuration")

        # Step 1: Initialize
        init_step_id = await create_job_step(job_id, "Initialize")
        await update_job_step(init_step_id, JobStatus.RUNNING, started_at=now)
        await update_job_status(job_id, JobStatus.RUNNING, progress=10, current_step="Initialize")

        # Initialization logic here
        await update_job_step(
            init_step_id,
            JobStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc),
            duration_seconds=1,
            details={"dno_name": dno.name, "year": job.year},
        )
        log.info("Initialization complete")

        # Step 2: Discover sources (find PDF URLs for Netzentgelte and Regelungen)
        discover_step_id = await create_job_step(job_id, "Discover Sources")
        await update_job_step(discover_step_id, JobStatus.RUNNING, started_at=datetime.now(timezone.utc))
        await update_job_status(job_id, JobStatus.RUNNING, progress=15, current_step="Discovering sources")

        from app.crawler.pdf_extractor import find_pdf_url_for_dno
        
        netzentgelte_url = find_pdf_url_for_dno(dno.name, job.year, "netzentgelte")
        regelungen_url = find_pdf_url_for_dno(dno.name, job.year, "regelungen")
        
        sources_found = []
        if netzentgelte_url:
            sources_found.append({"type": "netzentgelte", "url": netzentgelte_url})
        if regelungen_url:
            sources_found.append({"type": "regelungen", "url": regelungen_url})
        
        if not sources_found and dno.website:
            sources_found.append({"type": "website", "url": dno.website})

        await update_job_step(
            discover_step_id,
            JobStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc),
            duration_seconds=2,
            details={
                "sources_found": len(sources_found),
                "netzentgelte_url": netzentgelte_url,
                "regelungen_url": regelungen_url,
            },
        )
        log.info("Discovery complete", sources=len(sources_found), netzentgelte=bool(netzentgelte_url), regelungen=bool(regelungen_url))

        # Step 3: Fetch content (download both PDFs)
        fetch_step_id = await create_job_step(job_id, "Fetch Content")
        await update_job_step(fetch_step_id, JobStatus.RUNNING, started_at=datetime.now(timezone.utc))
        await update_job_status(job_id, JobStatus.RUNNING, progress=30, current_step="Downloading PDFs")

        import httpx
        from pathlib import Path
        
        downloads_dir = Path("/data/downloads") / dno.slug
        downloads_dir.mkdir(parents=True, exist_ok=True)
        
        netzentgelte_path = None
        regelungen_path = None
        pdfs_downloaded = 0
        
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
            # Download Netzentgelte PDF
            if netzentgelte_url:
                pdf_filename = f"{dno.slug}-netzentgelte-{job.year}.pdf"
                netzentgelte_path = downloads_dir / pdf_filename
                try:
                    response = await client.get(netzentgelte_url)
                    response.raise_for_status()
                    netzentgelte_path.write_bytes(response.content)
                    pdfs_downloaded += 1
                    log.info(f"Downloaded Netzentgelte PDF", path=str(netzentgelte_path), size=len(response.content))
                except Exception as e:
                    log.error(f"Failed to download Netzentgelte PDF: {e}")
                    netzentgelte_path = None
            
            # Download Regelungen PDF
            if regelungen_url:
                pdf_filename = f"{dno.slug}-regelungen-{job.year}.pdf"
                regelungen_path = downloads_dir / pdf_filename
                try:
                    response = await client.get(regelungen_url)
                    response.raise_for_status()
                    regelungen_path.write_bytes(response.content)
                    pdfs_downloaded += 1
                    log.info(f"Downloaded Regelungen PDF", path=str(regelungen_path), size=len(response.content))
                except Exception as e:
                    log.error(f"Failed to download Regelungen PDF: {e}")
                    regelungen_path = None

        await update_job_step(
            fetch_step_id,
            JobStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc),
            duration_seconds=5,
            details={
                "pdfs_downloaded": pdfs_downloaded,
                "netzentgelte_path": str(netzentgelte_path) if netzentgelte_path else None,
                "regelungen_path": str(regelungen_path) if regelungen_path else None,
            },
        )
        log.info("Fetch complete", pdfs_downloaded=pdfs_downloaded)

        # Step 4: Parse content (extract data from PDFs)
        parse_step_id = await create_job_step(job_id, "Parse Content")
        await update_job_step(parse_step_id, JobStatus.RUNNING, started_at=datetime.now(timezone.utc))
        await update_job_status(job_id, JobStatus.RUNNING, progress=50, current_step="Extracting data from PDFs")

        from app.crawler.pdf_extractor import extract_netzentgelte_from_pdf, extract_hlzf_from_pdf
        
        netzentgelte_records = []
        hlzf_records = []
        ai_used = False
        
        # Extract Netzentgelte
        if netzentgelte_path and netzentgelte_path.exists():
            try:
                netzentgelte_records = extract_netzentgelte_from_pdf(netzentgelte_path)
                log.info(f"Extracted {len(netzentgelte_records)} Netzentgelte records")
            except Exception as e:
                log.error(f"Failed to extract Netzentgelte: {e}")
        
        # Extract HLZF
        if regelungen_path and regelungen_path.exists():
            try:
                hlzf_records = extract_hlzf_from_pdf(regelungen_path)
                log.info(f"Extracted {len(hlzf_records)} HLZF records")
            except Exception as e:
                log.error(f"Failed to extract HLZF: {e}")
        
        # AI Fallback: If extraction failed or yielded no results, try Ollama
        import os
        ollama_url = os.environ.get("OLLAMA_URL", "http://ollama:11434")
        
        if not netzentgelte_records or not hlzf_records:
            log.info("Attempting AI fallback with Ollama", ollama_url=ollama_url)
            try:
                ai_results = await _extract_with_ollama(
                    ollama_url=ollama_url,
                    netzentgelte_path=netzentgelte_path if not netzentgelte_records else None,
                    regelungen_path=regelungen_path if not hlzf_records else None,
                    dno_name=dno.name,
                    year=job.year,
                )
                if ai_results.get("netzentgelte") and not netzentgelte_records:
                    netzentgelte_records = ai_results["netzentgelte"]
                    ai_used = True
                if ai_results.get("hlzf") and not hlzf_records:
                    hlzf_records = ai_results["hlzf"]
                    ai_used = True
            except Exception as e:
                log.warning(f"AI fallback failed: {e}")

        await update_job_step(
            parse_step_id,
            JobStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc),
            duration_seconds=5,
            details={
                "netzentgelte_count": len(netzentgelte_records),
                "hlzf_count": len(hlzf_records),
                "ai_used": ai_used,
            },
        )
        log.info("Parsing complete", netzentgelte=len(netzentgelte_records), hlzf=len(hlzf_records), ai_used=ai_used)

        # Step 5: Store data in database
        store_step_id = await create_job_step(job_id, "Store Data")
        await update_job_step(store_step_id, JobStatus.RUNNING, started_at=datetime.now(timezone.utc))
        await update_job_status(job_id, JobStatus.RUNNING, progress=75, current_step="Storing extracted data")

        from app.db import NetzentgelteModel, HLZFModel
        from sqlalchemy import and_
        
        netzentgelte_inserted = 0
        hlzf_inserted = 0
        
        # Standard voltage level mapping - maps various names to canonical names
        VOLTAGE_LEVEL_MAPPING = {
            # Hochspannung variants
            "hochspannung": "Hochspannung",
            "hochspannungsnetz": "Hochspannung",
            "hs": "Hochspannung",
            # Mittelspannung variants
            "mittelspannung": "Mittelspannung",
            "mittelspannungsnetz": "Mittelspannung",
            "ms": "Mittelspannung",
            # Niederspannung variants
            "niederspannung": "Niederspannung",
            "niederspannungsnetz": "Niederspannung",
            "ns": "Niederspannung",
            # Umspannung HS/MS variants
            "umspannung hoch-/mittelspannung": "Umspannung HS/MS",
            "umspannung hoch-mittelspannung": "Umspannung HS/MS",
            "umspannung hochspannung/mittelspannung": "Umspannung HS/MS",
            "hoch-/mittelspannung": "Umspannung HS/MS",
            "hs/ms": "Umspannung HS/MS",
            "umspannung zur mittelspannung": "Umspannung HS/MS",
            "umspg. zur mittelspannung": "Umspannung HS/MS",
            "umsp. zur ms": "Umspannung HS/MS",
            # Umspannung MS/NS variants
            "umspannung mittel-/niederspannung": "Umspannung MS/NS",
            "umspannung mittel-niederspannung": "Umspannung MS/NS",
            "umspannung mittelspannung/niederspannung": "Umspannung MS/NS",
            "mittel-/niederspannung": "Umspannung MS/NS",
            "ms/ns": "Umspannung MS/NS",
            "umspannung zur niederspannung": "Umspannung MS/NS",
            "umspg. zur niederspannung": "Umspannung MS/NS",
            "umsp. zur ns": "Umspannung MS/NS",
        }
        
        # Normalize voltage_level to prevent duplicates and standardize names
        def normalize_voltage_level(records):
            for record in records:
                if "voltage_level" in record and record["voltage_level"]:
                    # Replace newlines with spaces and collapse multiple spaces
                    cleaned = " ".join(record["voltage_level"].replace("\n", " ").split())
                    # Look up in mapping (case-insensitive)
                    normalized = VOLTAGE_LEVEL_MAPPING.get(cleaned.lower(), cleaned)
                    record["voltage_level"] = normalized
            return records
        
        netzentgelte_records = normalize_voltage_level(netzentgelte_records)
        hlzf_records = normalize_voltage_level(hlzf_records)
        
        async with get_db_session() as db:
            # Store Netzentgelte records
            for record in netzentgelte_records:
                existing_query = select(NetzentgelteModel).where(
                    and_(
                        NetzentgelteModel.dno_id == dno.id,
                        NetzentgelteModel.year == job.year,
                        NetzentgelteModel.voltage_level == record["voltage_level"]
                    )
                )
                existing_result = await db.execute(existing_query)
                existing = existing_result.scalar_one_or_none()
                
                if existing:
                    existing.leistung = record.get("leistung")
                    existing.arbeit = record.get("arbeit")
                    existing.leistung_unter_2500h = record.get("leistung_unter_2500h")
                    existing.arbeit_unter_2500h = record.get("arbeit_unter_2500h")
                    existing.verification_status = "extracted"
                    log.info(f"Updated Netzentgelte: {record['voltage_level']}")
                else:
                    new_record = NetzentgelteModel(
                        dno_id=dno.id,
                        year=job.year,
                        voltage_level=record["voltage_level"],
                        leistung=record.get("leistung"),
                        arbeit=record.get("arbeit"),
                        leistung_unter_2500h=record.get("leistung_unter_2500h"),
                        arbeit_unter_2500h=record.get("arbeit_unter_2500h"),
                        verification_status="extracted",
                    )
                    db.add(new_record)
                    netzentgelte_inserted += 1
                    log.info(f"Inserted Netzentgelte: {record['voltage_level']}")
            
            # Store HLZF records
            for record in hlzf_records:
                existing_query = select(HLZFModel).where(
                    and_(
                        HLZFModel.dno_id == dno.id,
                        HLZFModel.year == job.year,
                        HLZFModel.voltage_level == record["voltage_level"]
                    )
                )
                existing_result = await db.execute(existing_query)
                existing = existing_result.scalar_one_or_none()
                
                if existing:
                    existing.winter = record.get("winter")
                    existing.fruehling = record.get("fruehling")
                    existing.sommer = record.get("sommer")
                    existing.herbst = record.get("herbst")
                    existing.verification_status = "extracted"
                    log.info(f"Updated HLZF: {record['voltage_level']}")
                else:
                    new_record = HLZFModel(
                        dno_id=dno.id,
                        year=job.year,
                        voltage_level=record["voltage_level"],
                        winter=record.get("winter"),
                        fruehling=record.get("fruehling"),
                        sommer=record.get("sommer"),
                        herbst=record.get("herbst"),
                        verification_status="extracted",
                    )
                    db.add(new_record)
                    hlzf_inserted += 1
                    log.info(f"Inserted HLZF: {record['voltage_level']}")
            
            await db.commit()

        await update_job_step(
            store_step_id,
            JobStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc),
            duration_seconds=3,
            details={
                "netzentgelte_inserted": netzentgelte_inserted,
                "hlzf_inserted": hlzf_inserted,
                "total_records": netzentgelte_inserted + hlzf_inserted,
            },
        )
        log.info("Data storage complete", netzentgelte=netzentgelte_inserted, hlzf=hlzf_inserted)

        # Step 6: Finalize
        finalize_step_id = await create_job_step(job_id, "Finalize")
        await update_job_step(finalize_step_id, JobStatus.RUNNING, started_at=datetime.now(timezone.utc))
        await update_job_status(job_id, JobStatus.RUNNING, progress=95, current_step="Finalizing")

        await update_job_step(
            finalize_step_id,
            JobStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc),
            duration_seconds=1,
            details={"status": "success"},
        )

        # Mark job as completed
        completed_at = datetime.now(timezone.utc)
        await update_job_status(
            job_id,
            JobStatus.COMPLETED,
            progress=100,
            current_step="Completed",
            completed_at=completed_at,
        )

        log.info("Crawl job completed successfully")
        return {
            "status": "completed",
            "job_id": job_id,
            "dno": dno.slug,
            "year": job.year,
            "data_type": job.data_type,
        }

    except Exception as e:
        log.error("Crawl job failed", error=str(e))
        await update_job_status(
            job_id,
            JobStatus.FAILED,
            error_message=str(e),
            completed_at=datetime.now(timezone.utc),
        )
        raise


async def discover_sources_job(ctx: dict, dno_id: int, year: int, data_type: str) -> dict:
    """
    Standalone job to discover data sources for a DNO.

    Uses SearXNG to search for PDFs and pages containing Netzentgelte or HLZF data.

    Args:
        ctx: arq context dictionary
        dno_id: ID of the DNO
        year: Year to search for
        data_type: Type of data to find ("netzentgelte", "hlzf", "all")

    Returns:
        dict with discovered URLs
    """
    log = logger.bind(dno_id=dno_id, year=year, data_type=data_type)
    log.info("Starting discovery job")

    async with get_db_session() as db:
        dno_query = select(DNOModel).where(DNOModel.id == dno_id)
        result = await db.execute(dno_query)
        dno = result.scalar_one_or_none()

        if not dno:
            raise ValueError(f"DNO {dno_id} not found")

    # TODO: Implement SearXNG integration
    # Search queries like: "{dno_name} Netzentgelte {year} filetype:pdf"

    log.info("Discovery job completed (not yet implemented)")
    return {
        "status": "completed",
        "dno_id": dno_id,
        "discovered_urls": [],
        "message": "Discovery not yet implemented",
    }


async def extract_pdf_job(ctx: dict, file_path: str, dno_id: int, year: int) -> dict:
    """
    Extract data from a downloaded PDF file.

    Uses PDF parsing libraries and optionally LLM for structured extraction.

    Args:
        ctx: arq context dictionary
        file_path: Path to the PDF file
        dno_id: ID of the DNO
        year: Year the data is for

    Returns:
        dict with extracted data
    """
    log = logger.bind(file_path=file_path, dno_id=dno_id, year=year)
    log.info("Starting PDF extraction job")

    # TODO: Implement PDF extraction
    # 1. Read PDF with pdfplumber/PyMuPDF
    # 2. Extract tables
    # 3. Use LLM to identify and structure Netzentgelte/HLZF data

    log.info("PDF extraction job completed (not yet implemented)")
    return {
        "status": "completed",
        "file_path": file_path,
        "extracted_records": 0,
        "message": "Extraction not yet implemented",
    }
