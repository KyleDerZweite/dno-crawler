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
import zipfile
from pathlib import Path

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import CrawlJobModel
from app.jobs.steps.base import BaseStep, StepError

logger = structlog.get_logger()

# Limits
MAX_FILES = 50
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB per file
MAX_TOTAL_SIZE = 300 * 1024 * 1024  # 300MB total

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

        # Merge with existing downloads (for multi-pass crawls)
        existing_files = ctx.get("downloaded_files", [])
        existing_urls = {f["url"] for f in existing_files}
        start_idx = len(existing_files)

        # Build registry lookup for cross-run file reuse
        prior_downloads = ctx.get("prior_downloads", [])
        registry_by_url_hash: dict[str, dict] = {}
        for entry in prior_downloads:
            registry_by_url_hash[entry["url_hash"]] = entry

        downloaded: list[dict] = []
        reused = 0
        content_hashes_seen: set[str] = set()  # SHA-256 hashes for content dedup
        total_bytes = sum(f.get("size_bytes", 0) for f in existing_files)
        failed = 0

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0),
            follow_redirects=True,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        ) as client:
            for i, candidate in enumerate(candidates[:MAX_FILES]):
                url = candidate["url"]
                idx = start_idx + i

                # Skip URLs already downloaded in a previous pass
                if url in existing_urls:
                    continue

                # Check download registry: reuse file if it still exists on disk
                url_hash = hashlib.md5(url.encode()).hexdigest()[:32]
                registry_entry = registry_by_url_hash.get(url_hash)
                if registry_entry and registry_entry.get("file_path"):
                    existing_path = Path(registry_entry["file_path"])
                    if existing_path.exists():
                        downloaded.append(
                            {
                                "path": str(existing_path),
                                "format": registry_entry.get("file_format", "pdf"),
                                "url": url,
                                "size_bytes": existing_path.stat().st_size,
                                "source": "registry",
                            }
                        )
                        reused += 1
                        log.debug("file_reused_from_registry", url=url[:60])
                        continue

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

                # Strip HTML at download time to remove scripts, nav, styles, etc.
                if file_format == "html":
                    content = self._strip_html(content)

                # Build filename: {slug}_{index}_{url_hash}.{ext}
                url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
                filename = f"{dno_slug}_{idx:02d}_{url_hash}.{ext}"
                save_path = save_dir / filename

                # Compute content hash for deduplication
                content_hash = hashlib.sha256(content).hexdigest()

                # Skip duplicate content (same file at different URL)
                if content_hash in content_hashes_seen:
                    log.debug("duplicate_content_skipped", url=url[:60], hash=content_hash[:12])
                    continue
                content_hashes_seen.add(content_hash)

                # Save file
                await asyncio.to_thread(save_path.write_bytes, content)

                downloaded.append(
                    {
                        "path": str(save_path),
                        "format": file_format,
                        "url": url,
                        "size_bytes": file_size,
                        "content_hash": content_hash,
                    }
                )

                log.debug(
                    "file_downloaded",
                    url=url[:60],
                    format=file_format,
                    size_kb=file_size // 1024,
                    index=idx,
                )

        # Extract files from downloaded ZIPs and replace ZIP entries
        extracted_from_zips = await self._extract_zips(downloaded, save_dir, dno_slug, log)
        if extracted_from_zips:
            downloaded = extracted_from_zips

        ctx["downloaded_files"] = existing_files + downloaded
        job.context = ctx
        await db.commit()

        if not downloaded and not existing_files:
            raise StepError(
                f"All {failed} download attempts failed for {dno_slug}. "
                f"Tried {len(candidates[:MAX_FILES])} candidates."
            )

        parts = [f"Downloaded {len(downloaded) - reused} files"]
        if reused:
            parts.append(f"reused {reused} from registry")
        parts.append(f"{total_bytes // 1024} KB total")
        if failed:
            parts.append(f"{failed} failed")
        return f"{', '.join(parts)}"

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

    @staticmethod
    def _strip_html(content: bytes) -> bytes:
        """Strip junk elements from HTML before saving to disk."""
        try:
            from app.services.extraction.html_stripper import clean_html_for_storage

            text = content.decode("utf-8", errors="replace")
            cleaned = clean_html_for_storage(text)
            return cleaned.encode("utf-8")
        except Exception:
            return content  # Return original on any error

    async def _extract_zips(
        self,
        downloaded: list[dict],
        save_dir: Path,
        dno_slug: str,
        log: structlog.stdlib.BoundLogger,
    ) -> list[dict]:
        """Extract relevant files from downloaded ZIPs.

        Replaces ZIP entries in the downloaded list with their extracted
        contents (PDFs, XLSX, HTML). Non-ZIP entries are kept as-is.
        """
        # Relevant extensions inside ZIPs
        extract_exts = {".pdf", ".xlsx", ".xls", ".html", ".htm", ".csv"}
        result: list[dict] = []
        extracted_count = 0

        for entry in downloaded:
            if entry.get("format") != "zip":
                result.append(entry)
                continue

            zip_path = Path(entry["path"])
            if not zip_path.exists():
                continue

            source_url = entry.get("url", "")

            try:
                members = await asyncio.to_thread(self._list_zip_members, zip_path, extract_exts)

                for member_name in members:
                    file_format = self._detect_format_from_url(member_name)
                    safe_name = Path(member_name).name.replace(" ", "_")
                    dest_name = f"{dno_slug}_zip_{extracted_count:02d}_{safe_name}"
                    dest_path = save_dir / dest_name

                    content = await asyncio.to_thread(self._read_zip_member, zip_path, member_name)
                    if not content:
                        continue

                    # Strip HTML inside ZIPs too
                    if file_format == "html":
                        content = self._strip_html(content)

                    await asyncio.to_thread(dest_path.write_bytes, content)

                    content_hash = hashlib.sha256(content).hexdigest()
                    result.append(
                        {
                            "path": str(dest_path),
                            "format": file_format,
                            "url": source_url,
                            "size_bytes": len(content),
                            "content_hash": content_hash,
                            "source": "zip",
                            "zip_member": member_name,
                        }
                    )
                    extracted_count += 1

                log.info(
                    "zip_extracted",
                    zip_file=zip_path.name,
                    members_extracted=len(members),
                )

                # Remove the ZIP file after extraction
                await asyncio.to_thread(zip_path.unlink, missing_ok=True)

            except Exception as e:
                log.warning("zip_extraction_failed", file=zip_path.name, error=str(e))
                result.append(entry)

        if not extracted_count:
            return downloaded

        return result

    @staticmethod
    def _list_zip_members(zip_path: Path, allowed_exts: set[str]) -> list[str]:
        """List relevant members inside a ZIP archive."""
        members = []
        with zipfile.ZipFile(zip_path, "r") as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                ext = Path(info.filename).suffix.lower()
                if ext in allowed_exts and info.file_size < MAX_FILE_SIZE:
                    members.append(info.filename)
        return members

    @staticmethod
    def _read_zip_member(zip_path: Path, member_name: str) -> bytes | None:
        """Read a single member from a ZIP archive."""
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                return zf.read(member_name)
        except Exception:
            return None

    def _detect_format(self, content: bytes, content_type: str, url: str) -> str:
        """Detect file format from magic bytes, content-type, or URL."""
        header = content[:16] if content else b""

        # Magic bytes
        for magic, fmt in MAGIC_BYTES.items():
            if header.startswith(magic):
                return fmt

        # ZIP-based (XLSX/DOCX/plain ZIP)
        if header.startswith(b"PK\x03\x04"):
            if b"workbook.xml" in content[:10000]:
                return "xlsx"
            elif b"word/" in content[:10000]:
                return "docx"
            # Check URL to distinguish plain ZIPs from office formats
            if url.lower().split("?")[0].endswith(".zip"):
                return "zip"
            return "xlsx"

        # Content-Type
        ct_lower = content_type.lower()
        if "pdf" in ct_lower:
            return "pdf"
        elif "spreadsheet" in ct_lower or "excel" in ct_lower:
            return "xlsx"
        elif "zip" in ct_lower:
            return "zip"
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
        elif path.endswith(".zip"):
            return "zip"
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
            "zip": "zip",
        }.get(file_format, "bin")
