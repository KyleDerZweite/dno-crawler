"""
Step 03: Classify Documents

Post-download classification step that runs cheap regex extractors
on all downloaded files to identify which contain netzentgelte and/or hlzf data.

Algorithm:
1. For each downloaded file, run netzentgelte and hlzf extractors
2. Record extraction results (record count, pass/fail) per type
3. Pick best candidate per type (highest valid record count)
4. Move winning files from bulk-data/ to downloads/ with canonical naming
5. If nothing classified and first pass, set deepen_crawl flag

Output stored in job.context:
- classified_files: {data_type: {path, format, record_count, source_url}}
- unclassified_files: list of files that didn't match any type
- deepen_crawl: True if classify found nothing and deeper crawl should be tried
"""

import asyncio
import hashlib
import re
import shutil
from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import CrawlJobModel, DownloadRegistryModel
from app.jobs.steps.base import BaseStep

logger = structlog.get_logger()


class ClassifyStep(BaseStep):
    label = "Classifying Documents"
    description = "Running regex extractors to identify data in downloaded documents..."

    async def run(self, db: AsyncSession, job: CrawlJobModel) -> str:
        ctx = job.context or {}
        dno_slug = ctx.get("dno_slug", "unknown")
        log = logger.bind(dno=dno_slug, year=job.year)

        downloaded_files = ctx.get("downloaded_files", [])
        if not downloaded_files:
            ctx["classified_files"] = {}
            ctx["unclassified_files"] = []
            job.context = ctx
            await db.commit()
            return "No files to classify"

        # Track best candidate per data type
        best: dict[str, dict] = {}  # {data_type: {path, format, record_count, source_url}}
        unclassified: list[dict] = []

        for file_info in downloaded_files:
            file_path = Path(file_info["path"])
            file_format = file_info["format"]
            source_url = file_info.get("url", "")

            if not file_path.exists():
                log.warning("classify_file_missing", path=str(file_path))
                continue

            # Extract text once — reused for year detection and keyword fallback
            file_text = await self._extract_text(file_path, file_format, db)

            # Detect year from file content
            detected_year = self._detect_year_from_text(file_text, file_format)

            # Run extractors on this file
            netz_count = await self._try_netzentgelte(file_path, file_format, job.year)
            hlzf_count = await self._try_hlzf(file_path, file_format, job.year)

            # Keyword fallback: if regex extraction failed, check if the
            # file content strongly matches the expected data type so the
            # AI extractor in step 04 gets a chance to process it.
            netz_keyword = False
            hlzf_keyword = False
            if netz_count < 2:
                netz_keyword = self._keyword_match_netzentgelte(file_text)
            if hlzf_count < 2:
                hlzf_keyword = self._keyword_match_hlzf(file_text)

            log.debug(
                "classify_result",
                file=file_path.name,
                format=file_format,
                detected_year=detected_year,
                netz_records=netz_count,
                hlzf_records=hlzf_count,
                netz_keyword=netz_keyword,
                hlzf_keyword=hlzf_keyword,
            )

            # Determine the classification key suffix for non-target years.
            # For HLZF: if extraction succeeded (count > 0), use job.year since that's
            # what _try_hlzf filtered to. For netzentgelte: use detected_year.
            netz_year = detected_year
            netz_is_target = netz_year is None or netz_year == job.year
            netz_year_suffix = "" if netz_is_target else f":{netz_year}"

            # HLZF: if regex extraction found records, those are for job.year by design
            hlzf_year = job.year if hlzf_count > 0 else detected_year
            hlzf_is_target = hlzf_year is None or hlzf_year == job.year
            hlzf_year_suffix = "" if hlzf_is_target else f":{hlzf_year}"

            classified = False

            # Effective counts: regex extraction result, or keyword match → 0
            # (record_count=0 signals to extract step that AI is needed)
            netz_effective = netz_count if netz_count >= 2 else (0 if netz_keyword else -1)
            hlzf_effective = hlzf_count if hlzf_count >= 2 else (0 if hlzf_keyword else -1)

            # Check netzentgelte (regex ≥2 records, or keyword match)
            if netz_effective >= 0:
                key = f"netzentgelte{netz_year_suffix}"
                if self._is_better_candidate(netz_effective, file_format, best.get(key)):
                    best[key] = {
                        "path": str(file_path),
                        "format": file_format,
                        "record_count": netz_effective,
                        "source_url": source_url,
                        "detected_year": netz_year,
                    }
                classified = True

            # Check hlzf (regex ≥2 records, or keyword match)
            if hlzf_effective >= 0:
                key = f"hlzf{hlzf_year_suffix}"
                if self._is_better_candidate(hlzf_effective, file_format, best.get(key)):
                    best[key] = {
                        "path": str(file_path),
                        "format": file_format,
                        "record_count": hlzf_effective,
                        "source_url": source_url,
                        "detected_year": hlzf_year,
                    }
                classified = True

            if not classified:
                unclassified.append(
                    {
                        "path": str(file_path),
                        "format": file_format,
                        "url": source_url,
                        "netz_records": netz_count,
                        "hlzf_records": hlzf_count,
                    }
                )

        # Cross-type dedup: if the same file path won for both netzentgelte
        # and hlzf (same year suffix), keep only the type with the higher
        # record count.  A genuine HLZF document is 1-2 pages with time
        # windows; a 12-page netzentgelte PDF containing the word "hochlast"
        # somewhere is not HLZF.
        best = self._dedup_cross_type(best, log)

        # Build a lookup of which data_type each file won for (path -> data_type)
        winning_paths: dict[str, str] = {}
        for data_type_key, info in best.items():
            winning_paths[info["path"]] = data_type_key.split(":")[0]

        # Move winning files to downloads/ with canonical naming
        downloads_dir = Path(settings.downloads_path) / dno_slug
        downloads_dir.mkdir(parents=True, exist_ok=True)

        for data_type_key, info in best.items():
            src = Path(info["path"])
            ext = src.suffix or f".{info['format']}"
            # Parse key: "netzentgelte" or "netzentgelte:2025"
            if ":" in data_type_key:
                base_type, year_str = data_type_key.split(":", 1)
                file_year = int(year_str)
            else:
                base_type = data_type_key
                file_year = info.get("detected_year") or job.year
            canonical_name = f"{dno_slug}-{base_type}-{file_year}{ext}"
            dest = downloads_dir / canonical_name

            try:
                await asyncio.to_thread(shutil.copy2, str(src), str(dest))
                info["path"] = str(dest)
                log.info(
                    "classified_file_moved",
                    data_type=data_type_key,
                    src=src.name,
                    dest=canonical_name,
                    records=info["record_count"],
                )
            except Exception as e:
                log.warning("classify_move_failed", error=str(e), src=str(src))
                # Keep original path if move fails

        # =================================================================
        # Persist classification results to download registry
        # =================================================================
        dno_id = ctx.get("dno_id")
        if dno_id:
            await self._update_registry(
                db, dno_id, job.year, job.id, downloaded_files, best, unclassified, log
            )

        # Check if we should deepen the crawl
        crawl_pass = ctx.get("crawl_pass", 1)
        if not best and crawl_pass == 1:
            ctx["deepen_crawl"] = True
            log.info(
                "classify_nothing_found",
                files_checked=len(downloaded_files),
                triggering_deeper_crawl=True,
            )

        ctx["classified_files"] = best
        ctx["unclassified_files"] = unclassified
        job.context = ctx
        await db.commit()

        # Build result message
        parts = []
        for dt, info in best.items():
            parts.append(f"{dt}: {info['record_count']} records")

        if parts:
            return f"Classified: {', '.join(parts)} ({len(unclassified)} unclassified)"

        if ctx.get("deepen_crawl"):
            return f"No data found in {len(downloaded_files)} files - will deepen crawl"

        return f"No data found in {len(downloaded_files)} files"

    @staticmethod
    def _format_priority(fmt: str) -> int:
        """Return a priority score for file formats. PDFs are preferred."""
        if fmt == "pdf":
            return 2
        if fmt in ("xlsx", "xls", "csv"):
            return 1
        return 0  # html and others

    def _is_better_candidate(
        self, record_count: int, file_format: str, current_best: dict | None
    ) -> bool:
        """Check if a new candidate beats the current best.

        Higher record_count always wins. On ties, prefer PDF over HTML.
        """
        if current_best is None:
            return True
        cur_count = current_best["record_count"]
        if record_count != cur_count:
            return record_count > cur_count
        # Tiebreaker: prefer PDF over HTML/other formats
        return self._format_priority(file_format) > self._format_priority(current_best["format"])

    @staticmethod
    def _dedup_cross_type(
        best: dict[str, dict], log: structlog.stdlib.BoundLogger
    ) -> dict[str, dict]:
        """Remove cross-type duplicates where the same file won for both types.

        Groups entries by year suffix and checks if the same file path appears
        under both netzentgelte and hlzf.  Keeps only the type with higher
        record_count; on a tie keeps netzentgelte (more common data type).
        """
        # Group keys by year suffix
        suffixes: set[str] = set()
        for key in best:
            suffix = key.split(":", 1)[1] if ":" in key else ""
            suffixes.add(suffix)

        keys_to_remove: list[str] = []

        for suffix in suffixes:
            netz_key = f"netzentgelte:{suffix}" if suffix else "netzentgelte"
            hlzf_key = f"hlzf:{suffix}" if suffix else "hlzf"

            netz_info = best.get(netz_key)
            hlzf_info = best.get(hlzf_key)

            if not netz_info or not hlzf_info:
                continue

            if netz_info["path"] != hlzf_info["path"]:
                continue

            # Same file classified as both types — keep the stronger match
            netz_count = netz_info["record_count"]
            hlzf_count = hlzf_info["record_count"]

            if hlzf_count > netz_count:
                keys_to_remove.append(netz_key)
                log.info(
                    "cross_type_dedup",
                    kept=hlzf_key,
                    removed=netz_key,
                    file=Path(hlzf_info["path"]).name,
                )
            else:
                keys_to_remove.append(hlzf_key)
                log.info(
                    "cross_type_dedup",
                    kept=netz_key,
                    removed=hlzf_key,
                    file=Path(netz_info["path"]).name,
                )

        for key in keys_to_remove:
            del best[key]

        return best

    async def _update_registry(
        self,
        db: AsyncSession,
        dno_id: int,
        year: int,
        job_id: int,
        downloaded_files: list[dict],
        best: dict[str, dict],
        unclassified: list[dict],
        log,
    ) -> None:
        """Upsert classification results into the download registry."""
        # Build a lookup: file_path -> winning data_type
        winning_paths: dict[str, str] = {}
        for data_type_key, info in best.items():
            winning_paths[info["path"]] = data_type_key.split(":")[0]

        # Build a lookup: file_path -> unclassified detail
        unclassified_paths: dict[str, dict] = {}
        for entry in unclassified:
            unclassified_paths[entry["path"]] = entry

        upserted = 0
        for file_info in downloaded_files:
            url = file_info.get("url", "")
            if not url or url.startswith("cache://"):
                continue

            url_hash = hashlib.md5(url.encode()).hexdigest()[:32]
            file_path = file_info.get("path", "")

            # Determine classification
            classification = "unclassified"
            detail: dict = {}
            if file_path in winning_paths:
                classification = winning_paths[file_path]
            elif file_path in unclassified_paths:
                uc = unclassified_paths[file_path]
                # If regex found zero records for both types, mark irrelevant
                if uc.get("netz_records", 0) <= 0 and uc.get("hlzf_records", 0) <= 0:
                    classification = "irrelevant"
                detail = {
                    "netz_records": uc.get("netz_records", 0),
                    "hlzf_records": uc.get("hlzf_records", 0),
                }

            # Upsert: check if entry exists for this (dno_id, url_hash)
            result = await db.execute(
                select(DownloadRegistryModel).where(
                    DownloadRegistryModel.dno_id == dno_id,
                    DownloadRegistryModel.url_hash == url_hash,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.classification = classification
                existing.classification_detail = detail or existing.classification_detail
                existing.crawl_job_id = job_id
                existing.file_path = file_path
            else:
                db.add(
                    DownloadRegistryModel(
                        dno_id=dno_id,
                        year=year,
                        crawl_job_id=job_id,
                        source_url=url,
                        url_hash=url_hash,
                        file_path=file_path,
                        file_hash=file_info.get("content_hash"),
                        file_format=file_info.get("format"),
                        file_size_bytes=file_info.get("size_bytes"),
                        classification=classification,
                        classification_detail=detail or None,
                    )
                )
            upserted += 1

        if upserted:
            await db.commit()
            log.info("download_registry_updated", upserted=upserted)

    async def _extract_text(
        self, file_path: Path, file_format: str, db: AsyncSession | None = None
    ) -> str:
        """Extract plain text from a file for classification heuristics.

        For scanned PDFs (images with little embedded text), falls back to
        vision AI to OCR the pages — returning the text so keyword matchers
        and year detection work naturally.
        """
        try:
            if file_format == "pdf":
                import pdfplumber

                def _read_all_pages():
                    with pdfplumber.open(file_path) as pdf:
                        return "\n".join(page.extract_text() or "" for page in pdf.pages)

                text = await asyncio.to_thread(_read_all_pages)

                # If pdfplumber got very little text, the PDF is likely scanned
                if len(text.strip()) < 100 and db is not None:
                    ocr_text = await self._ocr_scanned_pdf(file_path, db)
                    if ocr_text:
                        return ocr_text

                return text
            elif file_format in ("html", "htm"):
                raw = await asyncio.to_thread(
                    file_path.read_text, encoding="utf-8", errors="replace"
                )
                return re.sub(r"<[^>]+>", " ", raw)
        except Exception as e:
            logger.debug("text_extraction_failed", file=file_path.name, error=str(e))
        return ""

    async def _ocr_scanned_pdf(self, file_path: Path, db: AsyncSession) -> str | None:
        """Use vision AI to OCR a scanned PDF for classification.

        Sends the PDF to the vision AI model with a lightweight prompt asking
        it to transcribe all visible text. Returns the transcribed text so
        keyword matchers and year detection work naturally.
        """
        try:
            from app.services.ai.gateway import AIGateway

            gateway = AIGateway(db)

            logger.info("ocr_scanned_pdf_start", file=file_path.name)

            prompt = (
                "Transcribe ALL visible text from this scanned PDF document. "
                "Preserve table structure using | as column delimiter and newlines for rows. "
                "Include all numbers, dates, voltage level names (e.g. Mittelspannung, MS, NS, HS), "
                "time windows (e.g. 07:30-15:30), price values, and season names exactly as shown. "
                "Return ONLY the raw transcribed text, no JSON, no commentary."
            )

            ocr_text = await gateway.ocr_pdf(file_path, prompt)

            if ocr_text:
                logger.info(
                    "ocr_scanned_pdf_done",
                    file=file_path.name,
                    text_len=len(ocr_text),
                )
            return ocr_text

        except Exception as e:
            logger.warning("ocr_scanned_pdf_failed", file=file_path.name, error=str(e))
            return None

    @staticmethod
    def _detect_year_from_text(text: str, file_format: str = "") -> int | None:
        """Detect the data year from already-extracted text.

        Searches for 4-digit years (20xx) near relevant keywords.
        Returns the detected year or None if ambiguous/not found.

        For HTML files with many year references (download index pages),
        returns None to avoid false classification with a wrong year.
        """
        if not text:
            return None

        keywords = (
            r"(?:Netzentgelt|Entgelt|Hochlastzeitfenster|Netznutzung|Preisblatt|gültig|Gültigkeit)"
        )
        # Use word boundaries (\b) to prevent matching years embedded in account
        # numbers (e.g. "50363120342" → false "2034") or prices ("0,02040000").
        pattern = rf"(?:{keywords}).{{0,100}}\b(20\d{{2}})\b|\b(20\d{{2}})\b.{{0,100}}{keywords}"
        matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)

        years: set[int] = set()
        for groups in matches:
            for g in groups:
                if g:
                    years.add(int(g))

        if len(years) == 1:
            return years.pop()

        if years:
            # HTML files with 3+ distinct years are likely download index pages,
            # not single-year data documents.  Return None to avoid picking a
            # wrong year (e.g. 2027 from a page listing 2020-2027 links).
            if file_format in ("html", "htm") and len(years) >= 3:
                return None
            return max(years)

        return None

    @staticmethod
    def _keyword_match_hlzf(text: str) -> bool:
        """Check if text strongly matches HLZF content.

        Requires ALL of:
        - At least one strong HLZF keyword in the title area (first 500 chars)
        - At least one voltage level keyword (MS, NS, Mittelspannung, etc.)
        - Multiple time patterns (HH:MM)
        """
        if not text:
            return False

        text_lower = text.lower()
        # Check title area for strong keywords to avoid false positives from
        # documents that mention "Hochlast" deep in unrelated content.
        title_area = text_lower[:500]

        # Must contain at least one strong HLZF keyword in title area
        hlzf_keywords = [
            "hochlastzeitfenster",
            "hochlastzeit",
            "atypische netznutzung",
        ]
        if not any(kw in title_area for kw in hlzf_keywords):
            return False

        # Must contain voltage level references
        vl_keywords = [
            "mittelspannung",
            "niederspannung",
            "hochspannung",
            "umspannung",
        ]
        # Also check for standalone abbreviations with word boundaries
        has_vl = any(kw in text_lower for kw in vl_keywords)
        if not has_vl:
            has_vl = bool(re.search(r"\b(?:MS|NS|HS)(?:/(?:MS|NS|HS))?\b", text))
        if not has_vl:
            return False

        # Must contain multiple time patterns (HH:MM)
        time_hits = re.findall(r"\d{1,2}:\d{2}", text)
        return len(time_hits) >= 4  # At least 2 von/bis pairs

    @staticmethod
    def _keyword_match_netzentgelte(text: str) -> bool:
        """Check if text strongly matches Netzentgelte content.

        Requires ALL of:
        - At least one strong Netzentgelte keyword in the title area (first 500 chars)
        - At least one voltage level keyword
        - Multiple decimal number patterns (prices)
        """
        if not text:
            return False

        text_lower = text.lower()
        # Check title area for strong keywords to avoid false positives from
        # documents like "Ergaenzende Bedingungen" or "Allgemeine Bedingungen"
        # that mention voltage levels and prices but are not tariff sheets.
        title_area = text_lower[:500]

        # Reject documents that are NOT standard netzentgelte even though
        # they contain "netzentgelt" in the title.
        reject_prefixes = ["individuelle", "vermiedene", "referenzpreis"]
        if any(rp in title_area for rp in reject_prefixes):
            return False

        # Must contain at least one strong Netzentgelte keyword in title area
        netz_keywords = [
            "netzentgelt",
            "netznutzungsentgelt",
            "leistungspreis",
            "arbeitspreis",
        ]
        # Also accept "preisblatt" but only when combined with a grid keyword
        has_preisblatt = "preisblatt" in title_area and any(
            kw in title_area for kw in ("netz", "strom", "entgelt")
        )
        if not has_preisblatt and not any(kw in title_area for kw in netz_keywords):
            return False

        # Must contain voltage level references
        vl_keywords = [
            "mittelspannung",
            "niederspannung",
            "hochspannung",
            "umspannung",
        ]
        has_vl = any(kw in text_lower for kw in vl_keywords)
        if not has_vl:
            has_vl = bool(re.search(r"\b(?:MS|NS|HS)(?:/(?:MS|NS|HS))?\b", text))
        if not has_vl:
            return False

        # Must contain multiple decimal number patterns (XX,X or XX.X style prices)
        price_hits = re.findall(r"\d{1,3}[,.]\d{1,4}", text)
        return len(price_hits) >= 4

    async def _try_netzentgelte(self, file_path: Path, file_format: str, year: int) -> int:
        """Try extracting netzentgelte data, return valid record count."""
        try:
            if file_format == "pdf":
                from app.services.extraction.pdf_extractor import extract_netzentgelte_from_pdf

                records = await asyncio.to_thread(extract_netzentgelte_from_pdf, file_path)
            elif file_format in ("html", "htm"):
                # No HTML parser for netzentgelte yet, return 0
                return 0
            else:
                return 0

            # Sanity check: count records with valid price values
            valid = 0
            for record in records:
                values = [
                    record.get("leistung"),
                    record.get("arbeit"),
                    record.get("leistung_unter_2500h"),
                    record.get("arbeit_unter_2500h"),
                ]
                if any(self._is_valid_value(v) for v in values):
                    valid += 1

            return valid
        except Exception as e:
            logger.debug("netzentgelte_extract_failed", file=file_path.name, error=str(e))
            return 0

    async def _try_hlzf(self, file_path: Path, file_format: str, year: int) -> int:
        """Try extracting hlzf data, return valid record count.

        For multi-year PDFs (records tagged with 'year'), counts only records
        matching the target year to avoid inflated scores vs single-year files.
        """
        try:
            if file_format == "pdf":
                from app.services.extraction.pdf_extractor import extract_hlzf_from_pdf

                records = await asyncio.to_thread(extract_hlzf_from_pdf, file_path)
            elif file_format in ("html", "htm"):
                from app.services.extraction.html_extractor import extract_hlzf_from_html

                html_content = await asyncio.to_thread(
                    file_path.read_text, encoding="utf-8", errors="replace"
                )
                records = extract_hlzf_from_html(html_content, year)
            else:
                return 0

            # For multi-year PDFs, count only target year records
            if records and any(r.get("year") is not None for r in records):
                target_records = [r for r in records if r.get("year") == year]
                return len(target_records)

            return len(records)
        except Exception as e:
            logger.debug("hlzf_extract_failed", file=file_path.name, error=str(e))
            return 0

    @staticmethod
    def _is_valid_value(v) -> bool:
        """Check if an extracted value is a real (non-placeholder) value."""
        if v is None:
            return False
        v_str = str(v).strip().lower()
        return v_str not in ("-", "n/a", "null", "none", "")
