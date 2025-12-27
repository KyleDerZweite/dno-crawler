"""
Step 04: Extract Data

Extracts structured data from downloaded files.

Strategy:
1. If AI is configured, use AI extraction (text mode for HTML, vision for PDF)
2. Otherwise, fall back to:
   - HTML files: BeautifulSoup-based extraction (html_extractor.py)
   - PDF files: Regex-based extraction (pdf_extractor.py)

What it does:
- Load the file from local storage
- Extract using configured method (AI or fallback)
- Parse into structured data format

Output stored in job.context:
- extracted_data: list of records from extraction
- extraction_notes: any notes about the extraction
- extraction_method: "ai", "html_parser", or "pdf_regex"
"""

import asyncio
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import CrawlJobModel
from app.jobs.steps.base import BaseStep


class ExtractStep(BaseStep):
    label = "Extracting Data"
    description = "Extracting structured data from document..."

    async def run(self, db: AsyncSession, job: CrawlJobModel) -> str:
        ctx = job.context or {}
        file_path = ctx.get("downloaded_file")
        file_format = ctx.get("file_format", "").lower()
        
        if not file_path:
            raise ValueError("No file to extract from")
        
        path = Path(file_path)
        dno_name = ctx.get("dno_name", "Unknown")
        
        # Detect format from extension if not in context
        if not file_format:
            file_format = path.suffix.lstrip(".").lower()
        
        # Try AI extraction if configured
        if settings.ai_enabled:
            result = await self._extract_with_ai(path, dno_name, job.year, job.data_type)
            if result:
                ctx["extracted_data"] = result.get("data", [])
                ctx["extraction_notes"] = result.get("notes", "")
                ctx["extraction_method"] = "ai"
                ctx["extraction_model"] = settings.ai_model
                job.context = ctx
                await db.commit()
                return f"Extracted {len(ctx['extracted_data'])} records using AI ({settings.ai_model})"
        
        # Fallback extraction based on file format
        records, method = await self._extract_fallback(path, file_format, job.data_type, job.year)
        ctx["extracted_data"] = records
        ctx["extraction_notes"] = f"Fallback {method} extraction"
        ctx["extraction_method"] = method
        job.context = ctx
        await db.commit()
        
        return f"Extracted {len(records)} records using {method}"

    async def _extract_with_ai(
        self, 
        file_path: Path, 
        dno_name: str, 
        year: int, 
        data_type: str
    ) -> dict | None:
        """Extract data using AI (auto-routes to text or vision mode)."""
        try:
            from app.services.extraction.ai_extractor import extract_with_ai
            
            prompt = self._build_prompt(dno_name, year, data_type)
            return await extract_with_ai(file_path, prompt)
        except Exception as e:
            import structlog
            structlog.get_logger().warning("ai_extraction_failed", error=str(e))
            return None

    async def _extract_fallback(
        self, 
        file_path: Path, 
        file_format: str, 
        data_type: str,
        year: int
    ) -> tuple[list, str]:
        """Fallback extraction when AI is not available."""
        
        # HTML files: use BeautifulSoup parser
        if file_format in ("html", "htm"):
            from app.services.extraction.html_extractor import extract_hlzf_from_html
            
            html_content = file_path.read_text(encoding="utf-8", errors="replace")
            
            if data_type == "hlzf":
                records = extract_hlzf_from_html(html_content, year)
                return records, "html_parser"
            else:
                # No HTML parser for netzentgelte yet
                return [], "html_parser"
        
        # PDF files: use regex extraction
        from app.services.extraction.pdf_extractor import (
            extract_netzentgelte_from_pdf,
            extract_hlzf_from_pdf,
        )
        
        if data_type == "netzentgelte":
            records = await asyncio.to_thread(extract_netzentgelte_from_pdf, file_path)
        else:  # hlzf
            records = await asyncio.to_thread(extract_hlzf_from_pdf, file_path)
        
        return records, "pdf_regex"

    def _build_prompt(self, dno_name: str, year: int, data_type: str) -> str:
        """Build the extraction prompt for AI."""
        if data_type == "netzentgelte":
            return f"""Extract Netzentgelte (network tariffs) data from this document.

DNO: {dno_name}
Year: {year}

For each voltage level, extract:
- voltage_level: Name as written (e.g., "Niederspannung", "Mittelspannung")
- arbeitspreis: Work price in ct/kWh
- leistungspreis: Capacity price in €/kW or €/kW/a

Return valid JSON:
{{
  "success": true,
  "data_type": "netzentgelte",
  "source_page": <page number>,
  "notes": "<any observations>",
  "data": [
    {{"voltage_level": "...", "arbeitspreis": ..., "leistungspreis": ...}}
  ]
}}
"""
        else:  # hlzf
            return f"""Extract HLZF (Hochlastzeitfenster) data from this document.

DNO: {dno_name}
Year: {year}

For each voltage level, extract time windows per season:
- voltage_level: Name as written
- winter: Time window(s) or "entfällt"
- fruehling: Time window(s) or "entfällt"
- sommer: Time window(s) or "entfällt"
- herbst: Time window(s) or "entfällt"

Return valid JSON:
{{
  "success": true,
  "data_type": "hlzf",
  "source_page": <page number>,
  "notes": "<any observations>",
  "data": [
    {{"voltage_level": "...", "winter": "...", "sommer": "..."}}
  ]
}}
"""
