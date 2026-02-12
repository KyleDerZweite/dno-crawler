"""
Step 02: Download

Downloads the found data source to local storage.

What it does:
- Skip if strategy is "use_cache"
- Stream large files with size limits (100MB max)
- Detect file format from magic bytes, Content-Type, or URL
- Proper encoding detection for HTML content
- Download file to: data/downloads/{dno_slug}/{dno_slug}-{data_type}-{year}.{ext}
- For HTML pages: strip unnecessary content and split by year

File storage convention:
    data/downloads/
    ├── westnetz/
    │   ├── westnetz-netzentgelte-2024.pdf
    │   ├── westnetz-netzentgelte-2025.pdf
    │   └── westnetz-hlzf-2025.html
    └── rheinnetz/
        └── rheinnetz-netzentgelte-2025.xlsx

Output stored in job.context:
- downloaded_file: local file path
- file_format: detected format (pdf, xlsx, html, etc.)
- detected_encoding: character encoding used for HTML
- years_split: list of years if HTML was split (optional)
"""

import asyncio
from pathlib import Path

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import CrawlJobModel
from app.jobs.steps.base import BaseStep, StepError
from app.services.encoding_utils import decode_content

logger = structlog.get_logger()


# Maximum file size (100MB)
MAX_FILE_SIZE = 100 * 1024 * 1024

# Magic bytes for file format detection
MAGIC_BYTES = {
    b'%PDF': 'pdf',
    # PK\x03\x04 (ZIP-based) handled separately below for XLSX/DOCX/PPTX disambiguation
    b'\xd0\xcf\x11\xe0': 'xls',  # OLE2 compound document (XLS, DOC)
}


class DownloadStep(BaseStep):
    label = "Downloading"
    description = "Downloading data source to local storage..."

    async def run(self, db: AsyncSession, job: CrawlJobModel) -> str:
        ctx = job.context or {}
        strategy = ctx.get("strategy", "search")

        # Skip if using cache
        if strategy == "use_cache":
            cached_file = ctx.get("file_to_process")
            ctx["downloaded_file"] = cached_file
            ctx["file_format"] = self._detect_format_from_url(cached_file) if cached_file else "unknown"
            job.context = ctx
            return "Skipped → Using cached file"

        # Check if file was already downloaded during discovery (landing page flow)
        cached_file_path = ctx.get("cached_file_path")
        if cached_file_path and Path(cached_file_path).exists():
            # File was already downloaded and verified during discovery
            ctx["downloaded_file"] = cached_file_path
            ctx["file_format"] = self._detect_format_from_path(Path(cached_file_path))
            job.context = ctx
            logger.info(
                "using_pre_cached_file",
                cached_path=cached_file_path,
                strategy=strategy,
            )
            return f"Using pre-cached file from discovery: {cached_file_path}"

        url = ctx.get("found_url")
        if not url:
            raise StepError("No URL to download - discovery step may have failed")

        # Build save dir (with path traversal protection)
        dno_slug = ctx.get("dno_slug", "unknown")
        base_dir = Path(settings.downloads_path)
        save_dir = base_dir / dno_slug
        if not save_dir.resolve().is_relative_to(base_dir.resolve()):
            raise StepError(f"Invalid slug for path construction: {dno_slug}")
        save_dir.mkdir(parents=True, exist_ok=True)

        log = logger.bind(dno=dno_slug, url=url[:60])

        # Download with streaming and retries
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0),
            follow_redirects=True,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        ) as client:
            content, content_type, file_size = await self._stream_download(
                client, url, log
            )

            # Detect format from multiple sources
            file_format = self._detect_format(content, content_type, url)

            # Build save path with correct extension
            save_path = save_dir / f"{dno_slug}-{job.data_type}-{job.year}.{file_format}"

            # For HTML files: detect encoding and process
            if file_format == "html":
                html_content, detected_encoding = decode_content(content, content_type)
                ctx["detected_encoding"] = detected_encoding

                log.info(
                    "Processing HTML content",
                    encoding=detected_encoding,
                    size_kb=len(content) // 1024,
                )

                result = await self._process_html(
                    html_content=html_content,
                    save_dir=save_dir,
                    dno_slug=dno_slug,
                    data_type=job.data_type,
                    target_year=job.year
                )

                if result:
                    ctx["downloaded_file"] = result["file_path"]
                    ctx["file_format"] = "html"
                    ctx["years_split"] = result.get("years_found", [])
                    job.context = ctx

                    years_str = ", ".join(str(y) for y in result.get("years_found", []))
                    return f"Downloaded & split HTML: {Path(result['file_path']).name} (years: {years_str})"
                else:
                    # HTML processing failed - save raw content as fallback
                    log.warning(
                        "HTML processing failed, saving raw content",
                        encoding=detected_encoding,
                    )
                    save_path.write_text(html_content, encoding="utf-8")
                    ctx["downloaded_file"] = str(save_path)
                    ctx["file_format"] = "html"
                    ctx["html_processing_failed"] = True
                    job.context = ctx
                    return f"Downloaded HTML (unprocessed): {save_path.name} ({file_size // 1024} KB)"

            # Binary file: save directly
            save_path.write_bytes(content)

        # Update context
        ctx["downloaded_file"] = str(save_path)
        ctx["file_format"] = file_format
        job.context = ctx

        return f"Downloaded to: {save_path.name} ({file_format.upper()}, {file_size // 1024} KB)"

    async def _stream_download(
        self,
        client: httpx.AsyncClient,
        url: str,
        log: structlog.stdlib.BoundLogger,
        max_retries: int = 3,
    ) -> tuple[bytes, str, int]:
        """
        Stream download with size limit and retries.

        Returns:
            Tuple of (content_bytes, content_type, file_size)

        Raises:
            StepError: If download fails or exceeds size limit
        """
        import asyncio

        from app.services.retry_utils import RETRYABLE_EXCEPTIONS

        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                async with client.stream("GET", url) as response:
                    # Handle rate limiting
                    if response.status_code == 429:
                        retry_after = response.headers.get("retry-after", "5")
                        wait_time = min(float(retry_after), 30.0)
                        log.warning("Rate limited, waiting", wait_time=wait_time, attempt=attempt)
                        await asyncio.sleep(wait_time)
                        continue

                    response.raise_for_status()

                    content_type = response.headers.get("content-type", "")
                    content_length = response.headers.get("content-length")

                    # Check declared size
                    if content_length:
                        declared_size = int(content_length)
                        if declared_size > MAX_FILE_SIZE:
                            raise StepError(
                                f"File too large: {declared_size // (1024*1024)}MB exceeds {MAX_FILE_SIZE // (1024*1024)}MB limit"
                            )

                    # Stream content with size tracking
                    chunks = []
                    total_size = 0

                    async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                        total_size += len(chunk)

                        if total_size > MAX_FILE_SIZE:
                            raise StepError(
                                f"Download exceeded size limit ({MAX_FILE_SIZE // (1024*1024)}MB)"
                            )

                        chunks.append(chunk)

                    content = b"".join(chunks)

                    log.info(
                        "Download complete",
                        size_kb=total_size // 1024,
                        content_type=content_type[:50] if content_type else "unknown",
                    )

                    return content, content_type, total_size

            except RETRYABLE_EXCEPTIONS as e:
                last_error = e
                if attempt < max_retries:
                    wait_time = 0.5 * (2 ** (attempt - 1))  # Exponential backoff
                    log.warning(
                        "Download failed, retrying",
                        error=str(e),
                        attempt=attempt,
                        wait_time=wait_time,
                    )
                    await asyncio.sleep(wait_time)
                continue
            except httpx.HTTPStatusError as e:
                # Server errors (5xx) can be retried
                if e.response.status_code >= 500 and attempt < max_retries:
                    wait_time = 0.5 * (2 ** (attempt - 1))
                    log.warning(
                        "Server error, retrying",
                        status=e.response.status_code,
                        attempt=attempt,
                    )
                    await asyncio.sleep(wait_time)
                    last_error = e
                    continue
                raise StepError(f"HTTP error {e.response.status_code}: {e}") from e

        # All retries exhausted
        if last_error:
            raise StepError(f"Download failed after {max_retries} attempts: {last_error}") from last_error
        raise StepError(f"Download failed after {max_retries} attempts")


    def _detect_format(
        self,
        content: bytes,
        content_type: str,
        url: str,
    ) -> str:
        """
        Detect file format from multiple sources (priority order):
        1. Magic bytes (most reliable)
        2. Content-Disposition header filename
        3. Content-Type header
        4. URL extension
        """
        # 1. Magic bytes detection (first 16 bytes)
        header = content[:16] if content else b""
        for magic, fmt in MAGIC_BYTES.items():
            if header.startswith(magic):
                return fmt

        # Check for XLSX vs DOCX (both are ZIP-based)
        if header.startswith(b'PK\x03\x04'):
            # Could be xlsx, docx, or pptx - check for specific signatures
            if b'[Content_Types].xml' in content[:2048]:
                if b'workbook.xml' in content[:10000]:
                    return 'xlsx'
                elif b'word/' in content[:10000]:
                    return 'docx'
                elif b'ppt/' in content[:10000]:
                    return 'pptx'
            return 'xlsx'  # Default for Office Open XML

        # 2. Content-Type header
        ct_lower = content_type.lower()

        # Handle common content types
        if "pdf" in ct_lower:
            return "pdf"
        elif "spreadsheet" in ct_lower or "excel" in ct_lower or "ms-excel" in ct_lower:
            return "xlsx"
        elif "msword" in ct_lower or "wordprocessing" in ct_lower:
            return "docx"
        elif "text/html" in ct_lower or "application/xhtml" in ct_lower:
            return "html"
        elif "text/csv" in ct_lower:
            return "csv"
        elif "octet-stream" in ct_lower or "force-download" in ct_lower:
            # Generic binary - fall through to URL detection
            pass

        # 3. Fall back to URL-based detection
        return self._detect_format_from_url(url)

    def _detect_format_from_url(self, url_or_path: str) -> str:
        """Detect file format from URL or path extension."""
        if not url_or_path:
            return "html"

        url_lower = url_or_path.lower()

        # Strip query parameters for extension detection
        path = url_lower.split("?")[0]

        if path.endswith(".pdf"):
            return "pdf"
        elif path.endswith(".xlsx"):
            return "xlsx"
        elif path.endswith(".xls"):
            return "xls"
        elif path.endswith(".docx"):
            return "docx"
        elif path.endswith(".doc"):
            return "doc"
        elif path.endswith(".csv"):
            return "csv"
        elif path.endswith(".pptx"):
            return "pptx"
        elif path.endswith((".html", ".htm")):
            return "html"
        else:
            # Assume HTML if no recognizable extension
            return "html"

    def _detect_format_from_path(self, file_path: Path) -> str:
        """Detect file format from a Path object."""
        return self._detect_format_from_url(str(file_path))

    async def _process_html(
        self,
        html_content: str,
        save_dir: Path,
        dno_slug: str,
        data_type: str,
        target_year: int
    ) -> dict | None:
        """Process HTML: strip unnecessary content and split by year."""
        from app.services.extraction.html_stripper import HtmlStripper

        try:
            stripper = HtmlStripper()

            # Strip and split into year-specific files
            created_files = await asyncio.to_thread(
                stripper.strip_and_split,
                html_content=html_content,
                output_dir=save_dir,
                slug=dno_slug,
                data_type=data_type
            )

            if not created_files:
                logger.warning(
                    "html_strip_failed",
                    slug=dno_slug,
                    data_type=data_type,
                    reason="no_files_created",
                )
                return None

            years_found = [year for year, _ in created_files]

            # Find the file for our target year
            target_file = None
            for year, file_path in created_files:
                if year == target_year:
                    target_file = str(file_path)
                    break

            # If target year not found, use the first file
            if not target_file and created_files:
                target_file = str(created_files[0][1])
                logger.warning(
                    "target_year_not_found",
                    target_year=target_year,
                    available_years=years_found,
                    using=target_file
                )

            return {
                "file_path": target_file,
                "years_found": years_found
            }

        except Exception as e:
            logger.warning(
                "html_processing_exception",
                slug=dno_slug,
                data_type=data_type,
                error=str(e),
            )
            return None
