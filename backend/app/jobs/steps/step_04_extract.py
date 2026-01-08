"""
Step 04: Extract Data

Extracts structured data from downloaded files.

Strategy (Regex-First with AI Fallback):
1. Try regex/HTML extraction first (cheaper, works for most documents)
2. Run sanity check on extracted data:
   - Netzentgelte: ≥3 records with at least leistung OR arbeit non-null
   - HLZF: ≥1 record with winter non-null
3. If sanity check passes → use regex result
4. If sanity check fails AND AI configured → try AI extraction
5. If AI not configured or fails → use regex result but auto-flag as potentially wrong

What it does:
- Load the file from local storage
- Extract using regex/HTML first, validate, then AI fallback if needed
- Parse into structured data format

Output stored in job.context:
- extracted_data: list of records from extraction
- extraction_notes: any notes about the extraction
- extraction_method: "regex", "html_parser", "ai", or "regex_ai_fallback"
- auto_flagged: True if extraction failed sanity and needs review
- auto_flag_reason: Reason for auto-flagging
"""

import asyncio
from pathlib import Path

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.db.models import CrawlJobModel
from app.jobs.steps.base import BaseStep
from app.services.sample_capture import SampleCapture

logger = structlog.get_logger()


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
        
        # Get file metadata
        file_metadata = self._get_file_metadata(path)
        
        # ===== STEP 1: Try regex/HTML extraction first =====
        logger.info(
            "extraction_starting",
            method="regex",
            dno=dno_name,
            year=job.year,
            data_type=job.data_type,
            file_format=file_format,
        )
        
        records, method = await self._extract_fallback(path, file_format, job.data_type, job.year)
        passed, reason = self._validate_extraction(records, job.data_type)
        
        if passed:
            # ===== Regex passed sanity check - use it! =====
            logger.info(
                "regex_extraction_passed",
                method=method,
                records=len(records),
                dno=dno_name,
                year=job.year,
                data_type=job.data_type,
            )
            
            ctx["extracted_data"] = records
            ctx["extraction_notes"] = f"{method} extraction (regex-first)"
            ctx["extraction_method"] = method
            
            # Extraction source metadata for persist step
            ctx["extraction_source_meta"] = {
                "source": method,
                "model": None,
                "source_format": file_format,
            }
            
            # Store extraction log
            ctx["extraction_log"] = {
                "prompt": f"File: {path.name}",
                "response": records,
                "file_metadata": file_metadata,
                "model": None,
                "mode": "regex_first",
                "usage": None,
            }
            
            job.context = ctx
            flag_modified(job, 'context')
            await db.commit()
            
            return f"Extracted {len(records)} records using {method} (regex-first)"
        
        # ===== STEP 2: Regex failed sanity check =====
        logger.warning(
            "regex_extraction_failed_sanity",
            reason=reason,
            records=len(records),
            dno=dno_name,
            year=job.year,
            data_type=job.data_type,
            method=method,
        )
        
        # ===== STEP 3: Try AI if configured =====
        ai_result = None
        if settings.ai_enabled:
            logger.info(
                "trying_ai_fallback",
                dno=dno_name,
                year=job.year,
                data_type=job.data_type,
                model=settings.ai_model,
            )
            
            prompt = self._build_prompt(dno_name, job.year, job.data_type)
            ai_result = await self._extract_with_ai(path, dno_name, job.year, job.data_type, prompt)
            
            if ai_result:
                extracted_data = ai_result.get("data", [])
                extraction_meta = ai_result.get("_extraction_meta", {})
                
                # ===== VALIDATE AI RESULT (same sanity check as regex) =====
                ai_passed, ai_reason = self._validate_extraction(extracted_data, job.data_type)
                
                if not ai_passed:
                    # AI also failed sanity check - log warning and auto-flag
                    logger.warning(
                        "ai_extraction_failed_sanity",
                        reason=ai_reason,
                        records=len(extracted_data),
                        dno=dno_name,
                        year=job.year,
                        data_type=job.data_type,
                        model=settings.ai_model,
                    )
                    
                    # Still use AI result (may have partial data) but flag for review
                    ctx["extracted_data"] = extracted_data
                    ctx["extraction_notes"] = f"AI extraction - FLAGGED: {ai_reason}"
                    ctx["extraction_method"] = "ai"
                    ctx["extraction_model"] = settings.ai_model
                    ctx["auto_flagged"] = True
                    ctx["auto_flag_reason"] = f"AI extraction sanity check failed: {ai_reason}"
                    
                    ctx["extraction_source_meta"] = {
                        "source": "ai",
                        "model": settings.ai_model,
                        "source_format": file_format,
                        "fallback_reason": reason,
                        "flagged": True,
                        "flag_reason": ai_reason,
                    }
                    
                    ctx["extraction_log"] = {
                        "prompt": prompt,
                        "response": extraction_meta.get("raw_response"),
                        "file_metadata": file_metadata,
                        "model": extraction_meta.get("model"),
                        "mode": extraction_meta.get("mode"),
                        "usage": extraction_meta.get("usage"),
                        "regex_fallback_reason": reason,
                        "ai_sanity_check_failed": ai_reason,
                    }
                    
                    job.context = ctx
                    flag_modified(job, 'context')
                    await db.commit()
                    
                    # Capture debug sample: regex failed, AI also failed
                    dno_slug = ctx.get("dno_slug", "unknown")
                    sample_capture = SampleCapture()
                    await sample_capture.capture(
                        category="debug",
                        dno_slug=dno_slug,
                        year=job.year,
                        data_type=job.data_type,
                        source_file_path=str(path),
                        source_format=file_format,
                        regex_result=records,
                        regex_fail_reason=reason,
                        ai_result=extracted_data,
                        ai_model=settings.ai_model,
                        prompt_used=prompt,
                        ai_fail_reason=ai_reason,
                    )
                    
                    return f"Extracted {len(extracted_data)} records using AI - FLAGGED: {ai_reason}"
                
                # AI passed sanity check - use it!
                logger.info(
                    "ai_extraction_success",
                    records=len(extracted_data),
                    dno=dno_name,
                    year=job.year,
                    data_type=job.data_type,
                    model=settings.ai_model,
                )
                
                ctx["extracted_data"] = extracted_data
                ctx["extraction_notes"] = ai_result.get("notes", "")
                ctx["extraction_method"] = "ai"
                ctx["extraction_model"] = settings.ai_model
                
                # Mark this as AI fallback (regex failed first)
                ctx["extraction_source_meta"] = {
                    "source": "ai",
                    "model": settings.ai_model,
                    "source_format": file_format,
                    "fallback_reason": reason,  # Why regex failed
                }
                
                ctx["extraction_log"] = {
                    "prompt": prompt,
                    "response": extraction_meta.get("raw_response"),
                    "file_metadata": file_metadata,
                    "model": extraction_meta.get("model"),
                    "mode": extraction_meta.get("mode"),
                    "usage": extraction_meta.get("usage"),
                    "regex_fallback_reason": reason,
                }
                
                job.context = ctx
                flag_modified(job, 'context')
                await db.commit()
                
                # Capture training sample: regex failed, AI succeeded
                dno_slug = ctx.get("dno_slug", "unknown")
                sample_capture = SampleCapture()
                await sample_capture.capture(
                    category="training",
                    dno_slug=dno_slug,
                    year=job.year,
                    data_type=job.data_type,
                    source_file_path=str(path),
                    source_format=file_format,
                    regex_result=records,
                    regex_fail_reason=reason,
                    ai_result=extracted_data,
                    ai_model=settings.ai_model,
                    prompt_used=prompt,
                )
                
                return f"Extracted {len(extracted_data)} records using AI fallback ({settings.ai_model}) - regex failed: {reason}"
        
        # ===== STEP 4: Both failed or AI not configured - use regex but flag =====
        logger.warning(
            "extraction_potentially_wrong",
            reason=reason,
            records=len(records),
            dno=dno_name,
            year=job.year,
            data_type=job.data_type,
            ai_enabled=settings.ai_enabled,
            ai_attempted=ai_result is not None if settings.ai_enabled else False,
        )
        
        # Capture debug sample when AI was attempted but completely failed (rate limited, API error)
        if settings.ai_enabled and ai_result is None:
            dno_slug = ctx.get("dno_slug", "unknown")
            sample_capture = SampleCapture()
            await sample_capture.capture(
                category="debug",
                dno_slug=dno_slug,
                year=job.year,
                data_type=job.data_type,
                source_file_path=str(path),
                source_format=file_format,
                regex_result=records,
                regex_fail_reason=reason,
                ai_result=None,
                ai_model=settings.ai_model,
                prompt_used=prompt,
                ai_fail_reason="AI extraction returned None (rate limited or API error)",
            )
        
        ctx["extracted_data"] = records
        ctx["extraction_notes"] = f"{method} extraction - FLAGGED: {reason}"
        ctx["extraction_method"] = method
        
        # Auto-flag for review
        ctx["auto_flagged"] = True
        ctx["auto_flag_reason"] = f"Extraction sanity check failed: {reason}"
        
        ctx["extraction_source_meta"] = {
            "source": method,
            "model": None,
            "source_format": file_format,
            "flagged": True,
            "flag_reason": reason,
        }
        
        ctx["extraction_log"] = {
            "prompt": f"File: {path.name}",
            "response": records,
            "file_metadata": file_metadata,
            "model": None,
            "mode": "regex_flagged",
            "usage": None,
            "sanity_check_failed": reason,
        }
        
        job.context = ctx
        flag_modified(job, 'context')
        await db.commit()
        
        return f"Extracted {len(records)} records using {method} - FLAGGED: {reason}"

    def _validate_extraction(self, records: list, data_type: str) -> tuple[bool, str]:
        """
        Validate extracted data passes sanity checks.
        
        Returns:
            Tuple of (passed: bool, reason: str)
        """
        if data_type == "netzentgelte":
            return self._validate_netzentgelte(records)
        else:  # hlzf
            return self._validate_hlzf(records)

    def _validate_netzentgelte(self, records: list) -> tuple[bool, str]:
        """
        Check netzentgelte has sufficient records with price values.
        
        Rules:
        - At least 2 records (small municipal utilities may only have MS and NS)
        - Each record must have at least leistung OR arbeit with actual value
        """
        if len(records) < 2:
            return False, f"Too few records: {len(records)} (minimum 2 required)"
        
        # Check each record has at least one price value
        valid_records = 0
        for record in records:
            leistung = record.get("leistung")
            arbeit = record.get("arbeit")
            leistung_unter = record.get("leistung_unter_2500h")
            arbeit_unter = record.get("arbeit_unter_2500h")
            
            # Check if value is valid (not None, not "-", not "N/A")
            def is_valid_value(v):
                if v is None:
                    return False
                v_str = str(v).strip().lower()
                return v_str not in ["-", "n/a", "null", "none", ""]
            
            # At least one price must be a valid value
            if any(is_valid_value(v) for v in [leistung, arbeit, leistung_unter, arbeit_unter]):
                valid_records += 1
        
        if valid_records < 2:
            return False, f"Too few valid records with prices: {valid_records} (minimum 2 required)"
        
        return True, "OK"

    def _validate_hlzf(self, records: list) -> tuple[bool, str]:
        """
        Check HLZF extraction quality.
        
        Rules:
        - At least 2 voltage levels (small DNOs may only have MS, MS/NS, NS)
        - At least one record has winter or herbst time window (peak load is in cold months)
        """
        if len(records) < 2:
            return False, f"Missing voltage levels: only {len(records)} extracted (minimum 2 required)"
        
        # Check if value is valid time data (not null, "-", or "entfällt")
        def is_valid_time(v):
            if v is None:
                return False
            v_str = str(v).strip().lower()
            return v_str not in ["-", "entfällt", "null", "none", ""]
        
        # Check at least one record has winter or herbst data (peak load times)
        has_peak_time = any(
            is_valid_time(record.get("winter")) or is_valid_time(record.get("herbst"))
            for record in records
        )
        
        if not has_peak_time:
            return False, "No records with winter or herbst time window (peak load times missing)"
        
        return True, "OK"


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
            logger.warning("ai_extraction_failed", error=str(e))
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
        """Extract using regex/HTML parser (primary extraction method)."""
        
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

IMPORTANT: Extract ALL voltage levels present in the document - the number varies by DNO:
- Large DNOs typically have 5 levels: HS, HS/MS, MS, MS/NS, NS
- Small municipal utilities often only have 3 levels: MS, MS/NS, NS (no high voltage infrastructure)
- TSOs may have HöS (Höchstspannung) instead of NS

Map these voltage level names to standardized abbreviations:
- Hochspannung / Hochspannungsnetz / "inHS" / "HS" → output as "HS"
- Umspannung Hoch-/Mittelspannung / "ausHS" / "HS/MS" → output as "HS/MS"
- Mittelspannung / Mittelspannungsnetz / "inMS" / "MS" / "MSP" → output as "MS"
- Umspannung Mittel-/Niederspannung / "ausMS" / "MS/NS" / "MSP/NSP" → output as "MS/NS"
- Niederspannung / Niederspannungsnetz / "inNS" / "NS" / "NSP" → output as "NS"
- Höchstspannung / "HöS" → output as "HöS" (rare, TSO only)
- Umspannung Höchst-/Hochspannung / "ausHöS" / "HöS/HS" → output as "HöS/HS" (rare, TSO only)

SKIP any "ausHÖS" or upstream TSO entries if extracting for a DNO (not TSO).

NOTE: The document may have ONE combined table OR SEPARATE tables per voltage level.
Voltage level names may be split across multiple lines in PDFs.

German electricity tariffs often have TWO sets of prices based on annual usage:
- "< 2.500 h/a" or "unter 2500h" (under 2500 hours/year usage)
- "≥ 2.500 h/a" or "über 2500h" (2500+ hours/year usage)

For EACH voltage level found, extract:
- voltage_level: Standardized abbreviation (HS, HS/MS, MS, MS/NS, NS)
- leistung_unter_2500h: Capacity price (Leistungspreis) for < 2500h in €/kW/a, or "-" if not available
- arbeit_unter_2500h: Work price (Arbeitspreis) for < 2500h in ct/kWh, or "-" if not available
- leistung: Capacity price (Leistungspreis) for ≥ 2500h in €/kW/a, or "-" if not available
- arbeit: Work price (Arbeitspreis) for ≥ 2500h in ct/kWh, or "-" if not available

If only one set of prices exists (no usage distinction), use leistung and arbeit fields only.
Use "-" for any price that doesn't exist for this DNO/voltage level (not null).

Return the structure:
{{
  "success": true,
  "data_type": "netzentgelte",
  "source_page": <page number>,
  "notes": "<observations about the table format and which voltage levels were found>",
  "voltage_levels_found": <number of voltage levels>,
  "data": [
    {{"voltage_level": "HS", "leistung_unter_2500h": "26.88", "arbeit_unter_2500h": "8.58", "leistung": "230.39", "arbeit": "0.44"}},
    {{"voltage_level": "HS/MS", ...}},
    ...
  ]
}}
"""
        else:  # hlzf
            return f"""Extract HLZF (Hochlastzeitfenster) data from this German electricity grid document.

DNO: {dno_name}
Year: {year}

IMPORTANT: Extract ALL voltage levels present in the document - the number varies by DNO:
- Large DNOs typically have 5 levels: HS, HS/MS, MS, MS/NS, NS
- Small municipal utilities often only have 3 levels: MS, MS/NS, NS (no high voltage infrastructure)
- TSOs may have HöS (Höchstspannung) instead of NS

Map these voltage level names to standardized abbreviations:
- Hochspannung / Hochspannungsnetz / "inHS" / "HS" → output as "HS"
- Umspannung Hoch-/Mittelspannung / "ausHS" / "HS/MS" → output as "HS/MS"
- Mittelspannung / Mittelspannungsnetz / "inMS" / "MS" / "MSP" → output as "MS"
- Umspannung Mittel-/Niederspannung / "ausMS" / "MS/NS" / "MSP/NSP" → output as "MS/NS"
- Niederspannung / Niederspannungsnetz / "inNS" / "NS" / "NSP" → output as "NS"
- Höchstspannung / "HöS" → output as "HöS" (rare, TSO only)
- Umspannung Höchst-/Hochspannung / "ausHöS" / "HöS/HS" → output as "HöS/HS" (rare, TSO only)

SKIP any upstream TSO entries if extracting for a DNO (not TSO).

NOTE: In PDF tables, voltage level names may be split across multiple lines.
The document may have ONE combined table OR SEPARATE tables per voltage level.
Season columns may appear in any order (Frühling, Sommer, Herbst, Winter).
Time columns may use "von/bis" format or direct time ranges.

For EACH voltage level found, extract:
- winter: Time window(s) for Dec-Feb
- fruehling: Time window(s) for Mar-May
- sommer: Time window(s) for Jun-Aug
- herbst: Time window(s) for Sep-Nov

Values for each season:
- Time window format: "HH:MM-HH:MM" (e.g., "07:30-15:30")
- Multiple windows: Separate with "\\n" (e.g., "07:30-13:00\\n17:00-19:30")
- No peak load times: Use "-" if explicitly marked as "entfällt" or no times for that season
- Note: It is NORMAL for Spring (Frühling) and Summer (Sommer) to have no peak times (use "-")

Return the structure:
{{
  "success": true,
  "data_type": "hlzf",
  "source_page": <page number where table was found>,
  "notes": "<observations about the table format and which voltage levels were found>",
  "voltage_levels_found": <number of voltage levels>,
  "data": [
    {{"voltage_level": "HS", "winter": "07:30-15:30\\n17:15-19:15", "fruehling": "-", "sommer": "-", "herbst": "11:15-14:00"}},
    {{"voltage_level": "HS/MS", "winter": "07:30-15:45\\n16:30-18:15", "fruehling": "-", "sommer": "-", "herbst": "16:45-17:30"}},
    ...
  ]
}}
"""

