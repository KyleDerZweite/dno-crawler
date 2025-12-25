"""
Content Verifier Service for DNO Crawler.

Verifies that discovered content actually matches the expected data type
before committing to full download/processing.

Features:
- Partial content fetching (first 15KB) to minimize bandwidth
- Multi-format support: PDF, HTML, XLSX, images
- Data-type-specific keyword matching
- Confidence scoring for verification
"""

import io
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()


# =============================================================================
# Data Types and Constants
# =============================================================================


class DataType(str, Enum):
    NETZENTGELTE = "netzentgelte"
    HLZF = "hlzf"


@dataclass
class VerificationResult:
    """Result of content verification."""
    is_verified: bool
    confidence: float  # 0.0 to 1.0
    detected_data_type: str | None
    keywords_found: list[str]
    keywords_missing: list[str]
    error: str | None = None
    content_sample: str | None = None  # First 500 chars for debugging


# Keywords that MUST appear for each data type (positive markers)
REQUIRED_KEYWORDS = {
    "netzentgelte": [
        # At least one of these must appear
        ["netzentgelt", "netznutzungsentgelt", "entgeltblatt", "preisblatt"],
    ],
    "hlzf": [
        # At least one of these must appear
        ["hochlastzeitfenster", "hlzf", "hochlast"],
    ],
}

# Keywords that strongly indicate a specific data type (boosters)
POSITIVE_KEYWORDS = {
    "netzentgelte": [
        "leistungspreis", "arbeitspreis", "ct/kwh", "€/kw", "eur/kw",
        "netznutzung", "netzentgelt", "entgelt", "preisblatt",
        "netzzugang", "preise", "tarifblatt", "entgeltblatt",
        "jahresleistungspreis", "leistungsentgelt", "arbeitsentgelt",
    ],
    "hlzf": [
        "hochlastzeitfenster", "hochlast", "zeitfenster", "hlzf",
        "§19", "stromnev", "spitzenlast", "peak", "hochlastzeit",
        "winter", "sommer", "herbst", "frühling", "fruehling",
        "entfällt", "entfaellt", "uhr",
    ],
}

# Keywords that indicate WRONG data type (negative markers)
NEGATIVE_KEYWORDS = {
    "netzentgelte": [
        # If looking for netzentgelte, these suggest wrong document
        "hochlastzeitfenster", "hlzf", "zeitfenster",
    ],
    "hlzf": [
        # If looking for HLZF, these suggest wrong document (but not as strong)
        # Keep light penalties since HLZF docs might mention prices
    ],
}

# Patterns that indicate document structure
STRUCTURE_PATTERNS = {
    "netzentgelte": [
        r"\d+[,\.]\d+\s*ct",  # Price pattern like "5,67 ct"
        r"\d+[,\.]\d+\s*€/k[wW]",  # €/kW pattern
        r"(niederspannung|mittelspannung|hochspannung)",  # Voltage levels
    ],
    "hlzf": [
        r"\d{1,2}:\d{2}\s*[-–]\s*\d{1,2}:\d{2}",  # Time window pattern "08:00-20:00"
        r"(winter|sommer|herbst|fr[üu]hling)",  # Seasons
        r"entf[äa]llt",  # "entfällt" pattern
    ],
}


# =============================================================================
# Content Verifier
# =============================================================================


class ContentVerifier:
    """Verifies content matches expected data type."""
    
    # Maximum bytes to fetch for sniffing
    SNIFF_SIZE = 15 * 1024  # 15KB
    
    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client
        self.log = logger.bind(component="ContentVerifier")
    
    async def verify_url(
        self,
        url: str,
        expected_data_type: str,
        expected_year: int | None = None,
    ) -> VerificationResult:
        """Verify URL content matches expected data type.
        
        Fetches partial content and analyzes it to determine if the
        resource actually contains the expected data type.
        
        Args:
            url: URL to verify
            expected_data_type: "netzentgelte" or "hlzf"
            expected_year: Expected year (optional, for additional validation)
            
        Returns:
            VerificationResult with confidence score and details
        """
        try:
            # Detect content type from URL
            content_type = self._detect_content_type(url)
            
            # Fetch partial content
            content = await self._fetch_partial(url)
            if not content:
                return VerificationResult(
                    is_verified=False,
                    confidence=0.0,
                    detected_data_type=None,
                    keywords_found=[],
                    keywords_missing=[],
                    error="Failed to fetch content",
                )
            
            # Extract text based on content type
            text = await self._extract_text(content, content_type, url)
            if not text:
                return VerificationResult(
                    is_verified=False,
                    confidence=0.3,  # Partial confidence - might still be valid
                    detected_data_type=None,
                    keywords_found=[],
                    keywords_missing=[],
                    error="Could not extract text from content",
                    content_sample=content[:500].decode("utf-8", errors="replace") if content else None,
                )
            
            # Verify content against expected data type
            return self._verify_text(text, expected_data_type, expected_year)
            
        except Exception as e:
            self.log.warning("verify_url_failed", url=url[:80], error=str(e))
            return VerificationResult(
                is_verified=False,
                confidence=0.0,
                detected_data_type=None,
                keywords_found=[],
                keywords_missing=[],
                error=str(e),
            )
    
    def verify_text(
        self,
        text: str,
        expected_data_type: str,
        expected_year: int | None = None,
    ) -> VerificationResult:
        """Verify extracted text matches expected data type.
        
        This is the synchronous version for already-downloaded content.
        """
        return self._verify_text(text, expected_data_type, expected_year)
    
    def _verify_text(
        self,
        text: str,
        expected_data_type: str,
        expected_year: int | None = None,
    ) -> VerificationResult:
        """Internal text verification logic."""
        text_lower = text.lower()
        
        # Track keywords
        found_keywords: list[str] = []
        missing_keywords: list[str] = []
        
        # Calculate scores
        positive_score = 0.0
        negative_score = 0.0
        structure_score = 0.0
        required_met = False
        
        # Check required keywords (at least one group must have a match)
        required = REQUIRED_KEYWORDS.get(expected_data_type, [])
        for keyword_group in required:
            if any(kw in text_lower for kw in keyword_group):
                required_met = True
                for kw in keyword_group:
                    if kw in text_lower:
                        found_keywords.append(kw)
                break
            else:
                missing_keywords.extend(keyword_group[:2])  # Only show first 2
        
        # Count positive keywords
        positive = POSITIVE_KEYWORDS.get(expected_data_type, [])
        for kw in positive:
            if kw in text_lower:
                found_keywords.append(kw)
                positive_score += 1
        
        # Count negative keywords (wrong data type markers)
        negative = NEGATIVE_KEYWORDS.get(expected_data_type, [])
        for kw in negative:
            if kw in text_lower:
                negative_score += 2  # Heavier penalty
        
        # Check structural patterns
        patterns = STRUCTURE_PATTERNS.get(expected_data_type, [])
        for pattern in patterns:
            if re.search(pattern, text_lower):
                structure_score += 2
        
        # Year validation (if expected)
        year_found = False
        if expected_year:
            if str(expected_year) in text:
                year_found = True
                positive_score += 2
        
        # Calculate confidence
        total_positive = len(positive)
        if total_positive > 0:
            keyword_confidence = min(1.0, (positive_score / (total_positive * 0.3)))
        else:
            keyword_confidence = 0.5
        
        structure_confidence = min(1.0, structure_score / (len(patterns) * 2)) if patterns else 0.5
        
        # Penalty for negative keywords
        penalty = min(0.5, negative_score * 0.1)
        
        # Combined confidence
        confidence = (keyword_confidence * 0.5 + structure_confidence * 0.5) - penalty
        
        # Require required keywords for high confidence
        if not required_met:
            confidence = min(confidence, 0.3)
        
        confidence = max(0.0, min(1.0, confidence))
        
        # Determine detected data type (which type does this look like?)
        detected = self._detect_data_type(text_lower)
        
        # Final verification decision
        is_verified = (
            required_met and 
            confidence >= 0.4 and 
            (detected == expected_data_type or detected is None)
        )
        
        self.log.debug(
            "verify_text_result",
            expected=expected_data_type,
            detected=detected,
            confidence=round(confidence, 2),
            required_met=required_met,
            positive_count=len([k for k in found_keywords if k in positive]),
            is_verified=is_verified,
        )
        
        return VerificationResult(
            is_verified=is_verified,
            confidence=confidence,
            detected_data_type=detected,
            keywords_found=list(set(found_keywords))[:10],  # Limit for display
            keywords_missing=list(set(missing_keywords))[:5],
            content_sample=text[:500] if text else None,
        )
    
    def _detect_data_type(self, text_lower: str) -> str | None:
        """Try to detect which data type the text represents."""
        netz_score = 0
        hlzf_score = 0
        
        for kw in POSITIVE_KEYWORDS["netzentgelte"]:
            if kw in text_lower:
                netz_score += 1
        
        for kw in POSITIVE_KEYWORDS["hlzf"]:
            if kw in text_lower:
                hlzf_score += 1
        
        # Strong HLZF markers
        if "hochlastzeitfenster" in text_lower or "hlzf" in text_lower:
            hlzf_score += 5
        
        # Strong Netzentgelte markers
        if "netzentgelt" in text_lower and "leistungspreis" in text_lower:
            netz_score += 5
        
        if netz_score > hlzf_score and netz_score > 3:
            return "netzentgelte"
        elif hlzf_score > netz_score and hlzf_score > 3:
            return "hlzf"
        
        return None
    
    async def _fetch_partial(self, url: str) -> bytes | None:
        """Fetch partial content using Range header."""
        if not self.client:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                return await self._do_fetch_partial(client, url)
        return await self._do_fetch_partial(self.client, url)
    
    async def _do_fetch_partial(self, client: httpx.AsyncClient, url: str) -> bytes | None:
        """Perform the actual partial fetch."""
        try:
            # Try Range request first
            response = await client.get(
                url,
                headers={"Range": f"bytes=0-{self.SNIFF_SIZE - 1}"},
                follow_redirects=True,
            )
            
            if response.status_code in (200, 206):
                return response.content[:self.SNIFF_SIZE]
            
            return None
        except Exception as e:
            self.log.debug("fetch_partial_failed", url=url[:80], error=str(e))
            return None
    
    def _detect_content_type(self, url: str) -> str:
        """Detect content type from URL."""
        url_lower = url.lower()
        if url_lower.endswith(".pdf"):
            return "pdf"
        elif url_lower.endswith((".xlsx", ".xls")):
            return "excel"
        elif url_lower.endswith((".docx", ".doc")):
            return "word"
        elif url_lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
            return "image"
        else:
            return "html"
    
    async def _extract_text(self, content: bytes, content_type: str, url: str) -> str | None:
        """Extract text from content based on type."""
        import asyncio
        
        if content_type == "pdf":
            return await asyncio.to_thread(self._extract_pdf_text, content)
        elif content_type == "excel":
            return await asyncio.to_thread(self._extract_excel_text, content)
        elif content_type == "html":
            return self._extract_html_text(content)
        elif content_type == "image":
            # Images need OCR - return None for now
            # Could integrate with AI vision in the future
            self.log.debug("image_content_skipped", url=url[:80])
            return None
        else:
            # Try as text
            try:
                return content.decode("utf-8", errors="replace")
            except Exception:
                return None
    
    def _extract_pdf_text(self, content: bytes) -> str | None:
        """Extract text from PDF content."""
        try:
            import pdfplumber
            
            pdf_file = io.BytesIO(content)
            text_parts = []
            
            with pdfplumber.open(pdf_file) as pdf:
                # Only read first few pages for sniffing
                for page in pdf.pages[:3]:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
            
            return "\n".join(text_parts) if text_parts else None
        except Exception as e:
            self.log.debug("pdf_extract_failed", error=str(e))
            return None
    
    def _extract_excel_text(self, content: bytes) -> str | None:
        """Extract text from Excel content."""
        try:
            import openpyxl
            
            excel_file = io.BytesIO(content)
            wb = openpyxl.load_workbook(excel_file, read_only=True, data_only=True)
            
            text_parts = []
            for sheet in wb.worksheets[:2]:  # First 2 sheets
                for row in list(sheet.iter_rows(max_row=50)):  # First 50 rows
                    row_text = " ".join(str(cell.value or "") for cell in row)
                    if row_text.strip():
                        text_parts.append(row_text)
            
            return "\n".join(text_parts) if text_parts else None
        except Exception as e:
            self.log.debug("excel_extract_failed", error=str(e))
            return None
    
    def _extract_html_text(self, content: bytes) -> str | None:
        """Extract text from HTML content."""
        try:
            from bs4 import BeautifulSoup
            
            soup = BeautifulSoup(content, "lxml")
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            # Get text
            text = soup.get_text(separator=" ", strip=True)
            
            # Clean up whitespace
            text = re.sub(r'\s+', ' ', text)
            
            return text if text else None
        except Exception as e:
            self.log.debug("html_extract_failed", error=str(e))
            return None


# =============================================================================
# Scoring Enhancement for Web Crawler
# =============================================================================


def score_for_data_type(url: str, data_type: str) -> float:
    """Calculate bonus/penalty score based on data type specificity.
    
    This function provides additional scoring to the web crawler
    based on data-type-specific keywords in the URL.
    
    Args:
        url: URL to score
        data_type: Expected data type
        
    Returns:
        Score adjustment (positive = boost, negative = penalty)
    """
    url_lower = url.lower()
    score = 0.0
    
    if data_type == "netzentgelte":
        # Boost for netzentgelte-specific terms
        if any(term in url_lower for term in ["netzentgelt", "preisblatt", "entgelt", "tarif"]):
            score += 15
        if "leistungspreis" in url_lower or "arbeitspreis" in url_lower:
            score += 10
            
        # Penalty for HLZF-related terms
        if any(term in url_lower for term in ["hochlast", "hlzf", "zeitfenster", "regelung"]):
            score -= 20
            
    elif data_type == "hlzf":
        # Boost for HLZF-specific terms
        if any(term in url_lower for term in ["hochlast", "hlzf", "zeitfenster"]):
            score += 20
        if "regelung" in url_lower:
            score += 5
            
        # Light penalty for pure pricing docs
        if "preisblatt" in url_lower and "hochlast" not in url_lower:
            score -= 10
    
    return score
