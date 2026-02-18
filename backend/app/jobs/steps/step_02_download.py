"""
Step 02: Bulk Download

Downloads ALL candidate URLs to bulk-data/{dno_slug}/.

What it does:
- Download each candidate URL sequentially
- Store files in data/bulk-data/{dno_slug}/
- Track downloads in ctx["downloaded_files"]
- Limits: max 30 files, max 50MB per file, max 200MB total
- Individual failures logged as warnings, step fails only if zero files downloaded

File storage convention:
    data/bulk-data/
    ├── westnetz/
    │   ├── westnetz_00_a1b2c3d4.pdf
    │   ├── westnetz_01_e5f6g7h8.xlsx
    │   └── westnetz_02_i9j0k1l2.html
    └── rheinnetz/
        └── rheinnetz_00_m3n4o5p6.pdf

Output stored in job.context:
- downloaded_files: list of {path, format, url, size_bytes}
"""

import asyncio
import hashlib
from pathlib import Path

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import CrawlJobModel
from app.jobs.steps.base import BaseStep, StepError

logger = structlog.get_logger()

# Limits
MAX_FILES = 30
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB per file
MAX_TOTAL_SIZE = 200 * 1024 * 1024  # 200MB total

# Magic bytes for file format detection
MAGIC_BYTES = {
    b"%PDF": "pdf",
    b"\xd0\xcf\x11\xe0": "xls",
}


class DownloadStep(BaseStep):
    label = "Downloading"
    description = "Downloading candidate files to local storage..."

    async def run(self, db: AsyncSession, job: CrawlJobModel) -> str:
        ctx = job.context or {}
        dno_slug = ctx.get("dno_slug", "unknown")
        log = logger.bind(dno=dno_slug)

        # Check for cache-hit fast path
        cached_files = ctx.get("cached_files", {})
        candidates = ctx.get("candidate_urls", [])

        # If we only have cached files and no candidates, use cache
        if not candidates and cached_files:
            downloaded = []
            for _dt, path_str in cached_files.items():
                path = Path(path_str)
                if path.exists():
                    downloaded.append(
                        {
                            "path": str(path),
                            "format": self._detect_format_from_url(str(path)),
                            "url": f"cache://{path.name}",
                            "size_bytes": path.stat().st_size,
                        }
                    )
            ctx["downloaded_files"] = downloaded
            ctx["strategy"] = "use_cache"
            job.context = ctx
            await db.commit()
            return f"Using {len(downloaded)} cached files"

        if not candidates:
            raise StepError("No candidate URLs to download - discovery step may have failed")

        # Build save directory (path traversal protection)
        base_dir = Path(settings.storage_path) / "bulk-data"
        save_dir = base_dir / dno_slug
        if not save_dir.resolve().is_relative_to(base_dir.resolve()):
            raise StepError(f"Invalid slug for path construction: {dno_slug}")
        save_dir.mkdir(parents=True, exist_ok=True)

        downloaded: list[dict] = []
        total_bytes = 0
        failed = 0

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0),
            follow_redirects=True,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        ) as client:
            for idx, candidate in enumerate(candidates[:MAX_FILES]):
                url = candidate["url"]

                if total_bytes >= MAX_TOTAL_SIZE:
                    log.warning("total_size_limit_reached", total_bytes=total_bytes)
                    break

                try:
                    content, content_type, file_size = await self._stream_download(client, url, log)
                except Exception as e:
                    log.warning("download_failed", url=url[:80], error=str(e))
                    failed += 1
                    continue

                if not content:
                    failed += 1
                    continue

                total_bytes += file_size

                # Detect format
                file_format = self._detect_format(content, content_type, url)
                ext = self._format_to_ext(file_format)

                # Build filename: {slug}_{index}_{url_hash}.{ext}
                url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
                filename = f"{dno_slug}_{idx:02d}_{url_hash}.{ext}"
                save_path = save_dir / filename

                # Save file
                await asyncio.to_thread(save_path.write_bytes, content)

                downloaded.append(
                    {
                        "path": str(save_path),
                        "format": file_format,
                        "url": url,
                        "size_bytes": file_size,
                    }
                )

                log.debug(
                    "file_downloaded",
                    url=url[:60],
                    format=file_format,
                    size_kb=file_size // 1024,
                    index=idx,
                )

        ctx["downloaded_files"] = downloaded
        job.context = ctx
        await db.commit()

        if not downloaded:
            raise StepError(
                f"All {failed} download attempts failed for {dno_slug}. "
                f"Tried {len(candidates[:MAX_FILES])} candidates."
            )

        return (
            f"Downloaded {len(downloaded)} files ({total_bytes // 1024} KB total, {failed} failed)"
        )

    async def _stream_download(
        self,
        client: httpx.AsyncClient,
        url: str,
        log: structlog.stdlib.BoundLogger,
        max_retries: int = 2,
    ) -> tuple[bytes, str, int]:
        """Stream download with size limit and retries."""
        from app.services.retry_utils import RETRYABLE_EXCEPTIONS

        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                async with client.stream("GET", url) as response:
                    if response.status_code == 429:
                        retry_after = response.headers.get("retry-after", "5")
                        wait_time = min(float(retry_after), 15.0)
                        await asyncio.sleep(wait_time)
                        continue

                    if response.status_code >= 400:
                        return b"", "", 0

                    response.raise_for_status()

                    content_type = response.headers.get("content-type", "")
                    content_length = response.headers.get("content-length")

                    if content_length and int(content_length) > MAX_FILE_SIZE:
                        log.debug("file_too_large", url=url[:60], size=content_length)
                        return b"", "", 0

                    chunks = []
                    total_size = 0
                    async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                        total_size += len(chunk)
                        if total_size > MAX_FILE_SIZE:
                            log.debug("file_too_large_streaming", url=url[:60])
                            return b"", "", 0
                        chunks.append(chunk)

                    return b"".join(chunks), content_type, total_size

            except RETRYABLE_EXCEPTIONS as e:
                last_error = e
                if attempt < max_retries:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                continue
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500 and attempt < max_retries:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                    last_error = e
                    continue
                return b"", "", 0

        if last_error:
            raise last_error
        return b"", "", 0

    def _detect_format(self, content: bytes, content_type: str, url: str) -> str:
        """Detect file format from magic bytes, content-type, or URL."""
        header = content[:16] if content else b""

        # Magic bytes
        for magic, fmt in MAGIC_BYTES.items():
            if header.startswith(magic):
                return fmt

        # ZIP-based (XLSX/DOCX)
        if header.startswith(b"PK\x03\x04"):
            if b"workbook.xml" in content[:10000]:
                return "xlsx"
            elif b"word/" in content[:10000]:
                return "docx"
            return "xlsx"

        # Content-Type
        ct_lower = content_type.lower()
        if "pdf" in ct_lower:
            return "pdf"
        elif "spreadsheet" in ct_lower or "excel" in ct_lower:
            return "xlsx"
        elif "text/html" in ct_lower or "application/xhtml" in ct_lower:
            return "html"

        return self._detect_format_from_url(url)

    def _detect_format_from_url(self, url_or_path: str) -> str:
        """Detect file format from URL or path extension."""
        if not url_or_path:
            return "html"

        path = url_or_path.lower().split("?")[0]
        if path.endswith(".pdf"):
            return "pdf"
        elif path.endswith(".xlsx"):
            return "xlsx"
        elif path.endswith(".xls"):
            return "xls"
        elif path.endswith(".docx"):
            return "docx"
        elif path.endswith((".html", ".htm")):
            return "html"
        return "html"

    def _format_to_ext(self, file_format: str) -> str:
        """Convert format name to file extension."""
        return {
            "pdf": "pdf",
            "xlsx": "xlsx",
            "xls": "xls",
            "docx": "docx",
            "html": "html",
            "csv": "csv",
        }.get(file_format, "bin")
