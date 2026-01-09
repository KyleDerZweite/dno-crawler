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

        # Check minimum records - at least 2 for small municipal DNOs
        if len(data) < 2:
            errors.append(f"Only {len(data)} voltage levels (expected at least 2)")

        # Helper to check if value is valid (not None, "-", or "N/A")
        def is_valid_value(v):
            if v is None:
                return False
            v_str = str(v).strip().lower()
            return v_str not in ["-", "n/a", "null", "none", ""]

        for i, record in enumerate(data):
            # Check required fields - missing voltage_level is critical
            if not record.get("voltage_level"):
                errors.append(f"Record {i}: missing voltage_level")

            # Validate Arbeitspreis range - skip "-" and null values
            ap = record.get("arbeitspreis") or record.get("arbeit")
            if is_valid_value(ap):
                try:
                    ap_float = float(str(ap).replace(",", "."))
                    if not (0.01 <= ap_float <= 20):
                        warnings.append(f"Arbeitspreis {ap} ct/kWh outside typical range (0.01-20)")
                except (ValueError, TypeError):
                    warnings.append(f"Arbeitspreis '{ap}' is not a valid number")

            # Validate Leistungspreis range - skip "-" and null values
            lp = record.get("leistungspreis") or record.get("leistung")
            if is_valid_value(lp):
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

        # Check minimum records - less than 2 is critical (even small DNOs have at least 2)
        if len(data) < 2:
            errors.append(f"Only {len(data)} voltage levels (expected at least 2)")

        # Helper to check if value is valid time data
        def is_valid_time(v):
            if v is None:
                return False
            v_str = str(v).strip().lower()
            return v_str not in ["-", "entfällt", "null", "none", ""]

        # Check that expected voltage levels are present
        # Note: Small DNOs may only have MS, MS/NS, NS (3 levels) - that's OK
        found_levels = set()
        for record in data:
            vl = str(record.get("voltage_level", "")).lower()
            # Normalize voltage level names
            if "hochspannung" in vl or vl == "hs":
                found_levels.add("hs")
            elif ("mittelspannung" in vl and "nieder" not in vl and "umspann" not in vl) or vl == "ms":
                found_levels.add("ms")
            elif "niederspannung" in vl or vl == "ns":
                found_levels.add("ns")
            # Check for Umspannung levels
            if ("umspann" in vl or "/" in vl) and "hs" in vl and "ms" in vl:
                found_levels.add("hs/ms")
            if ("umspann" in vl or "/" in vl) and "ms" in vl and "ns" in vl:
                found_levels.add("ms/ns")

        # Only warn if neither HS nor MS are present (very suspicious)
        if "ms" not in found_levels and "hs" not in found_levels:
            warnings.append("Neither MS nor HS voltage levels found - verify extraction")

        # Peak load seasons (winter and herbst)
        peak_seasons = ["winter", "herbst"]
        # Off-peak seasons (often legitimately empty)

        total_peak_slots = 0
        filled_peak_slots = 0

        for i, record in enumerate(data):
            # Missing voltage_level is a critical error
            if not record.get("voltage_level"):
                errors.append(f"Record {i}: missing voltage_level")

            # Count peak season data (winter + herbst)
            for season in peak_seasons:
                total_peak_slots += 1
                if is_valid_time(record.get(season)):
                    filled_peak_slots += 1

        # Check at least one peak season has time data overall
        has_any_peak_data = filled_peak_slots > 0
        if not has_any_peak_data:
            errors.append("No time window data found for peak seasons (winter/herbst)")

        # Warn if less than 40% of peak slots have data (might be incomplete extraction)
        if total_peak_slots > 0 and filled_peak_slots > 0:
            fill_rate = filled_peak_slots / total_peak_slots
            if fill_rate < 0.4:
                warnings.append(
                    f"Only {filled_peak_slots}/{total_peak_slots} peak season slots have data - "
                    f"may be incomplete extraction"
                )

        return errors, warnings

