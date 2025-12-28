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

from datetime import datetime
from urllib.parse import urlparse

import structlog
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CrawlJobModel, DNOSourceProfile, NetzentgelteModel, HLZFModel
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
        
        if job.data_type == "hlzf":
            saved_count = await self._save_hlzf(db, job.dno_id, job.year, data)
        elif job.data_type == "netzentgelte":
            saved_count = await self._save_netzentgelte(db, job.dno_id, job.year, data)
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
    
    def _normalize_voltage_level(self, raw: str) -> str:
        """
        Normalize voltage level names to a consistent abbreviated format.
        
        Mappings:
        - Hochspannung, HöS, HS -> HS
        - Hochspannung mit Umspannung auf MS, HS/MS, Umspannung Hoch-/Mittelspannung -> HS/MS
        - Mittelspannung, MS -> MS
        - Mittelspannung mit Umspannung auf NS, MS/NS, Umspannung Mittel-/Niederspannung -> MS/NS
        - Niederspannung, NS -> NS
        - Höchstspannung -> HöS (rarely used, keep as is)
        """
        raw = raw.strip()
        raw_lower = raw.lower()
        
        # Already abbreviated - clean up spaces
        if raw in ("HS", "MS", "NS", "HöS"):
            return raw
        if raw in ("HS/MS", "MS/NS"):
            return raw
        
        # Check for Umspannung (Transformer) levels first (most specific)
        if "umspannung" in raw_lower or "/" in raw_lower or "hs/ms" in raw_lower or "ms/ns" in raw_lower:
            # HS/MS variants
            if ("hoch" in raw_lower and "mittel" in raw_lower) or "hs/ms" in raw_lower:
                return "HS/MS"
            # MS/NS variants
            if ("mittel" in raw_lower and "nieder" in raw_lower) or "ms/ns" in raw_lower:
                return "MS/NS"
            # Implicit MS/NS: "Umspannung zur Niederspannung" usually implies MS->NS
            if "nieder" in raw_lower and "umspannung" in raw_lower:
                return "MS/NS"
        
        # Check for single levels (HS, MS, NS)
        if "hoch" in raw_lower or "hs" in raw_lower.split(): # Split to avoid matching 'hs' inside other words if any
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
    
    async def _save_hlzf(
        self,
        db: AsyncSession,
        dno_id: int,
        year: int,
        records: list[dict],
    ) -> int:
        """Save HLZF records with upsert logic."""
        saved = 0
        
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
                # Update existing record
                existing.winter = record.get("winter") or existing.winter
                existing.fruehling = record.get("fruehling") or existing.fruehling
                existing.sommer = record.get("sommer") or existing.sommer
                existing.herbst = record.get("herbst") or existing.herbst
                logger.debug("hlzf_updated", voltage_level=voltage_level, year=year)
            else:
                # Insert new record
                new_record = HLZFModel(
                    dno_id=dno_id,
                    year=year,
                    voltage_level=voltage_level,
                    winter=record.get("winter"),
                    fruehling=record.get("fruehling"),
                    sommer=record.get("sommer"),
                    herbst=record.get("herbst"),
                )
                db.add(new_record)
                logger.debug("hlzf_inserted", voltage_level=voltage_level, year=year)
            
            saved += 1
        
        logger.info("hlzf_saved", count=saved, dno_id=dno_id, year=year)
        return saved
    
    async def _save_netzentgelte(
        self,
        db: AsyncSession,
        dno_id: int,
        year: int,
        records: list[dict],
    ) -> int:
        """Save Netzentgelte records with upsert logic."""
        saved = 0
        
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
                # Update existing record
                if arbeit is not None:
                    existing.arbeit = float(arbeit)
                if leistung is not None:
                    existing.leistung = float(leistung)
                if arbeit_u2500 is not None:
                    existing.arbeit_unter_2500h = float(arbeit_u2500)
                if leistung_u2500 is not None:
                    existing.leistung_unter_2500h = float(leistung_u2500)
                logger.debug("netzentgelte_updated", voltage_level=voltage_level, year=year)
            else:
                # Insert new record
                new_record = NetzentgelteModel(
                    dno_id=dno_id,
                    year=year,
                    voltage_level=voltage_level,
                    arbeit=float(arbeit) if arbeit else None,
                    leistung=float(leistung) if leistung else None,
                    arbeit_unter_2500h=float(arbeit_u2500) if arbeit_u2500 else None,
                    leistung_unter_2500h=float(leistung_u2500) if leistung_u2500 else None,
                )
                db.add(new_record)
                logger.debug("netzentgelte_inserted", voltage_level=voltage_level, year=year)
            
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

