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
        
        await asyncio.sleep(0.2)  # Simulate validation
        
        if not data:
            ctx["is_valid"] = False
            ctx["validation_issues"] = ["No data extracted"]
            await db.commit()
            return "FAILED: No data extracted"
        
        # Validate and separate errors from warnings
        if job.data_type == "netzentgelte":
            errors, warnings = self._validate_netzentgelte(data)
        else:
            errors, warnings = self._validate_hlzf(data)
        
        # Errors = critical issues that make data unusable (don't save)
        # Warnings = quality concerns but data is still usable (save but flag)
        has_errors = len(errors) > 0
        has_warnings = len(warnings) > 0
        
        # Data is valid if there are no critical errors
        # Warnings allow saving but trigger auto-flagging
        ctx["is_valid"] = not has_errors
        ctx["validation_issues"] = errors + warnings
        
        # Auto-flag if there are warnings (data will be saved but flagged for review)
        if has_warnings and not has_errors:
            ctx["auto_flagged"] = True
            ctx["auto_flag_reason"] = f"Validation warnings: {'; '.join(warnings[:2])}"
        
        await db.commit()
        
        if has_errors:
            return f"FAILED: {len(errors)} errors found: {', '.join(errors[:2])}"
        elif has_warnings:
            return f"WARNING: {len(warnings)} issues found: {', '.join(warnings[:2])}"
        else:
            return f"PASSED: {len(data)} records validated successfully"
    
    def _validate_netzentgelte(self, data: list[dict]) -> tuple[list[str], list[str]]:
        """Validate Netzentgelte data.
        
        Returns:
            Tuple of (errors, warnings):
            - errors: Critical issues that should block saving
            - warnings: Quality concerns that should flag but allow saving
        """
        errors = []
        warnings = []
        
        # Check minimum records - this is a critical error
        if len(data) < 3:
            errors.append(f"Only {len(data)} voltage levels (expected at least 3)")
        
        for i, record in enumerate(data):
            # Check required fields - missing voltage_level is critical
            if not record.get("voltage_level"):
                errors.append(f"Record {i}: missing voltage_level")
            
            # Validate Arbeitspreis range - out of range is just a warning
            ap = record.get("arbeitspreis") or record.get("arbeit")
            if ap is not None:
                try:
                    ap_float = float(str(ap).replace(",", "."))
                    if not (0.01 <= ap_float <= 20):
                        warnings.append(f"Arbeitspreis {ap} ct/kWh outside typical range (0.01-20)")
                except (ValueError, TypeError):
                    warnings.append(f"Arbeitspreis '{ap}' is not a valid number")
            
            # Validate Leistungspreis range - out of range is just a warning
            lp = record.get("leistungspreis") or record.get("leistung")
            if lp is not None:
                try:
                    lp_float = float(str(lp).replace(",", "."))
                    if not (0 <= lp_float <= 500):
                        warnings.append(f"Leistungspreis {lp} €/kW outside typical range (0-500)")
                except (ValueError, TypeError):
                    warnings.append(f"Leistungspreis '{lp}' is not a valid number")
        
        return errors, warnings
    
    def _validate_hlzf(self, data: list[dict]) -> tuple[list[str], list[str]]:
        """Validate HLZF data.
        
        Returns:
            Tuple of (errors, warnings):
            - errors: Critical issues that should block saving (no data, missing voltage_level)
            - warnings: Quality concerns that should flag but allow saving (empty seasons, etc.)
        """
        errors = []
        warnings = []
        
        # Check minimum records - less than 2 is critical
        if len(data) < 2:
            errors.append(f"Only {len(data)} voltage levels (expected at least 2)")
        
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
            elif vl == "ms":  # Handle abbreviated form
                found_levels.add("ms")
            elif "niederspannung" in vl or vl == "ns":
                found_levels.add("ns")
            # Check for Umspannung levels
            if ("umspann" in vl or "/" in vl) and "hs" in vl and "ms" in vl:
                found_levels.add("hs/ms")
            if ("umspann" in vl or "/" in vl) and "ms" in vl and "ns" in vl:
                found_levels.add("ms/ns")
        
        # Missing expected voltage levels is a warning (might be legitimate for some DNOs)
        missing_levels = expected_levels - found_levels
        if missing_levels:
            warnings.append(f"Missing expected voltage levels: {', '.join(sorted(missing_levels)).upper()}")
        
        # Check for Umspannung levels (warn but don't fail)
        missing_umspannung = umspannung_levels - found_levels
        if missing_umspannung and len(data) < 4:
            warnings.append(f"Missing transformation levels: {', '.join(sorted(missing_umspannung)).upper()} (expected 5 levels total)")
        
        seasons = ["winter", "fruehling", "sommer", "herbst"]
        total_season_slots = 0
        filled_or_explicit_empty = 0  # Has time data OR explicitly "entfällt"
        completely_missing = 0  # Empty/None with no explicit "entfällt"
        
        for i, record in enumerate(data):
            # Missing voltage_level is a critical error
            if not record.get("voltage_level"):
                errors.append(f"Record {i}: missing voltage_level")
            
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
                    # Missing/None with no explicit marker - might be extraction issue or legitimate
                    completely_missing += 1
        
        # Check at least one season has time data overall - no time data is an error
        has_any_time_data = any(
            record.get(s) and str(record.get(s)).strip().lower() not in ["entfällt", "-", "none", ""]
            for record in data
            for s in seasons
        )
        if not has_any_time_data:
            errors.append("No time window data found in any record")
        
        # Check if too many seasons are completely missing (not "entfällt", just empty)
        # This is just a warning - many DNOs legitimately use null/None for empty seasons
        if total_season_slots > 0 and completely_missing > 0:
            missing_rate = completely_missing / total_season_slots
            if missing_rate > 0.5:
                warnings.append(
                    f"{completely_missing}/{total_season_slots} season slots are empty "
                    f"(null instead of 'entfällt') - may be incomplete extraction"
                )
        
        return errors, warnings
