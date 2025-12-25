"""
Step 04: Extract Data

Extracts structured data from downloaded files.

Strategy:
1. If AI is configured (AI_API_URL + AI_MODEL), use AI vision extraction
2. Otherwise, fall back to regex-based extraction from pdf_extractor.py

What it does:
- Load the file from local storage
- Extract using configured method (AI or regex)
- Parse into structured data format

Output stored in job.context:
- extracted_data: list of records from extraction
- extraction_notes: any notes about the extraction
- extraction_method: "ai" or "regex"
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
        
        if not file_path:
            raise ValueError("No file to extract from")
        
        path = Path(file_path)
        dno_name = ctx.get("dno_name", "Unknown")
        
        # Try AI extraction if configured
        if settings.ai_enabled:
            result = await self._extract_with_ai(path, dno_name, job.year, job.data_type)
            if result:
                ctx["extracted_data"] = result.get("data", [])
                ctx["extraction_notes"] = result.get("notes", "")
                ctx["extraction_method"] = "ai"
                ctx["extraction_model"] = settings.ai_model
                await db.commit()
                return f"Extracted {len(ctx['extracted_data'])} records using AI ({settings.ai_model})"
        
        # Fallback to regex extraction
        records = await self._extract_with_regex(path, job.data_type)
        ctx["extracted_data"] = records
        ctx["extraction_notes"] = "Regex-based extraction"
        ctx["extraction_method"] = "regex"
        await db.commit()
        
        return f"Extracted {len(records)} records using regex"

    async def _extract_with_ai(
        self, 
        file_path: Path, 
        dno_name: str, 
        year: int, 
        data_type: str
    ) -> dict | None:
        """Extract data using AI vision model."""
        try:
            from app.services.extraction.ai_extractor import extract_with_ai
            
            prompt = self._build_prompt(dno_name, year, data_type)
            return await extract_with_ai(file_path, prompt)
        except Exception as e:
            import structlog
            structlog.get_logger().warning("ai_extraction_failed", error=str(e))
            return None

    async def _extract_with_regex(self, file_path: Path, data_type: str) -> list:
        """Fallback regex-based extraction."""
        from app.services.extraction.pdf_extractor import (
            extract_netzentgelte_from_pdf,
            extract_hlzf_from_pdf,
        )
        
        # Run blocking PDF extraction in thread
        if data_type == "netzentgelte":
            return await asyncio.to_thread(extract_netzentgelte_from_pdf, file_path)
        else:  # hlzf
            return await asyncio.to_thread(extract_hlzf_from_pdf, file_path)

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
