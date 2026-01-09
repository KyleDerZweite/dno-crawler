"""
Step 06: Finalize

Final step that stores extracted data and updates learning profiles.

What it does:
- Save extracted data to NetzentgelteModel or HLZFModel
- Save provenance to DataSourceModel
- Update DNOSourceProfile with what worked (for learning)
- Record successful URL patterns in CrawlPathPatternModel
- Mark job as completed

Learning updates:
- Store successful URL and pattern for future crawls
- Record path patterns for cross-DNO learning
- Store file format for this DNO
- Store any extraction hints from Gemini
- Reset consecutive failure counter on success

Output:
- Job marked as completed
- Data persisted to database
- Source profile and patterns updated for future crawls
"""

import re
from datetime import datetime
from urllib.parse import urlparse

import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CrawlJobModel, DNOSourceProfile, HLZFModel, NetzentgelteModel
from app.jobs.steps.base import BaseStep
from app.services.pattern_learner import PatternLearner

logger = structlog.get_logger()


class FinalizeStep(BaseStep):
    label = "Finalizing"
    description = "Saving data and updating learning profile..."

    async def run(self, db: AsyncSession, job: CrawlJobModel) -> str:
        ctx = job.context or {}
        data = ctx.get("extracted_data", [])
        is_valid = ctx.get("is_valid", False)

        if not is_valid or not data:
            # Record pattern failure if one was used
            discovered_pattern = ctx.get("discovered_via_pattern")
            if discovered_pattern:
                learner = PatternLearner()
                await learner.record_failure(db, discovered_pattern)

            # Don't save invalid data, but still complete the job
            return "Skipped data save (validation failed)"

        # =========================================================================
        # Save extracted data to database
        # =========================================================================
        saved_count = 0

        # Get extraction source metadata
        source_meta = ctx.get("extraction_source_meta", {})

        # Check if data should be auto-flagged (sanity check failed)
        auto_flagged = ctx.get("auto_flagged", False)
        auto_flag_reason = ctx.get("auto_flag_reason")

        # Check for force_override flag (from bulk extraction)
        force_override = ctx.get("force_override", False)

        if job.data_type == "hlzf":
            saved_count = await self._save_hlzf(db, job.dno_id, job.year, data, source_meta, auto_flagged, auto_flag_reason, force_override)
        elif job.data_type == "netzentgelte":
            saved_count = await self._save_netzentgelte(db, job.dno_id, job.year, data, source_meta, auto_flagged, auto_flag_reason, force_override)
        else:
            logger.warning("unknown_data_type", data_type=job.data_type)

        # =========================================================================
        # Update learning (always run on success)
        # =========================================================================
        found_url = ctx.get("found_url")
        dno_slug = ctx.get("dno_slug")

        if found_url and dno_slug:
            # Record successful pattern for cross-DNO learning
            learner = PatternLearner()
            await learner.record_success(
                db=db,
                url=found_url,
                dno_slug=dno_slug,
                data_type=job.data_type,
            )

            # Update DNO source profile
            await self._update_source_profile(
                db=db,
                dno_id=job.dno_id,
                data_type=job.data_type,
                ctx=ctx,
                year=job.year,
            )

        await db.commit()

        # Determine source description for message
        # Priority: found_url > dno_name > file path > "cache"
        source = ctx.get("found_url")
        if not source:
            source = ctx.get("dno_name")
        if not source:
            downloaded_file = ctx.get("downloaded_file", "")
            if downloaded_file:
                from pathlib import Path
                source = Path(downloaded_file).name
        if not source:
            source = "cache"

        return f"Saved {saved_count} records from {source}"

    def _parse_german_float(self, value: str | float | None) -> float | None:
        """
        Parse a number that may be in German format (comma as decimal separator).
        
        Handles:
        - '6,69' -> 6.69 (German decimal)
        - '1.234,56' -> 1234.56 (German thousands + decimal)
        - '6.69' -> 6.69 (already correct format)
        - 6.69 -> 6.69 (already a float)
        - None -> None
        - '' -> None
        """
        if value is None:
            return None

        # If already a number, return it
        if isinstance(value, (int, float)):
            return float(value)

        # Convert to string and clean
        value = str(value).strip()
        if not value:
            return None

        # Handle German number format:
        # In German: 1.234,56 means 1234.56 (dot for thousands, comma for decimal)
        # In English: 1,234.56 means 1234.56 (comma for thousands, dot for decimal)

        # Check if it's German format (contains comma as decimal separator)
        if ',' in value:
            # Remove any dots (thousands separators in German)
            value = value.replace('.', '')
            # Replace comma with dot for decimal
            value = value.replace(',', '.')

        try:
            return float(value)
        except ValueError:
            logger.warning("parse_german_float_failed", value=value)
            return None

    def _normalize_voltage_level(self, raw: str) -> str:
        """
        Normalize voltage level names to a consistent abbreviated format.
        
        Mappings:
        - Hochspannung, HöS, HS -> HS
        - Hochspannung mit Umspannung auf MS, HS/MS, Umspannung Hoch-/Mittelspannung, Umspannung zur Mittelspannung -> HS/MS
        - Mittelspannung, MS -> MS
        - Mittelspannung mit Umspannung auf NS, MS/NS, Umspannung Mittel-/Niederspannung, Umspannung zur Niederspannung -> MS/NS
        - Niederspannung, NS -> NS
        - Höchstspannung -> HöS (rarely used, keep as is)
        """
        raw = raw.strip()
        # Normalize newlines to spaces (pdfplumber sometimes splits across lines)
        raw = raw.replace('\n', ' ').replace('\r', ' ')
        raw = ' '.join(raw.split())  # Normalize whitespace
        raw_lower = raw.lower()

        # Already abbreviated - clean up spaces
        if raw in ("HS", "MS", "NS", "HöS"):
            return raw
        if raw in ("HS/MS", "MS/NS"):
            return raw

        # Check for Umspannung (Transformer) levels first (most specific)
        # "Umspannung zur X" means the transformation FROM the higher level TO X
        # So "Umspannung zur Mittelspannung" = HS/MS (from HS to MS)
        # And "Umspannung zur Niederspannung" = MS/NS (from MS to NS)
        if "umspannung" in raw_lower:
            # "Umspannung zur Mittelspannung" - transformation ending at MS = HS/MS
            if "zur mittelspannung" in raw_lower or "zur ms" in raw_lower:
                return "HS/MS"
            # "Umspannung zur Niederspannung" - transformation ending at NS = MS/NS
            if "zur niederspannung" in raw_lower or "zur ns" in raw_lower:
                return "MS/NS"
            # Generic Umspannung with both levels mentioned
            if ("hoch" in raw_lower and "mittel" in raw_lower) or "hs/ms" in raw_lower:
                return "HS/MS"
            if ("mittel" in raw_lower and "nieder" in raw_lower) or "ms/ns" in raw_lower:
                return "MS/NS"

        # Check for slash notation (explicit transformation levels)
        if "/" in raw_lower or "hs/ms" in raw_lower or "ms/ns" in raw_lower:
            if ("hoch" in raw_lower and "mittel" in raw_lower) or "hs/ms" in raw_lower:
                return "HS/MS"
            if ("mittel" in raw_lower and "nieder" in raw_lower) or "ms/ns" in raw_lower:
                return "MS/NS"

        # Check for single levels (HS, MS, NS) - only if NOT Umspannung
        if "hoch" in raw_lower or "hs" in raw_lower.split():
            return "HS"
        if "mittel" in raw_lower or "ms" in raw_lower.split():
            return "MS"
        if "nieder" in raw_lower or "ns" in raw_lower.split():
            return "NS"

        # Specific exact matches for short codes if regex failed
        if raw == "HS": return "HS"
        if raw == "MS": return "MS"
        if raw == "NS": return "NS"
        if raw == "HS/MS": return "HS/MS"
        if raw == "MS/NS": return "MS/NS"

        # Fallback: return cleaned up version
        logger.warning("unknown_voltage_level", raw=raw)
        return raw.strip()

    def _normalize_hlzf_time(self, value: str | None) -> str | None:
        """
        Normalize HLZF time values to consistent HH:MM:SS format.
        
        Handles:
        - "7:15" -> "07:15:00"
        - "07:15" -> "07:15:00" 
        - "7:15:00" -> "07:15:00"
        - "7:15-13:15" -> "07:15:00-13:15:00"
        - "18:00 20:00" -> "18:00:00-20:00:00" (space instead of hyphen - AI error)
        - Multiple ranges separated by newlines
        """
        if value is None:
            return None

        value = value.strip()
        if not value or value.lower() == "entfällt" or value == "-":
            return None

        def normalize_single_time(t: str) -> str:
            """Normalize a single time like '7:15' to '07:15:00'."""
            t = t.strip()
            # Match time with optional seconds: H:MM or HH:MM or H:MM:SS or HH:MM:SS
            match = re.match(r'^(\d{1,2}):(\d{2})(?::(\d{2}))?$', t)
            if match:
                hour = match.group(1).zfill(2)
                minute = match.group(2)
                second = match.group(3) if match.group(3) else "00"
                return f"{hour}:{minute}:{second}"
            return t  # Return as-is if not matching expected format

        def normalize_range(r: str) -> str:
            """Normalize a time range like '7:15-13:15' to '07:15:00-13:15:00'."""
            r = r.strip()

            # First, try to match range with any dash type: hyphen (-), en-dash (–), em-dash (—)
            match = re.match(r'^(.+?)\s*[-–—]\s*(.+)$', r)
            if match:
                start = normalize_single_time(match.group(1))
                end = normalize_single_time(match.group(2))
                return f"{start}-{end}"

            # Handle AI error: "18:00 20:00" (space instead of hyphen between two times)
            space_match = re.match(r'^(\d{1,2}:\d{2}(?::\d{2})?)\s+(\d{1,2}:\d{2}(?::\d{2})?)$', r)
            if space_match:
                start = normalize_single_time(space_match.group(1))
                end = normalize_single_time(space_match.group(2))
                return f"{start}-{end}"

            return normalize_single_time(r)  # Single time, not a range

        # Split by newlines (multiple ranges) and normalize each
        lines = value.split('\n')
        normalized_lines = [normalize_range(line) for line in lines if line.strip()]
        return '\n'.join(normalized_lines) if normalized_lines else None

    async def _save_hlzf(
        self,
        db: AsyncSession,
        dno_id: int,
        year: int,
        records: list[dict],
        source_meta: dict | None = None,
        auto_flagged: bool = False,
        auto_flag_reason: str | None = None,
        force_override: bool = False,
    ) -> int:
        """Save HLZF records with upsert logic.
        
        Args:
            force_override: If True, override even verified records. If False, skip verified records.
        """
        saved = 0
        source_meta = source_meta or {}

        for record in records:
            raw_voltage = record.get("voltage_level", "").strip()
            if not raw_voltage:
                continue

            # Normalize voltage level to standard format
            voltage_level = self._normalize_voltage_level(raw_voltage)

            # Check if record exists
            query = select(HLZFModel).where(
                and_(
                    HLZFModel.dno_id == dno_id,
                    HLZFModel.year == year,
                    HLZFModel.voltage_level == voltage_level,
                )
            )
            result = await db.execute(query)
            existing = result.scalar_one_or_none()

            if existing:
                # Skip verified records unless force_override is set
                if existing.verification_status == "verified" and not force_override:
                    logger.debug("hlzf_skip_verified", voltage_level=voltage_level, year=year)
                    continue

                # Update existing record - always overwrite with new values (including null)
                if "winter" in record:
                    existing.winter = self._normalize_hlzf_time(record.get("winter"))
                if "fruehling" in record:
                    existing.fruehling = self._normalize_hlzf_time(record.get("fruehling"))
                if "sommer" in record:
                    existing.sommer = self._normalize_hlzf_time(record.get("sommer"))
                if "herbst" in record:
                    existing.herbst = self._normalize_hlzf_time(record.get("herbst"))
                # Update extraction source (overwrite with new extraction)
                existing.extraction_source = source_meta.get("source")
                existing.extraction_model = source_meta.get("model")
                existing.extraction_source_format = source_meta.get("source_format")
                # Apply auto-flag if sanity check failed
                if auto_flagged:
                    existing.verification_status = "flagged"
                    existing.flag_reason = auto_flag_reason
                logger.debug("hlzf_updated", voltage_level=voltage_level, year=year, auto_flagged=auto_flagged)
            else:
                # Insert new record with extraction source
                new_record = HLZFModel(
                    dno_id=dno_id,
                    year=year,
                    voltage_level=voltage_level,
                    winter=self._normalize_hlzf_time(record.get("winter")),
                    fruehling=self._normalize_hlzf_time(record.get("fruehling")),
                    sommer=self._normalize_hlzf_time(record.get("sommer")),
                    herbst=self._normalize_hlzf_time(record.get("herbst")),
                    extraction_source=source_meta.get("source"),
                    extraction_model=source_meta.get("model"),
                    extraction_source_format=source_meta.get("source_format"),
                    # Apply auto-flag if sanity check failed
                    verification_status="flagged" if auto_flagged else "pending",
                    flag_reason=auto_flag_reason if auto_flagged else None,
                )
                db.add(new_record)
                logger.debug("hlzf_inserted", voltage_level=voltage_level, year=year, auto_flagged=auto_flagged)

            saved += 1

        logger.info("hlzf_saved", count=saved, dno_id=dno_id, year=year)
        return saved

    async def _save_netzentgelte(
        self,
        db: AsyncSession,
        dno_id: int,
        year: int,
        records: list[dict],
        source_meta: dict | None = None,
        auto_flagged: bool = False,
        auto_flag_reason: str | None = None,
        force_override: bool = False,
    ) -> int:
        """Save Netzentgelte records with upsert logic.
        
        Args:
            force_override: If True, override even verified records. If False, skip verified records.
        """
        saved = 0
        source_meta = source_meta or {}

        for record in records:
            raw_voltage = record.get("voltage_level", "").strip()
            if not raw_voltage:
                continue

            # Normalize voltage level to standard format
            voltage_level = self._normalize_voltage_level(raw_voltage)

            # Check if record exists
            query = select(NetzentgelteModel).where(
                and_(
                    NetzentgelteModel.dno_id == dno_id,
                    NetzentgelteModel.year == year,
                    NetzentgelteModel.voltage_level == voltage_level,
                )
            )
            result = await db.execute(query)
            existing = result.scalar_one_or_none()

            # Map field names (AI may return different names)
            arbeit = record.get("arbeit") or record.get("arbeitspreis")
            leistung = record.get("leistung") or record.get("leistungspreis")
            arbeit_u2500 = record.get("arbeit_unter_2500h")
            leistung_u2500 = record.get("leistung_unter_2500h")

            if existing:
                # Skip verified records unless force_override is set
                if existing.verification_status == "verified" and not force_override:
                    logger.debug("netzentgelte_skip_verified", voltage_level=voltage_level, year=year)
                    continue

                # Update existing record
                if arbeit is not None:
                    existing.arbeit = self._parse_german_float(arbeit)
                if leistung is not None:
                    existing.leistung = self._parse_german_float(leistung)
                if arbeit_u2500 is not None:
                    existing.arbeit_unter_2500h = self._parse_german_float(arbeit_u2500)
                if leistung_u2500 is not None:
                    existing.leistung_unter_2500h = self._parse_german_float(leistung_u2500)
                # Update extraction source (overwrite with new extraction)
                existing.extraction_source = source_meta.get("source")
                existing.extraction_model = source_meta.get("model")
                existing.extraction_source_format = source_meta.get("source_format")
                # Apply auto-flag if sanity check failed
                if auto_flagged:
                    existing.verification_status = "flagged"
                    existing.flag_reason = auto_flag_reason
                logger.debug("netzentgelte_updated", voltage_level=voltage_level, year=year, auto_flagged=auto_flagged)
            else:
                # Insert new record with extraction source
                new_record = NetzentgelteModel(
                    dno_id=dno_id,
                    year=year,
                    voltage_level=voltage_level,
                    arbeit=self._parse_german_float(arbeit),
                    leistung=self._parse_german_float(leistung),
                    arbeit_unter_2500h=self._parse_german_float(arbeit_u2500),
                    leistung_unter_2500h=self._parse_german_float(leistung_u2500),
                    extraction_source=source_meta.get("source"),
                    extraction_model=source_meta.get("model"),
                    extraction_source_format=source_meta.get("source_format"),
                    # Apply auto-flag if sanity check failed
                    verification_status="flagged" if auto_flagged else "pending",
                    flag_reason=auto_flag_reason if auto_flagged else None,
                )
                db.add(new_record)
                logger.debug("netzentgelte_inserted", voltage_level=voltage_level, year=year, auto_flagged=auto_flagged)

            saved += 1

        logger.info("netzentgelte_saved", count=saved, dno_id=dno_id, year=year)
        return saved

    async def _update_source_profile(
        self,
        db: AsyncSession,
        dno_id: int,
        data_type: str,
        ctx: dict,
        year: int,
    ):
        """Update or create DNO source profile with learned info."""
        # Find existing profile
        query = select(DNOSourceProfile).where(
            DNOSourceProfile.dno_id == dno_id,
            DNOSourceProfile.data_type == data_type,
        )
        result = await db.execute(query)
        profile = result.scalar_one_or_none()

        if not profile:
            profile = DNOSourceProfile(
                dno_id=dno_id,
                data_type=data_type,
            )
            db.add(profile)

        # Update profile with successful crawl info
        found_url = ctx.get("found_url")
        if found_url:
            profile.source_domain = self._extract_domain(found_url)
            profile.last_url = found_url
            profile.url_pattern = self._detect_pattern(found_url, year)

        profile.source_format = ctx.get("file_format") or ctx.get("found_content_type")
        profile.discovery_method = ctx.get("strategy")
        profile.discovered_via_pattern = ctx.get("discovered_via_pattern")
        profile.last_success_year = year
        profile.last_success_at = datetime.utcnow()
        profile.consecutive_failures = 0

    def _extract_domain(self, url: str | None) -> str | None:
        """Extract domain from URL."""
        if not url:
            return None
        try:
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.hostname
            if domain and domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception:
            return None

    def _detect_pattern(self, url: str | None, year: int) -> str | None:
        """Detect year pattern in URL for future use."""
        if not url:
            return None
        year_str = str(year)
        if year_str in url:
            return url.replace(year_str, "{year}")
        return None

