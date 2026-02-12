"""
Sample Capture Service for DNO Crawler.

Captures samples when processing fails for offline analysis:

Directory Structure:
- extraction/
  - debug/: Both regex AND AI failed (for debugging)
  - training/: Regex failed → AI succeeded (for pattern learning)
- crawl/
  - errors/: Crawl failures (blocked, timeouts, etc.)
  - logs/: Detailed crawl logs for debugging

Samples are stored as JSON files with references to source files (not copies).
Only captures when both regex AND AI fail (or AI not configured).
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import structlog

logger = structlog.get_logger()


class SampleCapture:
    """Captures extraction and crawl samples for offline learning and debugging."""

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

    # =========================================================================
    # EXTRACTION SAMPLES (existing functionality, now under extraction/)
    # =========================================================================

    async def capture_extraction(
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
        """Capture an extraction sample to JSON file.

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
        # Create directory structure: extraction/{category}/{dno_slug}/
        sample_dir = self.base_dir / "extraction" / category / dno_slug
        sample_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        filename = f"{year}_{data_type}_{timestamp}.json"
        sample_path = sample_dir / filename

        # Build sample data
        sample = {
            "captured_at": datetime.now(UTC).isoformat() + "Z",
            "category": category,
            "type": "extraction",
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
            "extraction_sample_captured",
            category=category,
            dno=dno_slug,
            year=year,
            data_type=data_type,
            path=str(sample_path),
        )

        return str(sample_path)

    # Legacy method for backwards compatibility
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
        """Legacy method - redirects to capture_extraction."""
        return await self.capture_extraction(
            category=category,
            dno_slug=dno_slug,
            year=year,
            data_type=data_type,
            source_file_path=source_file_path,
            source_format=source_format,
            regex_result=regex_result,
            regex_fail_reason=regex_fail_reason,
            ai_result=ai_result,
            ai_model=ai_model,
            prompt_used=prompt_used,
            ai_fail_reason=ai_fail_reason,
        )

    # =========================================================================
    # CRAWL SAMPLES (new functionality for debugging crawl issues)
    # =========================================================================

    async def capture_crawl_error(
        self,
        dno_slug: str,
        url: str,
        error_type: str,
        error_message: str,
        status_code: int | None = None,
        response_headers: dict | None = None,
        response_body_snippet: str | None = None,
        request_headers: dict | None = None,
        job_id: str | None = None,
        step: str | None = None,
    ) -> str:
        """Capture a crawl error for debugging.

        Args:
            dno_slug: DNO identifier
            url: URL that failed
            error_type: Type of error (cloudflare, timeout, blocked, etc.)
            error_message: Detailed error message
            status_code: HTTP status code (if available)
            response_headers: Response headers (if available)
            response_body_snippet: First ~1KB of response body (if available)
            request_headers: Request headers used
            job_id: Associated job ID
            step: Which crawl step failed (discover, download, etc.)

        Returns:
            Path to the saved sample file
        """
        # Create directory structure: crawl/errors/{dno_slug}/
        sample_dir = self.base_dir / "crawl" / "errors" / dno_slug
        sample_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        filename = f"{error_type}_{timestamp}.json"
        sample_path = sample_dir / filename

        # Build sample data
        sample = {
            "captured_at": datetime.now(UTC).isoformat() + "Z",
            "type": "crawl_error",
            "dno_slug": dno_slug,
            "job_id": job_id,
            "step": step,
            "url": url,
            "error": {
                "type": error_type,
                "message": error_message,
            },
            "request": {
                "headers": request_headers,
            },
            "response": {
                "status_code": status_code,
                "headers": response_headers,
                "body_snippet": response_body_snippet,
            },
        }

        # Write sample to file
        sample_path.write_text(
            json.dumps(sample, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

        self.log.info(
            "crawl_error_captured",
            error_type=error_type,
            dno=dno_slug,
            url=url,
            path=str(sample_path),
        )

        return str(sample_path)

    async def capture_crawl_log(
        self,
        dno_slug: str,
        job_id: str,
        step: str,
        action: str,
        details: dict,
        success: bool = True,
    ) -> str:
        """Capture detailed crawl log for debugging.

        Args:
            dno_slug: DNO identifier
            job_id: Associated job ID
            step: Which crawl step (discover, download, etc.)
            action: What action was taken
            details: Detailed context/data
            success: Whether the action succeeded

        Returns:
            Path to the saved log file
        """
        # Create directory structure: crawl/logs/{dno_slug}/
        log_dir = self.base_dir / "crawl" / "logs" / dno_slug
        log_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        status = "ok" if success else "fail"
        filename = f"{step}_{action}_{status}_{timestamp}.json"
        log_path = log_dir / filename

        # Build log data
        log_entry = {
            "captured_at": datetime.now(UTC).isoformat() + "Z",
            "type": "crawl_log",
            "dno_slug": dno_slug,
            "job_id": job_id,
            "step": step,
            "action": action,
            "success": success,
            "details": details,
        }

        # Write log to file
        log_path.write_text(
            json.dumps(log_entry, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

        self.log.debug(
            "crawl_log_captured",
            dno=dno_slug,
            step=step,
            action=action,
            success=success,
            path=str(log_path),
        )

        return str(log_path)
