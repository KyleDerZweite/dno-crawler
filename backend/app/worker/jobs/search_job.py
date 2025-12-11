"""
Search job handler for the ARQ worker.

This job wraps the SearchAgent for queue-based processing.
Supports both legacy crawl jobs and new natural language search with Timeline UI.
"""

from datetime import datetime
from typing import Optional

import structlog

from app.crawler.search_agent import SearchAgent
from app.db import get_db_session

logger = structlog.get_logger()


async def job_process_search_request(
    ctx: dict, 
    # Legacy format
    payload: Optional[dict] = None,
    # New NL search format
    job_id: Optional[str] = None,
    prompt: Optional[str] = None,
    filters: Optional[dict] = None,
) -> dict:
    """
    ARQ job function for processing search requests.
    
    Runs strictly one at a time due to max_jobs=1 in WorkerSettings.
    
    Supports two modes:
    1. Legacy: payload dict with 'type' field
    2. NL Search: job_id + prompt + filters for Timeline UI
    """
    log = logger.bind(job_id=job_id)
    
    # Determine mode
    is_nl_search = job_id is not None and prompt is not None
    
    if is_nl_search:
        return await _process_nl_search(ctx, job_id, prompt, filters or {})
    elif payload:
        return await _process_legacy_search(ctx, payload)
    else:
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
    
    # Process with synchronous SearchAgent (using sync DB session)
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.core.config import settings
    
    # Create sync engine for SearchAgent (which is synchronous)
    sync_engine = create_engine(str(settings.database_url).replace("+asyncpg", ""))
    
    with Session(sync_engine) as sync_db:
        agent = SearchAgent(db_session=sync_db)
        agent.set_job_id(job_id)
        
        # Parse filters
        years = filters.get("years", [2024, 2025])
        types = filters.get("types", ["netzentgelte", "hlzf"])
        
        # Step 1: Parse the prompt (simplified - assumes address format)
        agent._report_step("Analyzing Input", "running", f"Parsing: {prompt[:50]}...")
        
        # Extract address components using German address format: "Street, ZIP City"
        # More robust parsing that handles "An der Ronne 160, 50859 Köln"
        import re
        
        # Find ZIP code (5 consecutive digits)
        zip_match = re.search(r'\b(\d{5})\b', prompt)
        zip_code = zip_match.group(1) if zip_match else ""
        
        if zip_code and zip_match:
            # City comes AFTER the ZIP code in German format
            after_zip = prompt[zip_match.end():].strip()
            # City is typically the first word(s) after ZIP, before any punctuation
            city_match = re.match(r'^([A-Za-zäöüÄÖÜß\s-]+)', after_zip)
            city = city_match.group(1).strip() if city_match else ""
            
            # Street is everything BEFORE the ZIP (minus the comma)
            street = prompt[:zip_match.start()].rstrip(', ').strip()
        else:
            # Fallback: try comma-based splitting
            parts = [p.strip() for p in prompt.split(',')]
            if len(parts) >= 2:
                street = parts[0]
                # Second part might be "ZIP City"
                zip_city = parts[1].strip().split()
                zip_code = zip_city[0] if zip_city and zip_city[0].isdigit() else ""
                city = " ".join(zip_city[1:]) if len(zip_city) > 1 else ""
            else:
                street = prompt
                city = ""
        
        if zip_code and city:
            agent._report_step("Analyzing Input", "done", f"ZIP={zip_code}, City={city}, Street={street}")
        else:
            agent._report_step("Analyzing Input", "done", f"Partial parse: ZIP={zip_code or 'N/A'}, City={city or 'N/A'}")
        
        # Step 2: Resolve DNO
        dno_name = agent.resolve_dno_from_address(zip_code, city, street)
        
        if not dno_name:
            # Mark job as failed
            async with get_db_session() as db:
                result = await db.execute(
                    select(SearchJobModel).where(SearchJobModel.id == job_id)
                )
                job = result.scalar_one_or_none()
                if job:
                    job.status = "failed"
                    job.error_message = f"Could not find DNO for: {prompt}"
                    job.completed_at = datetime.utcnow()
                    await db.commit()
            
            return {"status": "not_found", "message": "Could not resolve DNO"}
        
        # Step 3: Process for each year and type
        all_results = {
            "dno_name": dno_name,
            "netzentgelte": {},
            "hlzf": {},
        }
        
        for year in years:
            if "netzentgelte" in types:
                result = agent.find_and_process_pdf(dno_name, year)
                if result.get("status") == "success":
                    all_results["netzentgelte"][year] = result.get("records", [])
            
            if "hlzf" in types:
                result = agent.extract_hlzf(dno_name, year)
                if result.get("status") == "success":
                    all_results["hlzf"][year] = result.get("records", [])
        
        # Mark job as completed
        async with get_db_session() as db:
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


async def _process_legacy_search(ctx: dict, payload: dict) -> dict:
    """
    Process legacy search request (existing crawl.py endpoints).
    """
    log = logger.bind(job_type=payload.get('type'))
    log.info("Processing legacy search request")
    
    # Get DB session from context
    db = ctx.get('db')
    agent = SearchAgent(db_session=db)
    
    job_type = payload.get('type')
    
    if job_type == 'address':
        # Address resolution flow
        zip_code = payload.get('zip', '')
        city = payload.get('city', '')
        street = payload.get('street', '')
        year = payload.get('year', 2025)
        
        log.info("Resolving DNO from address", zip=zip_code, city=city)
        
        # Phase 1: Resolve DNO
        dno_name = agent.resolve_dno_from_address(zip_code, city, street)
        
        if not dno_name:
            return {
                "status": "not_found",
                "message": f"Could not find DNO for address: {zip_code} {city}",
            }
        
        # Phase 2: Find and process PDF
        result = agent.find_and_process_pdf(dno_name, year)
        result['resolved_dno'] = dno_name
        result['input'] = {'zip': zip_code, 'city': city, 'street': street}
        
        return result
        
    elif job_type == 'batch_dno':
        # Direct batch DNO processing
        dno_names = payload.get('dno_names', [])
        year = payload.get('year', 2025)
        
        log.info("Processing DNO batch", count=len(dno_names))
        
        results = agent.process_dno_batch(dno_names, year)
        
        return {
            "status": "completed",
            "total": len(dno_names),
            "results": results,
        }
        
    else:
        log.error("Unknown job type", job_type=job_type)
        return {
            "status": "error",
            "message": f"Unknown job type: {job_type}",
        }

