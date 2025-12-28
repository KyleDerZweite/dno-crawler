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
from sqlalchemy.orm.attributes import flag_modified

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
            prompt = self._build_prompt(dno_name, job.year, job.data_type)
            result = await self._extract_with_ai(path, dno_name, job.year, job.data_type, prompt)
            if result:
                extracted_data = result.get("data", [])
                extraction_meta = result.get("_extraction_meta", {})
                
                # Validate HLZF extraction - should have exactly 5 voltage levels
                if job.data_type == "hlzf" and len(extracted_data) != 5:
                    import structlog
                    structlog.get_logger().warning(
                        "hlzf_extraction_incomplete",
                        expected=5,
                        actual=len(extracted_data),
                        voltage_levels=[r.get("voltage_level") for r in extracted_data],
                        dno=dno_name,
                        year=job.year,
                        msg="AI did not extract all 5 voltage levels"
                    )
                
                # Get file metadata
                file_metadata = self._get_file_metadata(path)
                
                ctx["extracted_data"] = extracted_data
                ctx["extraction_notes"] = result.get("notes", "")
                ctx["extraction_method"] = "ai"
                ctx["extraction_model"] = settings.ai_model
                
                # Store extraction log for debugging/transparency
                ctx["extraction_log"] = {
                    "prompt": prompt,
                    "response": extraction_meta.get("raw_response"),
                    "file_metadata": file_metadata,
                    "model": extraction_meta.get("model"),
                    "mode": extraction_meta.get("mode"),
                    "usage": extraction_meta.get("usage"),
                }
                
                job.context = ctx
                flag_modified(job, 'context')
                await db.commit()
                return f"Extracted {len(extracted_data)} records using AI ({settings.ai_model})"
        
        # Fallback extraction based on file format
        records, method = await self._extract_fallback(path, file_format, job.data_type, job.year)
        
        # Get file metadata for fallback too
        file_metadata = self._get_file_metadata(path)
        
        ctx["extracted_data"] = records
        ctx["extraction_notes"] = f"Fallback {method} extraction"
        ctx["extraction_method"] = method
        
        # Store extraction log for fallback
        ctx["extraction_log"] = {
            "prompt": f"File: {path.name}",  # Reference to file, not content
            "response": records,  # The extraction result
            "file_metadata": file_metadata,
            "model": None,
            "mode": "fallback",
            "usage": None,
        }
        
        job.context = ctx
        flag_modified(job, 'context')
        await db.commit()
        
        return f"Extracted {len(records)} records using {method}"

    async def _extract_with_ai(
        self, 
        file_path: Path, 
        dno_name: str, 
        year: int, 
        data_type: str,
        prompt: str
    ) -> dict | None:
        """Extract data using AI (auto-routes to text or vision mode)."""
        try:
            from app.services.extraction.ai_extractor import extract_with_ai
            
            return await extract_with_ai(file_path, prompt)
        except Exception as e:
            import structlog
            structlog.get_logger().warning("ai_extraction_failed", error=str(e))
            return None

    def _get_file_metadata(self, file_path: Path) -> dict:
        """Get file metadata for logging."""
        metadata = {
            "path": str(file_path),
            "name": file_path.name,
            "format": file_path.suffix.lstrip(".").lower(),
            "size_bytes": file_path.stat().st_size if file_path.exists() else 0,
        }
        
        # Try to get page count for PDFs
        if file_path.suffix.lower() == ".pdf":
            try:
                import fitz
                doc = fitz.open(file_path)
                metadata["pages"] = len(doc)
                doc.close()
            except Exception:
                pass  # Skip if PyMuPDF not available
        
        return metadata

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

German electricity tariffs often have TWO sets of prices based on annual usage:
- "< 2.500 h/a" or "unter 2500h" (under 2500 hours/year usage)
- "≥ 2.500 h/a" or "über 2500h" (2500+ hours/year usage)

For each voltage level (Spannungsebene), extract:
- voltage_level: Standardized abbreviation MUST be used:
  - "HS" for Hochspannung
  - "HS/MS" for Umspannung Hoch-/Mittelspannung
  - "MS" for Mittelspannung
  - "MS/NS" for Umspannung Mittel-/Niederspannung
  - "NS" for Niederspannung
- leistung_unter_2500h: Capacity price (Leistungspreis) for < 2500h in €/kW/a
- arbeit_unter_2500h: Work price (Arbeitspreis) for < 2500h in ct/kWh
- leistung: Capacity price (Leistungspreis) for ≥ 2500h in €/kW/a  
- arbeit: Work price (Arbeitspreis) for ≥ 2500h in ct/kWh

If only one set of prices exists (no usage distinction), use leistung and arbeit fields only.

Return valid JSON:
{{
  "success": true,
  "data_type": "netzentgelte",
  "source_page": <page number>,
  "notes": "<any observations about the data>",
  "data": [
    {{"voltage_level": "HS", "leistung_unter_2500h": ..., "arbeit_unter_2500h": ..., "leistung": ..., "arbeit": ...}}
  ]
}}
"""
        else:  # hlzf
            return f"""Extract HLZF (Hochlastzeitfenster) data from this German electricity grid document.

DNO: {dno_name}
Year: {year}

CRITICAL: You MUST extract EXACTLY 5 voltage levels. Do NOT skip any rows!

The 5 voltage levels (Entnahmeebene/Spannungsebene) are:
1. Hochspannungsnetz / Hochspannung → output as "HS"
2. Umspannung zur Mittelspannung / Umspann. z. MS / HS/MS-Umspannung → output as "HS/MS"
3. Mittelspannungsnetz / Mittelspannung → output as "MS"
4. Umspannung zur Niederspannung / Umspann. z. NS / MS/NS-Umspannung → output as "MS/NS"  
5. Niederspannungsnetz / Niederspannung → output as "NS"

NOTE: In PDF tables, voltage level names may be split across multiple lines (e.g., "Umspannung zur" on one line and "Mittelspannung" on the next). These should be treated as a single voltage level.

TABLE STRUCTURE - columns ordered left-to-right:
- Column 1 (Winter): months Jan., Feb., Dez. / Januar, Februar, Dezember
- Column 2 (Frühling): months Mrz. – Mai / März bis Mai
- Column 3 (Sommer): months Jun. – Aug. / Juni bis August
- Column 4 (Herbst): months Sept. – Nov. / September bis November

For EACH of the 5 voltage levels, extract:
- winter: Time window(s) from first column, or null if "entfällt"
- fruehling: Time window(s) from second column, or null if "entfällt"
- sommer: Time window(s) from third column, or null if "entfällt"
- herbst: Time window(s) from fourth column, or null if "entfällt"

Time format: "HH:MM-HH:MM" (e.g., "07:30-15:30"). Multiple windows separated by "\\n".

YOU MUST RETURN EXACTLY 5 RECORDS - one for each voltage level:
{{
  "success": true,
  "data_type": "hlzf",
  "source_page": <page number where table was found>,
  "notes": "<any observations>",
  "data": [
    {{"voltage_level": "HS", "winter": "07:30-15:30\\n17:15-19:15", "fruehling": null, "sommer": null, "herbst": "11:15-14:00"}},
    {{"voltage_level": "HS/MS", "winter": "07:30-15:45\\n16:30-18:15", "fruehling": null, "sommer": null, "herbst": "16:45-17:30"}},
    {{"voltage_level": "MS", "winter": "...", "fruehling": "...", "sommer": "...", "herbst": "..."}},
    {{"voltage_level": "MS/NS", "winter": "...", "fruehling": "...", "sommer": "...", "herbst": "..."}},
    {{"voltage_level": "NS", "winter": "...", "fruehling": "...", "sommer": "...", "herbst": "..."}}
  ]
}}
"""
