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
from datetime import UTC, datetime
from urllib.parse import urlparse

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import normalize_voltage_level
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
            saved_count = await self._save_hlzf(
                db,
                job.dno_id,
                job.year,
                data,
                source_meta,
                auto_flagged,
                auto_flag_reason,
                force_override,
            )
        elif job.data_type == "netzentgelte":
            saved_count = await self._save_netzentgelte(
                db,
                job.dno_id,
                job.year,
                data,
                source_meta,
                auto_flagged,
                auto_flag_reason,
                force_override,
            )
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
        if "," in value:
            # Remove any dots (thousands separators in German)
            value = value.replace(".", "")
            # Replace comma with dot for decimal
            value = value.replace(",", ".")

        try:
            return float(value)
        except ValueError:
            logger.warning("parse_german_float_failed", value=value)
            return None

    def _normalize_voltage_level(self, raw: str) -> str:
        """Normalize voltage level via shared canonical backend mapping."""
        cleaned = " ".join(raw.replace("\n", " ").replace("\r", " ").split()).strip()
        normalized = normalize_voltage_level(cleaned)
        if normalized:
            return normalized
        logger.warning("unknown_voltage_level", raw=cleaned)
        return cleaned

    def _normalize_hlzf_time(
        self, value: list[dict[str, str]] | str | None
    ) -> list[dict[str, str]] | None:
        """Normalize HLZF time value to a JSON-ready array of {start, end} dicts.

        Accepts both structured arrays (from new extraction) and legacy strings.
        Always returns HH:MM:SS format with zero-padded hours.
        """

        def _norm_time(t: str) -> str:
            t = t.strip()
            m = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", t)
            if m:
                return f"{m.group(1).zfill(2)}:{m.group(2)}:{m.group(3) or '00'}"
            return t

        # Already a structured array — normalize times and pass through
        if isinstance(value, list):
            ranges = []
            for r in value:
                if isinstance(r, dict) and r.get("start") and r.get("end"):
                    ranges.append({"start": _norm_time(r["start"]), "end": _norm_time(r["end"])})
            return ranges if ranges else None

        # Legacy string fallback
        if value is None:
            return None

        value = value.strip()
        if not value or value.lower() in ("entfällt", "keine", "-"):
            return None

        def _parse_range(r: str) -> dict[str, str] | None:
            r = r.strip()
            m = re.match(r"^(.+?)\s*[-–—]\s*(.+)$", r)
            if m:
                return {"start": _norm_time(m.group(1)), "end": _norm_time(m.group(2))}
            m = re.match(r"^(\d{1,2}:\d{2}(?::\d{2})?)\s+(\d{1,2}:\d{2}(?::\d{2})?)$", r)
            if m:
                return {"start": _norm_time(m.group(1)), "end": _norm_time(m.group(2))}
            return None

        ranges = []
        for line in value.split("\n"):
            parsed = _parse_range(line)
            if parsed:
                ranges.append(parsed)

        return ranges if ranges else None

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
        """Save HLZF records using atomic bulk upsert (INSERT ... ON CONFLICT).

        Args:
            force_override: If True, override even verified records. If False, skip verified records.
        """
        source_meta = source_meta or {}

        # Filter to target year for multi-year PDFs (records tagged with 'year').
        # Records without a 'year' field are single-year and use the job's year.
        if records and any(r.get("year") is not None for r in records):
            records = [r for r in records if r.get("year") == year]
            logger.info(
                "hlzf_year_filtered",
                target_year=year,
                records_after_filter=len(records),
            )

        rows_to_upsert = []

        for record in records:
            raw_voltage = record.get("voltage_level", "").strip()
            if not raw_voltage:
                continue

            voltage_level = self._normalize_voltage_level(raw_voltage)
            rows_to_upsert.append(
                {
                    "dno_id": dno_id,
                    "year": year,
                    "voltage_level": voltage_level,
                    "winter": self._normalize_hlzf_time(record.get("winter")),
                    "fruehling": self._normalize_hlzf_time(record.get("fruehling")),
                    "sommer": self._normalize_hlzf_time(record.get("sommer")),
                    "herbst": self._normalize_hlzf_time(record.get("herbst")),
                    "extraction_source": source_meta.get("source"),
                    "extraction_model": source_meta.get("model"),
                    "extraction_source_format": source_meta.get("source_format"),
                    "verification_status": "flagged" if auto_flagged else "pending",
                    "flag_reason": auto_flag_reason if auto_flagged else None,
                }
            )

        if not rows_to_upsert:
            return 0

        # Merge rows with the same voltage_level by combining time windows.
        # The regex extractor may find multiple sub-tables for the same level.
        rows_to_upsert = self._merge_hlzf_by_voltage_level(rows_to_upsert)

        stmt = pg_insert(HLZFModel).values(rows_to_upsert)

        # Build SET clause for ON CONFLICT UPDATE
        update_cols = {
            "winter": stmt.excluded.winter,
            "fruehling": stmt.excluded.fruehling,
            "sommer": stmt.excluded.sommer,
            "herbst": stmt.excluded.herbst,
            "extraction_source": stmt.excluded.extraction_source,
            "extraction_model": stmt.excluded.extraction_model,
            "extraction_source_format": stmt.excluded.extraction_source_format,
            "verification_status": stmt.excluded.verification_status,
            "flag_reason": stmt.excluded.flag_reason,
        }

        # Skip verified records unless force_override is set
        where_clause = None if force_override else (HLZFModel.verification_status != "verified")

        stmt = stmt.on_conflict_do_update(
            index_elements=["dno_id", "year", "voltage_level"],
            set_=update_cols,
            where=where_clause,
        )

        await db.execute(stmt)
        saved = len(rows_to_upsert)
        logger.info("hlzf_saved", count=saved, dno_id=dno_id, year=year)
        return saved

    def _merge_hlzf_by_voltage_level(self, rows: list[dict]) -> list[dict]:
        """Merge HLZF rows sharing the same voltage_level.

        Multiple rows for one level can appear when the regex extractor hits
        separate sub-tables in the same PDF.  Time windows are combined with
        newlines; 'keine'/None values are dropped when real times exist.
        """
        seasons = ("winter", "fruehling", "sommer", "herbst")
        grouped: dict[str, list[dict]] = {}
        for row in rows:
            grouped.setdefault(row["voltage_level"], []).append(row)

        merged: list[dict] = []
        for _vl, group in grouped.items():
            if len(group) == 1:
                merged.append(group[0])
                continue

            base = dict(group[0])
            for season in seasons:
                combined: list[dict] = []
                seen: set[tuple[str, str]] = set()
                for row in group:
                    val = row.get(season)
                    if not val:
                        continue
                    for rng in val:
                        key = (rng["start"], rng["end"])
                        if key not in seen:
                            seen.add(key)
                            combined.append(rng)

                base[season] = combined if combined else None

            logger.debug(
                "hlzf_rows_merged",
                voltage_level=base["voltage_level"],
                source_rows=len(group),
            )
            merged.append(base)
        return merged

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
        """Save Netzentgelte records using atomic bulk upsert (INSERT ... ON CONFLICT).

        Args:
            force_override: If True, override even verified records. If False, skip verified records.
        """
        source_meta = source_meta or {}
        rows_to_upsert = []

        for record in records:
            raw_voltage = record.get("voltage_level", "").strip()
            if not raw_voltage:
                continue

            voltage_level = self._normalize_voltage_level(raw_voltage)

            # Map field names (AI may return different names)
            arbeit = record.get("arbeit") or record.get("arbeitspreis")
            leistung = record.get("leistung") or record.get("leistungspreis")
            arbeit_u2500 = record.get("arbeit_unter_2500h")
            leistung_u2500 = record.get("leistung_unter_2500h")

            rows_to_upsert.append(
                {
                    "dno_id": dno_id,
                    "year": year,
                    "voltage_level": voltage_level,
                    "arbeit": self._parse_german_float(arbeit),
                    "leistung": self._parse_german_float(leistung),
                    "arbeit_unter_2500h": self._parse_german_float(arbeit_u2500),
                    "leistung_unter_2500h": self._parse_german_float(leistung_u2500),
                    "extraction_source": source_meta.get("source"),
                    "extraction_model": source_meta.get("model"),
                    "extraction_source_format": source_meta.get("source_format"),
                    "verification_status": "flagged" if auto_flagged else "pending",
                    "flag_reason": auto_flag_reason if auto_flagged else None,
                }
            )

        if not rows_to_upsert:
            return 0

        # Deduplicate by conflict key (last entry wins) to avoid
        # CardinalityViolationError on batch INSERT ... ON CONFLICT
        deduped: dict[str, dict] = {}
        for row in rows_to_upsert:
            key = row["voltage_level"]
            deduped[key] = row
        rows_to_upsert = list(deduped.values())

        stmt = pg_insert(NetzentgelteModel).values(rows_to_upsert)

        # Build SET clause for ON CONFLICT UPDATE
        update_cols = {
            "arbeit": stmt.excluded.arbeit,
            "leistung": stmt.excluded.leistung,
            "arbeit_unter_2500h": stmt.excluded.arbeit_unter_2500h,
            "leistung_unter_2500h": stmt.excluded.leistung_unter_2500h,
            "extraction_source": stmt.excluded.extraction_source,
            "extraction_model": stmt.excluded.extraction_model,
            "extraction_source_format": stmt.excluded.extraction_source_format,
            "verification_status": stmt.excluded.verification_status,
            "flag_reason": stmt.excluded.flag_reason,
        }

        # Skip verified records unless force_override is set
        where_clause = (
            None if force_override else (NetzentgelteModel.verification_status != "verified")
        )

        stmt = stmt.on_conflict_do_update(
            index_elements=["dno_id", "year", "voltage_level"],
            set_=update_cols,
            where=where_clause,
        )

        await db.execute(stmt)
        saved = len(rows_to_upsert)
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
        profile.last_success_at = datetime.now(UTC)
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
