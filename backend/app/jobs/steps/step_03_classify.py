"""
Step 03: Classify Documents

Post-download classification step that runs cheap regex extractors
on all downloaded files to identify which contain netzentgelte and/or hlzf data.

Algorithm:
1. For each downloaded file, run netzentgelte and hlzf extractors
2. Record extraction results (record count, pass/fail) per type
3. Pick best candidate per type (highest valid record count)
4. Move winning files from bulk-data/ to downloads/ with canonical naming
5. If nothing classified and first pass, set deepen_crawl flag

Output stored in job.context:
- classified_files: {data_type: {path, format, record_count, source_url}}
- unclassified_files: list of files that didn't match any type
- deepen_crawl: True if classify found nothing and deeper crawl should be tried
"""

import asyncio
import shutil
from pathlib import Path

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import CrawlJobModel
from app.jobs.steps.base import BaseStep

logger = structlog.get_logger()


class ClassifyStep(BaseStep):
    label = "Classifying Documents"
    description = "Running regex extractors to identify data in downloaded documents..."

    async def run(self, db: AsyncSession, job: CrawlJobModel) -> str:
        ctx = job.context or {}
        dno_slug = ctx.get("dno_slug", "unknown")
        log = logger.bind(dno=dno_slug, year=job.year)

        downloaded_files = ctx.get("downloaded_files", [])
        if not downloaded_files:
            ctx["classified_files"] = {}
            ctx["unclassified_files"] = []
            job.context = ctx
            await db.commit()
            return "No files to classify"

        # Track best candidate per data type
        best: dict[str, dict] = {}  # {data_type: {path, format, record_count, source_url}}
        unclassified: list[dict] = []

        for file_info in downloaded_files:
            file_path = Path(file_info["path"])
            file_format = file_info["format"]
            source_url = file_info.get("url", "")

            if not file_path.exists():
                log.warning("classify_file_missing", path=str(file_path))
                continue

            # Run extractors on this file
            netz_count = await self._try_netzentgelte(file_path, file_format, job.year)
            hlzf_count = await self._try_hlzf(file_path, file_format, job.year)

            log.debug(
                "classify_result",
                file=file_path.name,
                format=file_format,
                netz_records=netz_count,
                hlzf_records=hlzf_count,
            )

            classified = False

            # Check netzentgelte (need >= 2 records with valid prices)
            if netz_count >= 2:
                if "netzentgelte" not in best or netz_count > best["netzentgelte"]["record_count"]:
                    best["netzentgelte"] = {
                        "path": str(file_path),
                        "format": file_format,
                        "record_count": netz_count,
                        "source_url": source_url,
                    }
                classified = True

            # Check hlzf (need >= 2 voltage levels)
            if hlzf_count >= 2:
                if "hlzf" not in best or hlzf_count > best["hlzf"]["record_count"]:
                    best["hlzf"] = {
                        "path": str(file_path),
                        "format": file_format,
                        "record_count": hlzf_count,
                        "source_url": source_url,
                    }
                classified = True

            if not classified:
                unclassified.append(
                    {
                        "path": str(file_path),
                        "format": file_format,
                        "url": source_url,
                        "netz_records": netz_count,
                        "hlzf_records": hlzf_count,
                    }
                )

        # Move winning files to downloads/ with canonical naming
        downloads_dir = Path(settings.downloads_path) / dno_slug
        downloads_dir.mkdir(parents=True, exist_ok=True)

        for data_type, info in best.items():
            src = Path(info["path"])
            ext = src.suffix or f".{info['format']}"
            canonical_name = f"{dno_slug}-{data_type}-{job.year}{ext}"
            dest = downloads_dir / canonical_name

            try:
                await asyncio.to_thread(shutil.copy2, str(src), str(dest))
                info["path"] = str(dest)
                log.info(
                    "classified_file_moved",
                    data_type=data_type,
                    src=src.name,
                    dest=canonical_name,
                    records=info["record_count"],
                )
            except Exception as e:
                log.warning("classify_move_failed", error=str(e), src=str(src))
                # Keep original path if move fails

        # Check if we should deepen the crawl
        crawl_pass = ctx.get("crawl_pass", 1)
        if not best and crawl_pass == 1:
            ctx["deepen_crawl"] = True
            log.info(
                "classify_nothing_found",
                files_checked=len(downloaded_files),
                triggering_deeper_crawl=True,
            )

        ctx["classified_files"] = best
        ctx["unclassified_files"] = unclassified
        job.context = ctx
        await db.commit()

        # Build result message
        parts = []
        for dt, info in best.items():
            parts.append(f"{dt}: {info['record_count']} records")

        if parts:
            return f"Classified: {', '.join(parts)} ({len(unclassified)} unclassified)"

        if ctx.get("deepen_crawl"):
            return f"No data found in {len(downloaded_files)} files - will deepen crawl"

        return f"No data found in {len(downloaded_files)} files"

    async def _try_netzentgelte(self, file_path: Path, file_format: str, year: int) -> int:
        """Try extracting netzentgelte data, return valid record count."""
        try:
            if file_format == "pdf":
                from app.services.extraction.pdf_extractor import extract_netzentgelte_from_pdf

                records = await asyncio.to_thread(extract_netzentgelte_from_pdf, file_path)
            elif file_format in ("html", "htm"):
                # No HTML parser for netzentgelte yet, return 0
                return 0
            else:
                return 0

            # Sanity check: count records with valid price values
            valid = 0
            for record in records:
                values = [
                    record.get("leistung"),
                    record.get("arbeit"),
                    record.get("leistung_unter_2500h"),
                    record.get("arbeit_unter_2500h"),
                ]
                if any(self._is_valid_value(v) for v in values):
                    valid += 1

            return valid
        except Exception as e:
            logger.debug("netzentgelte_extract_failed", file=file_path.name, error=str(e))
            return 0

    async def _try_hlzf(self, file_path: Path, file_format: str, year: int) -> int:
        """Try extracting hlzf data, return valid record count."""
        try:
            if file_format == "pdf":
                from app.services.extraction.pdf_extractor import extract_hlzf_from_pdf

                records = await asyncio.to_thread(extract_hlzf_from_pdf, file_path)
            elif file_format in ("html", "htm"):
                from app.services.extraction.html_extractor import extract_hlzf_from_html

                html_content = await asyncio.to_thread(
                    file_path.read_text, encoding="utf-8", errors="replace"
                )
                records = extract_hlzf_from_html(html_content, year)
            else:
                return 0

            return len(records)
        except Exception as e:
            logger.debug("hlzf_extract_failed", file=file_path.name, error=str(e))
            return 0

    @staticmethod
    def _is_valid_value(v) -> bool:
        """Check if an extracted value is a real (non-placeholder) value."""
        if v is None:
            return False
        v_str = str(v).strip().lower()
        return v_str not in ("-", "n/a", "null", "none", "")
