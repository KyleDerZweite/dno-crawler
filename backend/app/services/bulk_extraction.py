"""Shared bulk extraction helpers for admin endpoints."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arq import create_pool
from arq.connections import RedisSettings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import CrawlJobModel, HLZFModel, NetzentgelteModel


@dataclass
class BulkCandidate:
    """A scanned cached file candidate with DB-derived status metadata."""

    dno_info: dict[str, Any]
    file_info: dict[str, Any]
    file_path: Path
    has_verified: bool
    has_flagged: bool
    has_data: bool
    has_failed_job: bool


async def build_verification_status_lookup(
    db: AsyncSession,
) -> dict[tuple[str, int, int], list[str]]:
    """Build status lookup for (data_type, dno_id, year)."""
    netz_rows = await db.execute(
        select(
            NetzentgelteModel.dno_id, NetzentgelteModel.year, NetzentgelteModel.verification_status
        )
    )
    hlzf_rows = await db.execute(
        select(HLZFModel.dno_id, HLZFModel.year, HLZFModel.verification_status)
    )

    status_lookup: dict[tuple[str, int, int], list[str]] = {}
    for row in netz_rows.all():
        status_lookup.setdefault(("netzentgelte", row[0], row[1]), []).append(row[2])
    for row in hlzf_rows.all():
        status_lookup.setdefault(("hlzf", row[0], row[1]), []).append(row[2])
    return status_lookup


async def build_failed_job_set(db: AsyncSession) -> set[tuple[int, int, str]]:
    """Build lookup of (dno_id, year, data_type) tuples with failed jobs."""
    failed_rows = await db.execute(
        select(CrawlJobModel.dno_id, CrawlJobModel.year, CrawlJobModel.data_type)
        .where(CrawlJobModel.status == "failed")
        .distinct()
    )
    return {(row[0], row[1], row[2]) for row in failed_rows.all()}


async def build_active_job_set(db: AsyncSession) -> set[tuple[int, int, str]]:
    """Build lookup of (dno_id, year, data_type) tuples with pending/running jobs."""
    active_rows = await db.execute(
        select(CrawlJobModel.dno_id, CrawlJobModel.year, CrawlJobModel.data_type)
        .where(CrawlJobModel.status.in_(["pending", "running"]))
        .distinct()
    )
    return {(row[0], row[1], row[2]) for row in active_rows.all()}


def _mode_allows_extraction(
    *,
    mode: str,
    has_data: bool,
    has_verified: bool,
    has_flagged: bool,
    has_failed_job: bool,
) -> bool:
    if mode == "flagged_only":
        return has_flagged
    if mode == "default":
        return (not has_data) or has_flagged or (not has_verified)
    if mode == "force_override":
        return True
    if mode == "no_data_and_failed":
        return (not has_data) or has_failed_job
    return False


def scan_bulk_candidates(
    *,
    downloads_path: Path,
    dnos: dict[str, dict[str, Any]],
    parse_file_info: Callable[[Path, str], dict | None],
    supported_extensions: set[str],
    data_types: list[str],
    years: list[int] | None,
    formats: list[str] | None,
    mode: str,
    status_lookup: dict[tuple[str, int, int], list[str]],
    failed_job_set: set[tuple[int, int, str]],
) -> list[BulkCandidate]:
    """Scan file cache and return candidates eligible for extraction for the given mode."""
    candidates: list[BulkCandidate] = []

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
            if file_path.suffix.lower() not in supported_extensions:
                continue

            file_info = parse_file_info(file_path, dno_slug)
            if not file_info:
                continue

            if file_info["data_type"] not in data_types:
                continue
            if years and file_info["year"] not in years:
                continue
            if formats and file_info["format"] not in formats:
                continue

            statuses = status_lookup.get(
                (file_info["data_type"], dno_info["id"], file_info["year"]),
                [],
            )
            has_verified = any(s == "verified" for s in statuses)
            has_flagged = any(s == "flagged" for s in statuses)
            has_data = len(statuses) > 0
            has_failed_job = (
                dno_info["id"],
                file_info["year"],
                file_info["data_type"],
            ) in failed_job_set

            if not _mode_allows_extraction(
                mode=mode,
                has_data=has_data,
                has_verified=has_verified,
                has_flagged=has_flagged,
                has_failed_job=has_failed_job,
            ):
                continue

            candidates.append(
                BulkCandidate(
                    dno_info=dno_info,
                    file_info=file_info,
                    file_path=file_path,
                    has_verified=has_verified,
                    has_flagged=has_flagged,
                    has_data=has_data,
                    has_failed_job=has_failed_job,
                )
            )

    return candidates


async def create_bulk_extract_jobs(
    *,
    db: AsyncSession,
    candidates: Iterable[BulkCandidate],
    active_job_set: set[tuple[int, int, str]],
    admin_email: str,
    priority: int,
    force_override: bool,
) -> tuple[list[dict[str, Any]], int]:
    """Create CrawlJobModel rows for selected candidates and return enqueue payloads."""
    jobs_to_enqueue: list[dict[str, Any]] = []
    files_scanned = 0

    for candidate in candidates:
        files_scanned += 1

        dno_id = candidate.dno_info["id"]
        year = candidate.file_info["year"]
        data_type = candidate.file_info["data_type"]

        if (dno_id, year, data_type) in active_job_set:
            continue

        job_context = {
            "downloaded_file": str(candidate.file_path),
            "file_to_process": str(candidate.file_path),
            "dno_slug": candidate.file_info["dno_slug"],
            "dno_name": candidate.dno_info["name"],
            "dno_website": candidate.dno_info.get("website"),
            "strategy": "use_cache",
            "bulk_extract": True,
            "force_override": force_override,
            "initiated_by_admin": admin_email,
        }

        job = CrawlJobModel(
            dno_id=dno_id,
            year=year,
            data_type=data_type,
            job_type="extract",
            priority=priority,
            current_step=f"Bulk extract by {admin_email}",
            triggered_by=admin_email,
            context=job_context,
        )
        db.add(job)
        await db.flush()

        jobs_to_enqueue.append(
            {
                "id": job.id,
                "job_id": f"bulk_extract_{job.id}",
                "dno_slug": candidate.file_info["dno_slug"],
                "year": year,
                "data_type": data_type,
            }
        )

    return jobs_to_enqueue, files_scanned


async def enqueue_extract_jobs(redis_url: str, jobs_to_enqueue: list[dict[str, Any]]) -> int:
    """Enqueue extract jobs to Redis/ARQ queue."""
    queued = 0
    redis_pool = await create_pool(RedisSettings.from_dsn(redis_url))
    try:
        for job_info in jobs_to_enqueue:
            await redis_pool.enqueue_job(
                "process_extract",
                job_info["id"],
                _job_id=job_info["job_id"],
                _queue_name="extract",
            )
            queued += 1
    finally:
        await redis_pool.close()
    return queued
