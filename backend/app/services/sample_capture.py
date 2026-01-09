"""
Sample Capture Service for DNO Crawler.

Captures extraction samples when regex fails for offline analysis:
- training/: Regex failed → AI succeeded (for pattern learning)
- debug/: Regex failed → AI also failed (for debugging)

Samples are stored as JSON files with references to source files (not copies).
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Literal

import structlog

logger = structlog.get_logger()


class SampleCapture:
    """Captures extraction samples for offline learning and debugging."""

    def __init__(self, base_dir: Path | None = None):
        """Initialize with base directory for samples.
        
        Args:
            base_dir: Base directory for samples. Defaults to data/samples/
        """
        if base_dir is None:
            # Default to project's data/samples/ directory
            base_dir = Path(__file__).parent.parent.parent.parent.parent / "data" / "samples"
        self.base_dir = base_dir
        self.log = logger.bind(component="SampleCapture")

    async def capture(
        self,
        category: Literal["training", "debug"],
        dno_slug: str,
        year: int,
        data_type: str,
        source_file_path: str,
        source_format: str,
        regex_result: list,
        regex_fail_reason: str,
        ai_result: list | None = None,
        ai_model: str | None = None,
        prompt_used: str | None = None,
        ai_fail_reason: str | None = None,
    ) -> str:
        """Capture a sample to JSON file.
        
        Args:
            category: "training" (AI succeeded) or "debug" (AI also failed)
            dno_slug: DNO identifier
            year: Data year
            data_type: "netzentgelte" or "hlzf"
            source_file_path: Path to the downloaded PDF/HTML file
            source_format: "pdf" or "html"
            regex_result: What regex extraction returned
            regex_fail_reason: Why regex sanity check failed
            ai_result: What AI extraction returned (if any)
            ai_model: AI model used
            prompt_used: Prompt sent to AI
            ai_fail_reason: Why AI sanity check failed (debug only)
            
        Returns:
            Path to the saved sample file
        """
        # Create directory structure
        sample_dir = self.base_dir / category / dno_slug
        sample_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{year}_{data_type}_{timestamp}.json"
        sample_path = sample_dir / filename

        # Build sample data
        sample = {
            "captured_at": datetime.utcnow().isoformat() + "Z",
            "category": category,
            "dno_slug": dno_slug,
            "year": year,
            "data_type": data_type,
            "source": {
                "file_path": source_file_path,
                "format": source_format,
            },
            "regex": {
                "result": regex_result,
                "fail_reason": regex_fail_reason,
            },
            "ai": {
                "result": ai_result,
                "model": ai_model,
                "prompt": prompt_used,
                "fail_reason": ai_fail_reason,
            },
        }

        # Write sample to file
        sample_path.write_text(
            json.dumps(sample, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

        self.log.info(
            "sample_captured",
            category=category,
            dno=dno_slug,
            year=year,
            data_type=data_type,
            path=str(sample_path),
        )

        return str(sample_path)
