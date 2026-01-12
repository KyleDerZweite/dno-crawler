"""
Impressum Address Extractor Service.

Extracts full address (postal code + city) from DNO Impressum pages
to enrich the partial address data from VNB Digital API.

Strategy:
1. Fetch DNO's /impressum page
2. Find the street address (from VNB) in the HTML
3. Extract nearby postal code + city
4. Return enriched address or None on failure

Gracefully handles:
- JS-rendered pages (returns None)
- Missing Impressum pages (returns None)
- Malformed HTML (returns None)

TODO (Ideas for future enhancement - not required):
- Extract additional fields from Impressum:
  - Geschäftsführung (management names)
  - Handelsregister (company registration number, e.g., "HRB 12345")
  - USt-IdNr (VAT ID, e.g., "DE123456789")
  - Responsible person for content (Verantwortlich i.S.d. § 55 RStV)
- These could be stored in a separate DNO metadata table for legal/compliance purposes
"""

import re
from dataclasses import dataclass

import httpx
import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger()


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class FullAddress:
    """Full address extracted from Impressum."""
    street: str
    house_number: str
    postal_code: str
    city: str

    @property
    def formatted(self) -> str:
        """Format as German address string."""
        return f"{self.street} {self.house_number}, {self.postal_code} {self.city}"


# =============================================================================
# Patterns
# =============================================================================

# 5-digit German postal code followed by city name
POSTAL_CITY_PATTERN = re.compile(
    r"(\d{5})\s+([A-ZÄÖÜa-zäöü][A-ZÄÖÜa-zäöü\s\-\.]+)"
)

# Street with house number (German format)
# Note: Street suffix is embedded in word (Florianstraße, not "Florian straße")
STREET_PATTERN = re.compile(
    r"([A-ZÄÖÜa-zäöü][A-ZÄÖÜa-zäöü\-]*(?:straße|strasse|str\.|gürtel|weg|platz|ring|allee|damm|ufer|hof|park))\s*(\d+(?:\s*[-–]\s*\d+)?)",
    re.IGNORECASE
)

# Common Impressum URL paths
IMPRESSUM_PATHS = [
    "/impressum",
    "/de/impressum.html",
    "/de/impressum",
    "/impressum.html",
]


# =============================================================================
# Extractor Class
# =============================================================================


class ImpressumExtractor:
    """Service for extracting full addresses from Impressum pages."""

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self.log = logger.bind(service="ImpressumExtractor")

    async def extract_full_address(
        self,
        homepage_url: str,
        vnb_street: str,
    ) -> FullAddress | None:
        """
        Extract full address from DNO's Impressum page.

        Args:
            homepage_url: DNO homepage URL (e.g., "https://www.rheinnetz.de/")
            vnb_street: Street address from VNB Digital (e.g., "Parkgürtel 24")

        Returns:
            FullAddress with postal code + city, or None on failure
        """
        log = self.log.bind(homepage=homepage_url, vnb_street=vnb_street)

        # Normalize homepage URL
        base_url = homepage_url.rstrip("/")

        # Try common Impressum paths
        html = None
        for path in IMPRESSUM_PATHS:
            impressum_url = f"{base_url}{path}"
            html = await self._fetch_page(impressum_url)
            if html:
                log.debug("Found Impressum page", url=impressum_url)
                break

        if not html:
            log.debug("No Impressum page found")
            return None

        # Extract address
        result = self._extract_from_html(html, vnb_street)

        if result:
            log.info(
                "Extracted full address",
                postal_code=result.postal_code,
                city=result.city,
            )
        else:
            log.debug("Could not extract address from Impressum")

        return result

    async def _fetch_page(self, url: str) -> str | None:
        """Fetch page HTML, return None on error."""
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=self.timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; DNO-Crawler/1.0)",
                "Accept": "text/html",
            },
        ) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
                return response.text
            except httpx.HTTPError:
                return None

    def _normalize_street(self, street: str) -> str:
        """Normalize street name for comparison."""
        s = street.lower().strip()
        s = re.sub(r"straße", "str", s)
        s = re.sub(r"strasse", "str", s)
        s = re.sub(r"str\.", "str", s)
        s = re.sub(r"\s+", "", s)
        s = re.sub(r"[\-–]", "", s)
        return s

    def _extract_from_html(self, html: str, vnb_street: str) -> FullAddress | None:
        """Extract address from HTML content."""
        soup = BeautifulSoup(html, "html.parser")

        # Remove script and style elements
        for element in soup(["script", "style", "nav", "header"]):
            element.decompose()

        # Get text content
        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        # Normalize VNB street for matching
        vnb_normalized = self._normalize_street(vnb_street)

        # Find street line
        street_line_idx = None
        for idx, line in enumerate(lines):
            if self._normalize_street(line).startswith(vnb_normalized[:10]):
                street_line_idx = idx
                break

        if street_line_idx is None:
            # Try partial match
            street_match = STREET_PATTERN.match(vnb_street)
            if street_match:
                street_name = street_match.group(1).lower()
                for idx, line in enumerate(lines):
                    if street_name in line.lower():
                        street_line_idx = idx
                        break

        if street_line_idx is None:
            return None

        # Look for postal code + city nearby
        search_range = lines[max(0, street_line_idx-2):street_line_idx+4]

        postal_code = None
        city = None

        for line in search_range:
            match = POSTAL_CITY_PATTERN.search(line)
            if match:
                postal_code = match.group(1)
                city = match.group(2).strip()
                break

        if not postal_code or not city:
            return None

        # Extract street and house number from VNB address
        street_match = STREET_PATTERN.match(vnb_street)
        if street_match:
            street = street_match.group(1)
            house_number = street_match.group(2)
        else:
            parts = vnb_street.rsplit(" ", 1)
            street = parts[0] if len(parts) > 1 else vnb_street
            house_number = parts[1] if len(parts) > 1 else ""

        return FullAddress(
            street=street,
            house_number=house_number,
            postal_code=postal_code,
            city=city,
        )


# Singleton instance
impressum_extractor = ImpressumExtractor()
