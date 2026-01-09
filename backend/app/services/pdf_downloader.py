"""
PDF Downloader service for downloading and validating PDF documents.

Extracted from SearchAgent.
"""

import re
from pathlib import Path

import httpx
import pdfplumber
import structlog

from app.core.config import settings

logger = structlog.get_logger()


class PDFDownloader:
    """
    Download and validate PDF documents.
    
    Handles downloading PDFs from URLs and validating their content
    matches expected DNO/year data.
    """

    def __init__(self):
        """Initialize the PDF downloader."""
        self.log = logger.bind(component="PDFDownloader")

    def download(
        self,
        url: str,
        dno_name: str,
        year: int,
        pdf_type: str = "netzentgelte"
    ) -> Path | None:
        """
        Download PDF to local storage.
        
        Args:
            url: URL to download from
            dno_name: Name of the DNO (used for directory/filename)
            year: Year of the data
            pdf_type: Type of PDF ("netzentgelte" or "regelungen")
            
        Returns:
            Path to downloaded PDF, or None if download failed
        """
        log = self.log.bind(url=url)

        # Create safe filename
        safe_name = re.sub(r'[^a-zA-Z0-9]', '-', dno_name.lower())
        downloads_dir = Path(settings.downloads_path) / safe_name
        downloads_dir.mkdir(parents=True, exist_ok=True)

        pdf_path = downloads_dir / f"{pdf_type}-{year}.pdf"

        try:
            with httpx.Client(follow_redirects=True, timeout=60.0) as client:
                response = client.get(url)
                response.raise_for_status()

                # Verify it's actually a PDF
                if not response.content.startswith(b'%PDF'):
                    log.warning("Downloaded file is not a valid PDF")
                    return None

                pdf_path.write_bytes(response.content)
                log.info("PDF downloaded", path=str(pdf_path), size=len(response.content))
                return pdf_path

        except Exception as e:
            log.error("PDF download failed", error=str(e))
            return None

    def validate_content(
        self,
        pdf_path: Path,
        dno_name: str,
        year: int,
    ) -> bool:
        """
        "The Glance" - Read page 1 to verify this is the correct document.
        
        Performs keyword checks to validate the document.
        
        Args:
            pdf_path: Path to the PDF file
            dno_name: Expected DNO name
            year: Expected year
            
        Returns:
            True if document appears valid, False otherwise
        """
        try:
            with pdfplumber.open(pdf_path) as pdf:
                first_page_text = pdf.pages[0].extract_text() or ""

            # Quick keyword check
            if str(year) not in first_page_text:
                self.log.debug("Year not found in PDF")
                return False

            # Check for Netzentgelte keywords
            keywords = ["netzentgelt", "leistungspreis", "arbeitspreis", "preisblatt"]
            if not any(kw in first_page_text.lower() for kw in keywords):
                self.log.debug("No Netzentgelte keywords found")
                return False

            return True

        except Exception as e:
            self.log.error("PDF validation error", error=str(e))
            return False

