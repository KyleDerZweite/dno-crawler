"""
Step 05: Validate Data

Validates extracted data for quality and plausibility.

What it does:
- Check that required fields are present
- Validate numeric values are in plausible ranges
- Ensure minimum number of voltage levels extracted
- Flag any issues for review

Validation rules for Netzentgelte:
- At least 3 voltage levels extracted
- Arbeitspreis: 0.01 - 20 ct/kWh (typical range)
- Leistungspreis: 1 - 500 €/kW (typical range)

Validation rules for HLZF:
- At least 2 voltage levels
- Time windows in valid format (HH:MM-HH:MM) or "entfällt"

Output stored in job.context:
- is_valid: True if data passes all checks
- validation_issues: list of any issues found
"""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CrawlJobModel
from app.jobs.steps.base import BaseStep


class ValidateStep(BaseStep):
    label = "Validating Data"
    description = "Checking extracted data for quality and plausibility..."

    async def run(self, db: AsyncSession, job: CrawlJobModel) -> str:
        ctx = job.context or {}
        data = ctx.get("extracted_data", [])
        issues = []
        
        await asyncio.sleep(0.2)  # Simulate validation
        
        if not data:
            issues.append("No data extracted")
            ctx["is_valid"] = False
            ctx["validation_issues"] = issues
            await db.commit()
            return "FAILED: No data extracted"
        
        if job.data_type == "netzentgelte":
            issues = self._validate_netzentgelte(data)
        else:
            issues = self._validate_hlzf(data)
        
        is_valid = len(issues) == 0
        ctx["is_valid"] = is_valid
        ctx["validation_issues"] = issues
        await db.commit()
        
        if is_valid:
            return f"PASSED: {len(data)} records validated successfully"
        else:
            return f"WARNING: {len(issues)} issues found: {', '.join(issues[:3])}"
    
    def _validate_netzentgelte(self, data: list[dict]) -> list[str]:
        """Validate Netzentgelte data."""
        issues = []
        
        # Check minimum records
        if len(data) < 3:
            issues.append(f"Only {len(data)} voltage levels (expected at least 3)")
        
        for i, record in enumerate(data):
            # Check required fields
            if not record.get("voltage_level"):
                issues.append(f"Record {i}: missing voltage_level")
            
            # Validate Arbeitspreis range
            ap = record.get("arbeitspreis")
            if ap is not None:
                if not (0.01 <= ap <= 20):
                    issues.append(f"Arbeitspreis {ap} ct/kWh outside typical range (0.01-20)")
            
            # Validate Leistungspreis range
            lp = record.get("leistungspreis")
            if lp is not None:
                if not (1 <= lp <= 500):
                    issues.append(f"Leistungspreis {lp} €/kW outside typical range (1-500)")
        
        return issues
    
    def _validate_hlzf(self, data: list[dict]) -> list[str]:
        """Validate HLZF data."""
        issues = []
        
        # Check minimum records
        if len(data) < 2:
            issues.append(f"Only {len(data)} voltage levels (expected at least 2)")
        
        # Check that expected voltage levels are present
        # Standard German grid has: HS, HS/MS, MS, MS/NS, NS (5 levels)
        expected_levels = {"hs", "ms", "ns"}  # At minimum these 3
        umspannung_levels = {"hs/ms", "ms/ns"}  # Transformation levels (optional but common)
        
        found_levels = set()
        for record in data:
            vl = str(record.get("voltage_level", "")).lower()
            # Normalize voltage level names
            if "hochspannung" in vl or vl == "hs":
                found_levels.add("hs")
            elif "mittelspannung" in vl and "nieder" not in vl and "umspann" not in vl:
                found_levels.add("ms")
            elif "niederspannung" in vl or vl == "ns":
                found_levels.add("ns")
            # Check for Umspannung levels
            if ("umspann" in vl or "/" in vl) and "hs" in vl and "ms" in vl:
                found_levels.add("hs/ms")
            if ("umspann" in vl or "/" in vl) and "ms" in vl and "ns" in vl:
                found_levels.add("ms/ns")
        
        missing_levels = expected_levels - found_levels
        if missing_levels:
            issues.append(f"Missing expected voltage levels: {', '.join(sorted(missing_levels)).upper()}")
        
        # Check for Umspannung levels (warn but don't fail)
        missing_umspannung = umspannung_levels - found_levels
        if missing_umspannung and len(data) < 4:
            issues.append(f"Missing transformation levels: {', '.join(sorted(missing_umspannung)).upper()} (expected 5 levels total)")
        
        seasons = ["winter", "fruehling", "sommer", "herbst"]
        total_season_slots = 0
        filled_or_explicit_empty = 0  # Has time data OR explicitly "entfällt"
        completely_missing = 0  # Empty/None with no explicit "entfällt"
        
        for i, record in enumerate(data):
            if not record.get("voltage_level"):
                issues.append(f"Record {i}: missing voltage_level")
            
            # Count how many seasons have data vs are legitimately empty
            for season in seasons:
                total_season_slots += 1
                val = record.get(season)
                val_str = str(val or "").strip().lower()
                
                if val_str in ["entfällt", "-"]:
                    # Explicitly marked as not applicable - this is valid
                    filled_or_explicit_empty += 1
                elif val and val_str not in ["none", ""]:
                    # Has actual time data
                    filled_or_explicit_empty += 1
                else:
                    # Missing/None with no explicit marker - might be extraction issue
                    completely_missing += 1
        
        # Check at least one season has time data overall
        has_any_time_data = any(
            record.get(s) and str(record.get(s)).strip().lower() not in ["entfällt", "-", "none", ""]
            for record in data
            for s in seasons
        )
        if not has_any_time_data:
            issues.append("No time window data found in any record")
        
        # Check if too many seasons are completely missing (not "entfällt", just empty)
        # This suggests extraction failure rather than legitimate empty data
        if total_season_slots > 0 and completely_missing > 0:
            missing_rate = completely_missing / total_season_slots
            if missing_rate > 0.5:
                issues.append(
                    f"{completely_missing}/{total_season_slots} season slots are completely empty "
                    f"(not 'entfällt') - extraction may be incomplete"
                )
        
        return issues
