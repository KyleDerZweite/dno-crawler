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
from app.services.extraction.prompts import build_extraction_prompt
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
        prompt = None
        
        from app.services.ai.gateway import AIGateway
        gateway = AIGateway(db)
        
        # Determine needs based on file extension
        # Note: PDF needs separate handling in gateway but effectively needs file support
        # logic here mirrors gateway.extract()
        suffix = path.suffix.lower()
        needs_vision = suffix in {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp"}
        needs_files = suffix == ".pdf"
        
        configs = await gateway.get_sorted_configs(
            needs_vision=needs_vision,
            needs_files=needs_files
        )
        is_ai_enabled = len(configs) > 0
        primary_model = configs[0].model if configs else "unknown"

        logger.info(
            "ai_config_debug",
            file=path.name,
            suffix=suffix,
            needs_vision=needs_vision,
            needs_files=needs_files,
            configs_found=len(configs),
            primary_model=primary_model,
            is_ai_enabled=is_ai_enabled
        )

        if is_ai_enabled:
            logger.info(
                "trying_ai_fallback",
                dno=dno_name,
                year=job.year,
                data_type=job.data_type,
                model=primary_model,
            )

            prompt = self._build_prompt(dno_name, job.year, job.data_type)
            ai_result = await self._extract_with_ai(path, dno_name, job.year, job.data_type, prompt, db)

            if ai_result:
                extracted_data = ai_result.get("data", [])
                extraction_meta = ai_result.get("_extraction_meta", {})
                used_model = extraction_meta.get("model", "unknown")

                # ===== POST-PROCESS AI RESULTS =====
                # Clean up common formatting issues (k.A., Uhr, German decimals, spaces)
                from app.core.parsers import clean_ai_extraction_result
                extracted_data = clean_ai_extraction_result(extracted_data, job.data_type)

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
                        model=used_model,
                    )

                    # Still use AI result (may have partial data) but flag for review
                    ctx["extracted_data"] = extracted_data
                    ctx["extraction_notes"] = f"AI extraction - FLAGGED: {ai_reason}"
                    ctx["extraction_method"] = "ai"
                    ctx["extraction_model"] = used_model
                    ctx["auto_flagged"] = True
                    ctx["auto_flag_reason"] = f"AI extraction sanity check failed: {ai_reason}"

                    ctx["extraction_source_meta"] = {
                        "source": "ai",
                        "model": used_model,
                        "source_format": file_format,
                        "fallback_reason": reason,
                        "flagged": True,
                        "flag_reason": ai_reason,
                    }

                    ctx["extraction_log"] = {
                        "prompt": prompt,
                        "response": extraction_meta.get("raw_response"),
                        "file_metadata": file_metadata,
                        "model": used_model,
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
                        ai_model=used_model,
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
                    model=used_model,
                )

                ctx["extracted_data"] = extracted_data
                ctx["extraction_notes"] = ai_result.get("notes", "")
                ctx["extraction_method"] = "ai"
                ctx["extraction_model"] = used_model

                # Mark this as AI fallback (regex failed first)
                ctx["extraction_source_meta"] = {
                    "source": "ai",
                    "model": used_model,
                    "source_format": file_format,
                    "fallback_reason": reason,  # Why regex failed
                }

                ctx["extraction_log"] = {
                    "prompt": prompt,
                    "response": extraction_meta.get("raw_response"),
                    "file_metadata": file_metadata,
                    "model": used_model,
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
                    ai_model=used_model,
                    prompt_used=prompt,
                )

                return f"Extracted {len(extracted_data)} records using AI fallback ({used_model}) - regex failed: {reason}"

        # ===== STEP 4: Both failed or AI not configured - use regex but flag =====
        logger.warning(
            "extraction_potentially_wrong",
            reason=reason,
            records=len(records),
            dno=dno_name,
            year=job.year,
            data_type=job.data_type,
            ai_enabled=is_ai_enabled,
            ai_attempted=ai_result is not None if is_ai_enabled else False,
        )

        # Capture debug sample when AI was attempted but completely failed (rate limited, API error)
        if is_ai_enabled and ai_result is None:
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
                ai_model="unknown",
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
        prompt: str,
        db: AsyncSession
    ) -> dict | None:
        """Extract data using AI (auto-routes to text or vision mode)."""
        try:
            from app.services.ai.gateway import AIGateway, NoProviderAvailableError

            # Gateway requires DB session
            gateway = AIGateway(db)
            return await gateway.extract(file_path, prompt)
            
        except NoProviderAvailableError as e:
            logger.warning("ai_extraction_failed_no_provider", error=str(e))
            return None
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
            extract_hlzf_from_pdf,
            extract_netzentgelte_from_pdf,
        )

        if data_type == "netzentgelte":
            records = await asyncio.to_thread(extract_netzentgelte_from_pdf, file_path)
        else:  # hlzf
            records = await asyncio.to_thread(extract_hlzf_from_pdf, file_path)

        return records, "pdf_regex"

    def _build_prompt(self, dno_name: str, year: int, data_type: str) -> str:
        """Build the extraction prompt for AI using centralized prompts."""
        return build_extraction_prompt(dno_name, year, data_type)
