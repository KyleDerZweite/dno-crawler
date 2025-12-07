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

        # Step 2: Discover sources
        discover_step_id = await create_job_step(job_id, "Discover Sources")
        await update_job_step(discover_step_id, JobStatus.RUNNING, started_at=datetime.now(timezone.utc))
        await update_job_status(job_id, JobStatus.RUNNING, progress=20, current_step="Discovering sources")

        # TODO: Implement discovery logic using SearXNG or configured URLs
        # For now, we just log that this step would happen
        sources_found = []
        if dno.website:
            sources_found.append(dno.website)

        await update_job_step(
            discover_step_id,
            JobStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc),
            duration_seconds=2,
            details={"sources_found": len(sources_found), "urls": sources_found[:5]},
        )
        log.info("Discovery complete", sources_found=len(sources_found))

        # Step 3: Fetch content
        fetch_step_id = await create_job_step(job_id, "Fetch Content")
        await update_job_step(fetch_step_id, JobStatus.RUNNING, started_at=datetime.now(timezone.utc))
        await update_job_status(job_id, JobStatus.RUNNING, progress=40, current_step="Fetching content")

        # TODO: Implement fetching logic (HTTP client, Playwright for JS pages)
        # For now, simulate fetching
        await update_job_step(
            fetch_step_id,
            JobStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc),
            duration_seconds=5,
            details={"pages_fetched": 0, "pdfs_downloaded": 0},
        )
        log.info("Fetch complete")

        # Step 4: Parse content
        parse_step_id = await create_job_step(job_id, "Parse Content")
        await update_job_step(parse_step_id, JobStatus.RUNNING, started_at=datetime.now(timezone.utc))
        await update_job_status(job_id, JobStatus.RUNNING, progress=60, current_step="Parsing content")

        # TODO: Implement parsing logic (HTML parser, PDF parser)
        await update_job_step(
            parse_step_id,
            JobStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc),
            duration_seconds=3,
            details={"tables_found": 0, "potential_data_items": 0},
        )
        log.info("Parsing complete")

        # Step 5: Extract and store data
        store_step_id = await create_job_step(job_id, "Store Data")
        await update_job_step(store_step_id, JobStatus.RUNNING, started_at=datetime.now(timezone.utc))
        await update_job_status(job_id, JobStatus.RUNNING, progress=80, current_step="Storing data")

        # TODO: Implement LLM-based extraction and data storage
        await update_job_step(
            store_step_id,
            JobStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc),
            duration_seconds=2,
            details={"netzentgelte_records": 0, "hlzf_records": 0},
        )
        log.info("Data storage complete")

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
