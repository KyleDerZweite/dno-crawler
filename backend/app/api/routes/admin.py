"""
Admin routes - requires admin role.

User management has been moved to Zitadel.
This module only contains job management and data normalization routes.
"""

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

import structlog
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import User as AuthUser
from app.core.auth import require_admin
from app.core.config import settings
from app.core.models import APIResponse
from app.db import (
    CrawlJobModel,
    DNOModel,
    HLZFModel,
    NetzentgelteModel,
    get_db,
)

logger = structlog.get_logger()

router = APIRouter()

# Priority for bulk admin extraction jobs (lower than default 5)
BULK_EXTRACT_PRIORITY = 2


@router.get("/dashboard")
async def admin_dashboard(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Get admin dashboard statistics."""
    # Count DNOs
    dno_count = await db.scalar(select(func.count(DNOModel.id)))

    # Count DNOs by status
    uncrawled_count = await db.scalar(
        select(func.count(DNOModel.id)).where(DNOModel.status == "uncrawled")
    )
    crawled_count = await db.scalar(
        select(func.count(DNOModel.id)).where(DNOModel.status == "crawled")
    )

    # Count pending jobs
    pending_jobs = await db.scalar(
        select(func.count(CrawlJobModel.id)).where(CrawlJobModel.status == "pending")
    )
    running_jobs = await db.scalar(
        select(func.count(CrawlJobModel.id)).where(CrawlJobModel.status == "running")
    )

    # Count flagged records
    flagged_netzentgelte = await db.scalar(
        select(func.count(NetzentgelteModel.id)).where(
            NetzentgelteModel.verification_status == "flagged"
        )
    )
    flagged_hlzf = await db.scalar(
        select(func.count(HLZFModel.id)).where(HLZFModel.verification_status == "flagged")
    )

    # Count total data points
    total_netzentgelte = await db.scalar(select(func.count(NetzentgelteModel.id)))
    total_hlzf = await db.scalar(select(func.count(HLZFModel.id)))

    return APIResponse(
        success=True,
        data={
            "dnos": {
                "total": dno_count or 0,
                "uncrawled": uncrawled_count or 0,
                "crawled": crawled_count or 0,
            },
            "jobs": {
                "pending": pending_jobs or 0,
                "running": running_jobs or 0,
            },
            "data_points": {
                "netzentgelte": total_netzentgelte or 0,
                "hlzf": total_hlzf or 0,
                "total": (total_netzentgelte or 0) + (total_hlzf or 0),
            },
            "flagged": {
                "netzentgelte": flagged_netzentgelte or 0,
                "hlzf": flagged_hlzf or 0,
                "total": (flagged_netzentgelte or 0) + (flagged_hlzf or 0),
            },
        },
    )


@router.get("/flagged")
async def list_flagged_items(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Get all flagged records for review."""
    # Get flagged Netzentgelte with DNO info
    netz_query = (
        select(
            NetzentgelteModel.id,
            NetzentgelteModel.year,
            NetzentgelteModel.voltage_level,
            NetzentgelteModel.flag_reason,
            NetzentgelteModel.flagged_at,
            NetzentgelteModel.flagged_by,
            DNOModel.id.label("dno_id"),
            DNOModel.name.label("dno_name"),
            DNOModel.slug.label("dno_slug"),
        )
        .join(DNOModel, NetzentgelteModel.dno_id == DNOModel.id)
        .where(NetzentgelteModel.verification_status == "flagged")
        .order_by(NetzentgelteModel.flagged_at.desc())
    )
    netz_result = await db.execute(netz_query)
    netz_flagged = [
        {
            "id": row.id,
            "type": "netzentgelte",
            "year": row.year,
            "voltage_level": row.voltage_level,
            "flag_reason": row.flag_reason,
            "flagged_at": row.flagged_at.isoformat() if row.flagged_at else None,
            "flagged_by": row.flagged_by,
            "dno_id": row.dno_id,
            "dno_name": row.dno_name,
            "dno_slug": row.dno_slug,
        }
        for row in netz_result.all()
    ]

    # Get flagged HLZF with DNO info
    hlzf_query = (
        select(
            HLZFModel.id,
            HLZFModel.year,
            HLZFModel.voltage_level,
            HLZFModel.flag_reason,
            HLZFModel.flagged_at,
            HLZFModel.flagged_by,
            DNOModel.id.label("dno_id"),
            DNOModel.name.label("dno_name"),
            DNOModel.slug.label("dno_slug"),
        )
        .join(DNOModel, HLZFModel.dno_id == DNOModel.id)
        .where(HLZFModel.verification_status == "flagged")
        .order_by(HLZFModel.flagged_at.desc())
    )
    hlzf_result = await db.execute(hlzf_query)
    hlzf_flagged = [
        {
            "id": row.id,
            "type": "hlzf",
            "year": row.year,
            "voltage_level": row.voltage_level,
            "flag_reason": row.flag_reason,
            "flagged_at": row.flagged_at.isoformat() if row.flagged_at else None,
            "flagged_by": row.flagged_by,
            "dno_id": row.dno_id,
            "dno_name": row.dno_name,
            "dno_slug": row.dno_slug,
        }
        for row in hlzf_result.all()
    ]

    # Combine and sort by flagged_at
    all_flagged = netz_flagged + hlzf_flagged
    all_flagged.sort(key=lambda x: x["flagged_at"] or "", reverse=True)

    return APIResponse(
        success=True,
        data={
            "items": all_flagged,
            "total": len(all_flagged),
        },
    )


# ==============================================================================
# Cached Files & Bulk Extraction
# ==============================================================================

SUPPORTED_EXTENSIONS = {".pdf", ".html", ".htm", ".xlsx", ".xls", ".csv", ".docx"}


def _parse_file_info(file_path: Path, dno_slug: str) -> dict | None:
    """Parse file info from a cached file path.

    Expected format: {dno_slug}-{data_type}-{year}.{ext}
    Example: netze-bw-gmbh-netzentgelte-2024.pdf
    """
    name = file_path.name
    # Pattern: slug-datatype-year.ext
    pattern = rf"^{re.escape(dno_slug)}-(\w+)-(\d{{4}})\.(\w+)$"
    match = re.match(pattern, name)
    if not match:
        return None

    data_type = match.group(1)
    year = int(match.group(2))
    ext = match.group(3).lower()

    # Only accept known data types
    if data_type not in ("netzentgelte", "hlzf"):
        return None

    return {
        "name": name,
        "path": f"{dno_slug}/{name}",
        "dno_slug": dno_slug,
        "data_type": data_type,
        "year": year,
        "format": ext,
        "size": file_path.stat().st_size,
    }


@router.get("/files")
async def list_cached_files(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Get statistics about cached files and their extraction status.

    Scans the downloads directory and cross-references with database to show:
    - Total files, by data type, by format
    - Extraction status (no data, flagged, verified, unverified)
    """
    storage_path = settings.storage_path
    downloads_path = Path(storage_path) / "downloads"

    if not downloads_path.exists():
        return APIResponse(
            success=True,
            data={
                "total_files": 0,
                "files": [],
                "by_data_type": {"netzentgelte": 0, "hlzf": 0},
                "by_format": {},
                "by_status": {"no_data": 0, "flagged": 0, "verified": 0, "unverified": 0},
            },
        )

    # Get all DNO slugs for matching
    dno_query = select(DNOModel.id, DNOModel.slug, DNOModel.name)
    dno_result = await db.execute(dno_query)
    dnos = {row.slug: {"id": row.id, "name": row.name} for row in dno_result.all()}

    # Batch-load all verification statuses upfront (eliminates N+1 queries)
    netz_status_result = await db.execute(
        select(
            NetzentgelteModel.dno_id,
            NetzentgelteModel.year,
            NetzentgelteModel.verification_status,
        )
    )
    hlzf_status_result = await db.execute(
        select(
            HLZFModel.dno_id,
            HLZFModel.year,
            HLZFModel.verification_status,
        )
    )

    # Build lookup: (data_type, dno_id, year) -> list of statuses
    status_lookup: dict[tuple, list[str]] = {}
    for row in netz_status_result.all():
        key = ("netzentgelte", row[0], row[1])
        status_lookup.setdefault(key, []).append(row[2])
    for row in hlzf_status_result.all():
        key = ("hlzf", row[0], row[1])
        status_lookup.setdefault(key, []).append(row[2])

    files = []
    by_data_type = {"netzentgelte": 0, "hlzf": 0}
    by_format = {}
    by_status = {"no_data": 0, "flagged": 0, "verified": 0, "unverified": 0}

    # Scan all subdirectories (each is a DNO slug)
    for dno_dir in downloads_path.iterdir():
        if not dno_dir.is_dir():
            continue

        dno_slug = dno_dir.name
        dno_info = dnos.get(dno_slug)
        if not dno_info:
            continue  # Unknown DNO, skip

        for file_path in dno_dir.iterdir():
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue

            file_info = _parse_file_info(file_path, dno_slug)
            if not file_info:
                continue

            # Add DNO info
            file_info["dno_id"] = dno_info["id"]
            file_info["dno_name"] = dno_info["name"]

            # Look up extraction status from batch-loaded data
            statuses = status_lookup.get(
                (file_info["data_type"], dno_info["id"], file_info["year"]), []
            )

            if not statuses:
                file_info["extraction_status"] = "no_data"
                by_status["no_data"] += 1
            elif any(s == "verified" for s in statuses):
                file_info["extraction_status"] = "verified"
                by_status["verified"] += 1
            elif any(s == "flagged" for s in statuses):
                file_info["extraction_status"] = "flagged"
                by_status["flagged"] += 1
            else:
                file_info["extraction_status"] = "unverified"
                by_status["unverified"] += 1

            files.append(file_info)
            by_data_type[file_info["data_type"]] += 1
            by_format[file_info["format"]] = by_format.get(file_info["format"], 0) + 1

    # Sort files by DNO name, then year descending
    files.sort(key=lambda f: (f["dno_name"], -f["year"]))

    return APIResponse(
        success=True,
        data={
            "total_files": len(files),
            "files": files,
            "by_data_type": by_data_type,
            "by_format": by_format,
            "by_status": by_status,
        },
    )


class BulkExtractRequest(BaseModel):
    """Request model for bulk extraction."""

    mode: Literal["flagged_only", "default", "force_override", "no_data_and_failed"]
    data_types: list[str] = ["netzentgelte", "hlzf"]
    years: list[int] | None = None
    formats: list[str] | None = None  # Filter by file format (pdf, html, etc.)
    dno_ids: list[int] | None = None
    dry_run: bool = False  # If true, return preview without queueing


class BulkExtractPreview(BaseModel):
    """Preview of bulk extraction."""

    total_files: int
    will_extract: int
    protected_verified: int  # Files with verified data that WON'T be touched (unless force)
    failed_jobs: int  # Files with failed extraction jobs
    will_override_verified: int  # Files with verified data that WILL be overridden (force mode)
    flagged: int
    no_data: int
    unverified: int
    files: list[dict]


@router.post("/extract/preview")
async def preview_bulk_extract(
    request: BulkExtractRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Preview what a bulk extraction would do without queueing jobs.

    Returns counts of files that would be extracted based on mode:
    - flagged_only: Only files where existing data has verification_status = 'flagged'
    - default: Files with no data OR verification_status != 'verified'
    - force_override: ALL files (including verified)
    - no_data_and_failed: Only files with no data OR files with failed extraction jobs
    """
    storage_path = settings.storage_path
    downloads_path = Path(storage_path) / "downloads"

    if not downloads_path.exists():
        return APIResponse(
            success=True,
            data=BulkExtractPreview(
                total_files=0,
                will_extract=0,
                protected_verified=0,
                will_override_verified=0,
                flagged=0,
                no_data=0,
                unverified=0,
                failed_jobs=0,
                files=[],
            ).model_dump(),
        )

    # Get DNOs
    dno_query = select(DNOModel.id, DNOModel.slug, DNOModel.name)
    if request.dno_ids:
        dno_query = dno_query.where(DNOModel.id.in_(request.dno_ids))
    dno_result = await db.execute(dno_query)
    dnos = {row.slug: {"id": row.id, "name": row.name} for row in dno_result.all()}

    # Batch-load verification statuses upfront (eliminates N+1)
    netz_st = await db.execute(
        select(
            NetzentgelteModel.dno_id, NetzentgelteModel.year, NetzentgelteModel.verification_status
        )
    )
    hlzf_st = await db.execute(
        select(HLZFModel.dno_id, HLZFModel.year, HLZFModel.verification_status)
    )
    preview_status_lookup: dict[tuple, list[str]] = {}
    for row in netz_st.all():
        preview_status_lookup.setdefault(("netzentgelte", row[0], row[1]), []).append(row[2])
    for row in hlzf_st.all():
        preview_status_lookup.setdefault(("hlzf", row[0], row[1]), []).append(row[2])

    # Batch-load failed job markers
    failed_jobs_result = await db.execute(
        select(CrawlJobModel.dno_id, CrawlJobModel.year, CrawlJobModel.data_type)
        .where(CrawlJobModel.status == "failed")
        .distinct()
    )
    failed_job_set = {(row[0], row[1], row[2]) for row in failed_jobs_result.all()}

    total_files = 0
    will_extract = 0
    protected_verified = 0
    will_override_verified = 0
    flagged = 0
    no_data = 0
    unverified = 0
    failed_jobs = 0
    files_to_process = []

    for dno_dir in downloads_path.iterdir():
        if not dno_dir.is_dir():
            continue

        dno_slug = dno_dir.name
        dno_info = dnos.get(dno_slug)
        if not dno_info:
            continue

        for file_path in dno_dir.iterdir():
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue

            file_info = _parse_file_info(file_path, dno_slug)
            if not file_info:
                continue

            # Apply filters
            if file_info["data_type"] not in request.data_types:
                continue
            if request.years and file_info["year"] not in request.years:
                continue
            if request.formats and file_info["format"] not in request.formats:
                continue

            total_files += 1
            file_info["dno_id"] = dno_info["id"]
            file_info["dno_name"] = dno_info["name"]

            # Look up statuses from batch-loaded data
            statuses = preview_status_lookup.get(
                (file_info["data_type"], dno_info["id"], file_info["year"]), []
            )

            has_verified = any(s == "verified" for s in statuses)
            has_flagged = any(s == "flagged" for s in statuses)
            has_data = len(statuses) > 0
            has_failed_job = (
                dno_info["id"],
                file_info["year"],
                file_info["data_type"],
            ) in failed_job_set

            # Determine if this file should be extracted based on mode
            should_extract = False

            if request.mode == "flagged_only":
                if has_flagged:
                    should_extract = True
                    flagged += 1
            elif request.mode == "default":
                if not has_data:
                    should_extract = True
                    no_data += 1
                elif has_flagged:
                    should_extract = True
                    flagged += 1
                elif not has_verified:
                    should_extract = True
                    unverified += 1
                else:
                    protected_verified += 1
            elif request.mode == "force_override":
                should_extract = True
                if not has_data:
                    no_data += 1
                elif has_verified:
                    will_override_verified += 1
                elif has_flagged:
                    flagged += 1
                else:
                    unverified += 1
            elif request.mode == "no_data_and_failed":
                if not has_data:
                    should_extract = True
                    no_data += 1
                elif has_failed_job:
                    should_extract = True
                    failed_jobs += 1

            if should_extract:
                will_extract += 1
                file_info["will_extract"] = True
                file_info["has_verified"] = has_verified
                file_info["has_flagged"] = has_flagged
                file_info["has_data"] = has_data
                file_info["has_failed_job"] = has_failed_job
                files_to_process.append(file_info)

    return APIResponse(
        success=True,
        data={
            "total_files": total_files,
            "will_extract": will_extract,
            "protected_verified": protected_verified,
            "will_override_verified": will_override_verified,
            "flagged": flagged,
            "no_data": no_data,
            "unverified": unverified,
            "failed_jobs": failed_jobs,
            "files": files_to_process,
        },
    )


@router.post("/extract/bulk")
async def trigger_bulk_extract(
    request: BulkExtractRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Trigger bulk extraction jobs for cached files.

    Jobs are queued with lower priority (2) so they don't block regular jobs.

    Modes:
    - flagged_only: Only re-extract files where data is flagged
    - default: Extract files with no data, flagged, or unverified (skip verified)
    - force_override: Extract all files, including verified (adds force_override to context)
    - no_data_and_failed: Only files with no data OR files with failed extraction jobs
    """
    # First get the preview to know what to extract
    storage_path = settings.storage_path
    downloads_path = Path(storage_path) / "downloads"

    if not downloads_path.exists():
        return APIResponse(
            success=True,
            message="No files to extract",
            data={"jobs_queued": 0, "files_scanned": 0},
        )

    # Get DNOs
    dno_query = select(DNOModel.id, DNOModel.slug, DNOModel.name, DNOModel.website)
    if request.dno_ids:
        dno_query = dno_query.where(DNOModel.id.in_(request.dno_ids))
    dno_result = await db.execute(dno_query)
    dnos = {
        row.slug: {"id": row.id, "name": row.name, "website": row.website}
        for row in dno_result.all()
    }

    # Batch-load verification statuses upfront (eliminates N+1)
    bulk_netz_st = await db.execute(
        select(
            NetzentgelteModel.dno_id, NetzentgelteModel.year, NetzentgelteModel.verification_status
        )
    )
    bulk_hlzf_st = await db.execute(
        select(HLZFModel.dno_id, HLZFModel.year, HLZFModel.verification_status)
    )
    bulk_status_lookup: dict[tuple, list[str]] = {}
    for row in bulk_netz_st.all():
        bulk_status_lookup.setdefault(("netzentgelte", row[0], row[1]), []).append(row[2])
    for row in bulk_hlzf_st.all():
        bulk_status_lookup.setdefault(("hlzf", row[0], row[1]), []).append(row[2])

    # Batch-load failed job markers
    bulk_failed_result = await db.execute(
        select(CrawlJobModel.dno_id, CrawlJobModel.year, CrawlJobModel.data_type)
        .where(CrawlJobModel.status == "failed")
        .distinct()
    )
    bulk_failed_set = {(row[0], row[1], row[2]) for row in bulk_failed_result.all()}

    # Batch-load existing pending/running jobs
    active_jobs_result = await db.execute(
        select(CrawlJobModel.dno_id, CrawlJobModel.year, CrawlJobModel.data_type)
        .where(CrawlJobModel.status.in_(["pending", "running"]))
        .distinct()
    )
    active_jobs_set = {(row[0], row[1], row[2]) for row in active_jobs_result.all()}

    jobs_queued = 0
    files_scanned = 0
    jobs_to_enqueue = []

    # Connect to Redis for job queueing
    redis_pool = await create_pool(RedisSettings.from_dsn(str(settings.redis_url)))

    try:
        for dno_dir in downloads_path.iterdir():
            if not dno_dir.is_dir():
                continue

            dno_slug = dno_dir.name
            dno_info = dnos.get(dno_slug)
            if not dno_info:
                continue

            for file_path in dno_dir.iterdir():
                if not file_path.is_file():
                    continue
                if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                    continue

                file_info = _parse_file_info(file_path, dno_slug)
                if not file_info:
                    continue

                # Apply filters
                if file_info["data_type"] not in request.data_types:
                    continue
                if request.years and file_info["year"] not in request.years:
                    continue
                if request.formats and file_info["format"] not in request.formats:
                    continue

                files_scanned += 1

                # Look up statuses from batch-loaded data
                statuses = bulk_status_lookup.get(
                    (file_info["data_type"], dno_info["id"], file_info["year"]), []
                )
                has_verified = any(s == "verified" for s in statuses)
                has_flagged = any(s == "flagged" for s in statuses)
                has_data = len(statuses) > 0
                has_failed_job = (
                    dno_info["id"],
                    file_info["year"],
                    file_info["data_type"],
                ) in bulk_failed_set

                # Determine if this file should be extracted based on mode
                should_extract = False

                if request.mode == "flagged_only":
                    should_extract = has_flagged
                elif request.mode == "default":
                    should_extract = not has_data or has_flagged or not has_verified
                elif request.mode == "force_override":
                    should_extract = True
                elif request.mode == "no_data_and_failed":
                    should_extract = not has_data or has_failed_job

                if not should_extract:
                    continue

                # Check if there's already a pending/running job (from batch-loaded set)
                if (dno_info["id"], file_info["year"], file_info["data_type"]) in active_jobs_set:
                    logger.debug(
                        "job_already_exists", dno_id=dno_info["id"], year=file_info["year"]
                    )
                    continue

                # Create job context
                job_context = {
                    "downloaded_file": str(file_path),
                    "file_to_process": str(file_path),
                    "dno_slug": dno_slug,
                    "dno_name": dno_info["name"],
                    "dno_website": dno_info["website"],
                    "strategy": "use_cache",
                    "bulk_extract": True,  # Mark as bulk extract job
                    "force_override": request.mode == "force_override",
                    "initiated_by_admin": admin.email,
                }

                # Create job in database
                job = CrawlJobModel(
                    dno_id=dno_info["id"],
                    year=file_info["year"],
                    data_type=file_info["data_type"],
                    job_type="extract",
                    priority=BULK_EXTRACT_PRIORITY,
                    current_step=f"Bulk extract by {admin.email}",
                    triggered_by=admin.email,
                    context=job_context,
                )
                db.add(job)
                await db.flush()  # Get the job ID

                # Collect job for enqueueing after commit
                jobs_to_enqueue.append(
                    {
                        "id": job.id,
                        "job_id": f"bulk_extract_{job.id}",
                        "dno_slug": dno_slug,
                        "year": file_info["year"],
                        "data_type": file_info["data_type"],
                    }
                )

        # Commit all jobs to DB first
        await db.commit()

        # Now enqueue them to Redis
        for job_info in jobs_to_enqueue:
            await redis_pool.enqueue_job(
                "process_extract",
                job_info["id"],
                _job_id=job_info["job_id"],
                _queue_name="extract",
            )
            jobs_queued += 1
            logger.info(
                "bulk_extract_job_queued",
                job_id=job_info["id"],
                dno_slug=job_info["dno_slug"],
                year=job_info["year"],
                data_type=job_info["data_type"],
                mode=request.mode,
            )

    finally:
        await redis_pool.close()

    return APIResponse(
        success=True,
        message=f"Queued {jobs_queued} extraction jobs",
        data={
            "jobs_queued": jobs_queued,
            "files_scanned": files_scanned,
        },
    )


@router.get("/extract/bulk/status")
async def get_bulk_extract_status(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Get status of bulk extraction jobs (low priority jobs).

    Returns counts of pending, running, completed, and failed bulk extract jobs.
    """
    # Query jobs with bulk_extract priority
    pending = await db.scalar(
        select(func.count(CrawlJobModel.id)).where(
            and_(
                CrawlJobModel.priority == BULK_EXTRACT_PRIORITY,
                CrawlJobModel.status == "pending",
            )
        )
    )

    running = await db.scalar(
        select(func.count(CrawlJobModel.id)).where(
            and_(
                CrawlJobModel.priority == BULK_EXTRACT_PRIORITY,
                CrawlJobModel.status == "running",
            )
        )
    )

    completed = await db.scalar(
        select(func.count(CrawlJobModel.id)).where(
            and_(
                CrawlJobModel.priority == BULK_EXTRACT_PRIORITY,
                CrawlJobModel.status == "completed",
            )
        )
    )

    failed = await db.scalar(
        select(func.count(CrawlJobModel.id)).where(
            and_(
                CrawlJobModel.priority == BULK_EXTRACT_PRIORITY,
                CrawlJobModel.status == "failed",
            )
        )
    )

    total = (pending or 0) + (running or 0) + (completed or 0) + (failed or 0)

    return APIResponse(
        success=True,
        data={
            "total": total,
            "pending": pending or 0,
            "running": running or 0,
            "completed": completed or 0,
            "failed": failed or 0,
            "progress_percent": round((completed or 0) / total * 100, 1) if total > 0 else 0,
        },
    )


@router.post("/extract/bulk/cancel")
async def cancel_bulk_extract(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Cancel all pending bulk extraction jobs.

    Only cancels jobs that are still pending (not running or completed).
    """
    # Find all pending bulk extract jobs
    query = select(CrawlJobModel).where(
        and_(
            CrawlJobModel.priority == BULK_EXTRACT_PRIORITY,
            CrawlJobModel.status == "pending",
        )
    )
    result = await db.execute(query)
    pending_jobs = result.scalars().all()

    cancelled_count = 0
    for job in pending_jobs:
        job.status = "cancelled"
        job.error_message = f"Cancelled by admin: {admin.email}"
        job.completed_at = datetime.now(UTC)
        cancelled_count += 1

    await db.commit()

    logger.info(
        "bulk_extract_cancelled",
        cancelled_count=cancelled_count,
        admin=admin.email,
    )

    return APIResponse(
        success=True,
        message=f"Cancelled {cancelled_count} pending bulk extraction jobs",
        data={"cancelled": cancelled_count},
    )


@router.delete("/extract/bulk")
async def delete_bulk_extract_jobs(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Delete ALL bulk extraction jobs to reset progress.

    This effectively resets the 'Bulk Extraction Progress' bar.
    It deletes jobs with BULK_EXTRACT_PRIORITY (2).
    """
    # Delete all jobs with bulk priority
    query = select(CrawlJobModel).where(CrawlJobModel.priority == BULK_EXTRACT_PRIORITY)
    result = await db.execute(query)
    jobs = result.scalars().all()

    deleted_count = 0
    for job in jobs:
        await db.delete(job)
        deleted_count += 1

    await db.commit()

    logger.info(
        "bulk_extract_reset",
        deleted_count=deleted_count,
        admin=admin.email,
    )

    return APIResponse(
        success=True,
        message=f"Deleted {deleted_count} bulk extraction jobs",
        data={"deleted": deleted_count},
    )


# ==============================================================================
# NOTE: AI Configuration endpoints moved to /app/api/routes/ai.py
# See /api/v1/ai/* for provider management
# ==============================================================================
