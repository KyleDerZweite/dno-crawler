"""
Admin routes - requires admin role.

User management has been moved to Zitadel.
This module only contains job management and data normalization routes.
"""

import os
import re
from datetime import datetime
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
        select(func.count(NetzentgelteModel.id)).where(NetzentgelteModel.verification_status == "flagged")
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
        "path": str(file_path),
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
    storage_path = os.environ.get("STORAGE_PATH", "/data")
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

            # Check extraction status in database
            if file_info["data_type"] == "netzentgelte":
                status_query = select(NetzentgelteModel.verification_status).where(
                    and_(
                        NetzentgelteModel.dno_id == dno_info["id"],
                        NetzentgelteModel.year == file_info["year"],
                    )
                )
            else:
                status_query = select(HLZFModel.verification_status).where(
                    and_(
                        HLZFModel.dno_id == dno_info["id"],
                        HLZFModel.year == file_info["year"],
                    )
                )

            status_result = await db.execute(status_query)
            statuses = [row[0] for row in status_result.all()]

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
    storage_path = os.environ.get("STORAGE_PATH", "/data")
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

            # Check extraction status
            if file_info["data_type"] == "netzentgelte":
                status_query = select(NetzentgelteModel.verification_status).where(
                    and_(
                        NetzentgelteModel.dno_id == dno_info["id"],
                        NetzentgelteModel.year == file_info["year"],
                    )
                )
            else:
                status_query = select(HLZFModel.verification_status).where(
                    and_(
                        HLZFModel.dno_id == dno_info["id"],
                        HLZFModel.year == file_info["year"],
                    )
                )

            status_result = await db.execute(status_query)
            statuses = [row[0] for row in status_result.all()]

            has_verified = any(s == "verified" for s in statuses)
            has_flagged = any(s == "flagged" for s in statuses)
            has_data = len(statuses) > 0

            # Check if there's a failed job for this file
            failed_job_query = select(CrawlJobModel.id).where(
                and_(
                    CrawlJobModel.dno_id == dno_info["id"],
                    CrawlJobModel.year == file_info["year"],
                    CrawlJobModel.data_type == file_info["data_type"],
                    CrawlJobModel.status == "failed",
                )
            ).limit(1)
            has_failed_job = await db.scalar(failed_job_query) is not None

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
    storage_path = os.environ.get("STORAGE_PATH", "/data")
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
    dnos = {row.slug: {"id": row.id, "name": row.name, "website": row.website} for row in dno_result.all()}

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

                # Check extraction status to determine if we should queue
                if file_info["data_type"] == "netzentgelte":
                    status_query = select(NetzentgelteModel.verification_status).where(
                        and_(
                            NetzentgelteModel.dno_id == dno_info["id"],
                            NetzentgelteModel.year == file_info["year"],
                        )
                    )
                else:
                    status_query = select(HLZFModel.verification_status).where(
                        and_(
                            HLZFModel.dno_id == dno_info["id"],
                            HLZFModel.year == file_info["year"],
                        )
                    )

                status_result = await db.execute(status_query)
                statuses = [row[0] for row in status_result.all()]

                has_verified = any(s == "verified" for s in statuses)
                has_flagged = any(s == "flagged" for s in statuses)
                has_data = len(statuses) > 0

                # Check if there's a failed job for this file (for no_data_and_failed mode)
                has_failed_job = False
                if request.mode == "no_data_and_failed":
                    failed_job_query = select(CrawlJobModel.id).where(
                        and_(
                            CrawlJobModel.dno_id == dno_info["id"],
                            CrawlJobModel.year == file_info["year"],
                            CrawlJobModel.data_type == file_info["data_type"],
                            CrawlJobModel.status == "failed",
                        )
                    ).limit(1)
                    has_failed_job = await db.scalar(failed_job_query) is not None

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

                # Check if there's already a pending/running job for this DNO+year+type
                existing_job_query = select(CrawlJobModel.id).where(
                    and_(
                        CrawlJobModel.dno_id == dno_info["id"],
                        CrawlJobModel.year == file_info["year"],
                        CrawlJobModel.data_type == file_info["data_type"],
                        CrawlJobModel.status.in_(["pending", "running"]),
                    )
                )
                existing_job = await db.scalar(existing_job_query)
                if existing_job:
                    logger.debug("job_already_exists", dno_id=dno_info["id"], year=file_info["year"])
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
                jobs_to_enqueue.append({
                    "id": job.id,
                    "job_id": f"bulk_extract_{job.id}",
                    "dno_slug": dno_slug,
                    "year": file_info["year"],
                    "data_type": file_info["data_type"]
                })

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
        job.completed_at = datetime.utcnow()
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
    query = select(CrawlJobModel).where(
        CrawlJobModel.priority == BULK_EXTRACT_PRIORITY
    )
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
# AI Configuration
# ==============================================================================


class AIConfigCreate(BaseModel):
    """Request model for creating AI provider config."""
    name: str
    provider_type: Literal["openai", "google", "anthropic", "openrouter", "litellm", "custom"]
    auth_type: Literal["api_key", "oauth", "cli"] = "api_key"
    model: str
    api_key: str | None = None
    api_url: str | None = None
    supports_text: bool = True
    supports_vision: bool = False
    supports_files: bool = False


class AIConfigUpdate(BaseModel):
    """Request model for updating AI provider config."""
    name: str | None = None
    model: str | None = None
    api_key: str | None = None
    api_url: str | None = None
    supports_text: bool | None = None
    supports_vision: bool | None = None
    supports_files: bool | None = None
    is_enabled: bool | None = None


class AIConfigReorder(BaseModel):
    """Request model for reordering AI configs."""
    config_ids: list[int]


@router.get("/ai-config")
async def list_ai_configs(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """List all AI provider configurations."""
    from app.services.ai.config_service import AIConfigService

    service = AIConfigService(db)
    configs = await service.list_all()

    # Transform to response format (don't expose encrypted secrets)
    items = []
    for config in configs:
        items.append({
            "id": config.id,
            "name": config.name,
            "provider_type": config.provider_type,
            "auth_type": config.auth_type,
            "model": config.model,
            "api_url": config.api_url,
            "has_api_key": bool(config.api_key_encrypted),
            "has_oauth": bool(config.oauth_refresh_token_encrypted),
            "supports_text": config.supports_text,
            "supports_vision": config.supports_vision,
            "supports_files": config.supports_files,
            "is_enabled": config.is_enabled,
            "priority": config.priority,
            "status": config.status_display,
            "is_subscription": config.is_subscription,
            "last_success_at": config.last_success_at.isoformat() if config.last_success_at else None,
            "last_error_at": config.last_error_at.isoformat() if config.last_error_at else None,
            "last_error_message": config.last_error_message,
            "consecutive_failures": config.consecutive_failures,
            "total_requests": config.total_requests,
            "total_tokens_used": config.total_tokens_used,
            "created_at": config.created_at.isoformat() if config.created_at else None,
        })

    return APIResponse(
        success=True,
        data={"configs": items, "total": len(items)},
    )


@router.post("/ai-config")
async def create_ai_config(
    request: AIConfigCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Create a new AI provider configuration."""
    from app.services.ai.config_service import AIConfigService

    service = AIConfigService(db)

    config = await service.create(
        name=request.name,
        provider_type=request.provider_type,
        auth_type=request.auth_type,
        model=request.model,
        api_key=request.api_key,
        api_url=request.api_url,
        supports_text=request.supports_text,
        supports_vision=request.supports_vision,
        supports_files=request.supports_files,
        created_by=admin.id,
    )

    await db.commit()

    return APIResponse(
        success=True,
        message=f"Created AI provider config: {config.name}",
        data={"id": config.id},
    )


@router.patch("/ai-config/{config_id}")
async def update_ai_config(
    config_id: int,
    request: AIConfigUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Update an AI provider configuration."""
    from app.services.ai.config_service import AIConfigService

    service = AIConfigService(db)

    config = await service.update(
        config_id=config_id,
        name=request.name,
        model=request.model,
        api_key=request.api_key,
        api_url=request.api_url,
        supports_text=request.supports_text,
        supports_vision=request.supports_vision,
        supports_files=request.supports_files,
        is_enabled=request.is_enabled,
        modified_by=admin.id,
    )

    if not config:
        return APIResponse(
            success=False,
            message="Configuration not found",
        )

    await db.commit()

    return APIResponse(
        success=True,
        message=f"Updated AI provider config: {config.name}",
    )


@router.delete("/ai-config/{config_id}")
async def delete_ai_config(
    config_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Delete an AI provider configuration."""
    from app.services.ai.config_service import AIConfigService

    service = AIConfigService(db)
    deleted = await service.delete(config_id)

    if not deleted:
        return APIResponse(
            success=False,
            message="Configuration not found",
        )

    await db.commit()

    return APIResponse(
        success=True,
        message="AI provider config deleted",
    )


@router.post("/ai-config/reorder")
async def reorder_ai_configs(
    request: AIConfigReorder,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Reorder AI provider configurations (for fallback priority)."""
    from app.services.ai.config_service import AIConfigService

    service = AIConfigService(db)
    await service.reorder(request.config_ids)
    await db.commit()

    return APIResponse(
        success=True,
        message="Provider order updated",
    )


@router.post("/ai-config/{config_id}/test")
async def test_ai_config(
    config_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Test an AI provider configuration."""
    from app.services.ai.gateway import AIGateway

    gateway = AIGateway(db)
    result = await gateway.test_provider(config_id)

    return APIResponse(
        success=result.get("success", False),
        message=result.get("message") or result.get("error"),
        data=result,
    )


class AIConfigTestRequest(BaseModel):
    """Request to test an AI configuration before saving."""
    provider_type: str
    auth_type: str = "api_key"  # "api_key" or "cli"
    model: str
    api_key: str | None = None
    api_url: str | None = None


@router.post("/ai-config/test")
async def test_ai_config_preview(
    request: AIConfigTestRequest,
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Test an AI provider configuration BEFORE saving it.

    Sends a quick test message to verify the credentials work.
    """
    import time
    from types import SimpleNamespace

    from app.services.ai.gateway import PROVIDER_CLASSES

    start_time = time.time()

    try:
        # Get the provider class
        provider_class = PROVIDER_CLASSES.get(request.provider_type)
        if not provider_class:
            return APIResponse(
                success=False,
                message=f"Unknown provider type: {request.provider_type}",
            )

        # Create a mock config object mimicking AIProviderConfigModel
        mock_config = SimpleNamespace(
            id=0,
            name="Test Config",
            provider_type=request.provider_type,
            model=request.model,
            api_key_encrypted=request.api_key,  # Will be treated as plain text in test
            api_url=request.api_url,
            auth_type=request.auth_type,
            is_subscription=(request.auth_type == "cli"),
            supports_vision=True,
            supports_files=True,
            supports_text=True,
            is_enabled=True,
            oauth_refresh_token_encrypted=None,
        )

        # Create provider instance
        provider = provider_class(mock_config)

        # Override the API key decryption for testing (use plain key)
        if request.api_key:
            provider.api_key = request.api_key

        # Run health check (sends test message)
        is_healthy = await provider.health_check()

        elapsed_ms = int((time.time() - start_time) * 1000)

        if is_healthy:
            return APIResponse(
                success=True,
                message=f"Connection successful! Model responded in {elapsed_ms}ms",
                data={
                    "model": request.model,
                    "response": "OK",
                    "elapsed_ms": elapsed_ms,
                },
            )
        else:
            return APIResponse(
                success=False,
                message=f"Health check failed after {elapsed_ms}ms",
                data={
                    "model": request.model,
                    "elapsed_ms": elapsed_ms,
                },
            )

    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.warning("ai_config_test_failed", error=str(e), provider=request.provider_type)
        return APIResponse(
            success=False,
            message=f"Connection failed: {e!s}",
            data={
                "model": request.model,
                "elapsed_ms": elapsed_ms,
                "error": str(e),
            },
        )


@router.get("/ai-config/models/{provider_type}")
async def list_provider_models(
    provider_type: str,
    admin: Annotated[AuthUser, Depends(require_admin)],
    query: str | None = None,
    supports_vision: bool | None = None,
    supports_files: bool | None = None,
    limit: int = 25,
) -> APIResponse:
    """List available models for a provider.

    Two-stage approach:
    - Without query: Returns curated/suggested models (FALLBACK_MODELS)
    - With query: Searches the full models.dev registry

    This optimizes the UI by showing recommended models first, then
    enabling fuzzy search against the full registry when user types.
    """
    from app.services.ai.config_service import AIConfigService, get_models_registry_status

    default_url = AIConfigService.get_default_url(provider_type)
    registry_status = get_models_registry_status()

    # If no query provided, return suggested models only
    if not query:
        models = AIConfigService.get_suggested_models(provider_type)
        return APIResponse(
            success=True,
            data={
                "provider": provider_type,
                "models": models,
                "default_url": default_url,
                "custom_model_supported": True,
                "registry_status": registry_status,
                "source": "suggested",
            },
        )

    # With query, search the full registry
    models = await AIConfigService.search_models_for_provider(
        provider_type=provider_type,
        query=query,
        supports_vision=supports_vision,
        supports_files=supports_files,
        limit=limit,
    )

    return APIResponse(
        success=True,
        data={
            "provider": provider_type,
            "models": models,
            "default_url": default_url,
            "custom_model_supported": True,
            "registry_status": registry_status,
            "source": "search",
            "query": query,
        },
    )


@router.post("/ai-config/models/refresh")
async def refresh_models_registry(
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Refresh the models registry from models.dev API."""
    from app.services.ai.config_service import refresh_models_registry as do_refresh

    success = await do_refresh()

    if success:
        return APIResponse(
            success=True,
            message="Models registry refreshed successfully",
        )
    else:
        return APIResponse(
            success=False,
            message="Failed to refresh models registry",
        )


@router.get("/ai-config/status")
async def get_ai_status(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Get overall AI configuration status."""
    from app.services.ai.config_service import AIConfigService

    service = AIConfigService(db)
    all_configs = await service.list_all()
    enabled_configs = await service.list_enabled()
    active_config = await service.get_active_config()

    return APIResponse(
        success=True,
        data={
            "ai_enabled": len(enabled_configs) > 0,
            "total_configs": len(all_configs),
            "enabled_configs": len(enabled_configs),
            "active_provider": {
                "id": active_config.id,
                "name": active_config.name,
                "provider_type": active_config.provider_type,
                "model": active_config.model,
            } if active_config else None,
        },
    )

