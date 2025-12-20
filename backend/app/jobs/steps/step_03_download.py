"""
Step 03: Download

Downloads the found data source to local storage.

What it does:
- Skip if strategy is "use_cache"
- Detect file format from URL (pdf, xlsx, html, etc.)
- Download file to: data/downloads/{dno_slug}/{dno_slug}-{data_type}-{year}.{ext}
- For HTML pages, save the page content

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
"""

import asyncio
from pathlib import Path

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import CrawlJobModel
from app.jobs.steps.base import BaseStep


class DownloadStep(BaseStep):
    label = "Downloading"
    description = "Downloading data source to local storage..."

    async def run(self, db: AsyncSession, job: CrawlJobModel) -> str:
        ctx = job.context or {}
        strategy = ctx.get("strategy", "search")
        
        # Skip if using cache
        if strategy == "use_cache":
            # Use the cached file
            ctx["downloaded_file"] = ctx.get("file_to_process")
            ctx["file_format"] = self._detect_format(ctx["downloaded_file"])
            return "Skipped → Using cached file"
        
        url = ctx.get("found_url")
        if not url:
            raise ValueError("No URL to download - search step may have failed")
        
        # Build save dir
        dno_slug = ctx.get("dno_slug", "unknown")
        save_dir = Path(settings.downloads_path) / dno_slug
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # Download the file
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            # Detect format from Content-Type header (more reliable than URL)
            content_type = response.headers.get("content-type", "").lower()
            file_format = self._detect_format_from_content_type(content_type, url)
            
            # Build save path with correct extension
            save_path = save_dir / f"{dno_slug}-{job.data_type}-{job.year}.{file_format}"
            
            # Save to disk
            save_path.write_bytes(response.content)
        
        # Update context
        ctx["downloaded_file"] = str(save_path)
        ctx["file_format"] = file_format
        job.context = ctx
        # Let base class handle commit
        
        return f"Downloaded to: {save_path.name} ({file_format.upper()}, {len(response.content) // 1024} KB)"
    
    def _detect_format_from_content_type(self, content_type: str, url: str) -> str:
        """Detect file format from Content-Type header, fall back to URL."""
        # Check Content-Type header first (most reliable)
        if "pdf" in content_type:
            return "pdf"
        elif "spreadsheet" in content_type or "excel" in content_type:
            return "xlsx"
        elif "msword" in content_type or "wordprocessing" in content_type:
            return "docx"
        elif "text/html" in content_type:
            return "html"
        elif "text/csv" in content_type:
            return "csv"
        # Fall back to URL-based detection
        return self._detect_format(url)
    
    def _detect_format(self, url_or_path: str) -> str:
        """Detect file format from URL or path (fallback)."""
        url_lower = url_or_path.lower()
        
        if url_lower.endswith(".pdf"):
            return "pdf"
        elif url_lower.endswith(".xlsx"):
            return "xlsx"
        elif url_lower.endswith(".xls"):
            return "xls"
        elif url_lower.endswith(".docx"):
            return "docx"
        elif url_lower.endswith(".csv"):
            return "csv"
        elif url_lower.endswith(".pptx"):
            return "pptx"
        else:
            # Assume HTML if no extension
            return "html"
