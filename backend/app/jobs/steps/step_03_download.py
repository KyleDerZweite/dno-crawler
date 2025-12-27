"""
Step 03: Download

Downloads the found data source to local storage.

What it does:
- Skip if strategy is "use_cache"
- Detect file format from URL (pdf, xlsx, html, etc.)
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
- years_split: list of years if HTML was split (optional)
"""

import asyncio
from pathlib import Path

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import CrawlJobModel
from app.jobs.steps.base import BaseStep

logger = structlog.get_logger()


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
            
            # For HTML files: strip and split by year
            if file_format == "html":
                html_content = response.content.decode("utf-8", errors="replace")
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
                    return f"Downloaded & split HTML: {result['file_path']} (years: {years_str})"
            
            # Standard file: save directly
            save_path.write_bytes(response.content)
        
        # Update context
        ctx["downloaded_file"] = str(save_path)
        ctx["file_format"] = file_format
        job.context = ctx
        
        return f"Downloaded to: {save_path.name} ({file_format.upper()}, {len(response.content) // 1024} KB)"
    
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
            logger.warning("html_strip_failed", slug=dno_slug, data_type=data_type)
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

