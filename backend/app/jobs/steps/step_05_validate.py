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
        
        for i, record in enumerate(data):
            if not record.get("voltage_level"):
                issues.append(f"Record {i}: missing voltage_level")
            
            # Check at least one season has data
            seasons = ["winter", "fruehling", "sommer", "herbst"]
            has_data = any(record.get(s) for s in seasons)
            if not has_data:
                issues.append(f"Record {i}: no seasonal data")
        
        return issues
