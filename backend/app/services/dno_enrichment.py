"""
DNO enrichment service — robots.txt + impressum in a single call.

Consolidates the repeated pattern of fetching robots.txt and enriching
addresses via Impressum extraction that was duplicated across search
and CRUD endpoints.
"""

from dataclasses import dataclass

import httpx
import structlog

from app.services.impressum_extractor import impressum_extractor
from app.services.robots_parser import RobotsResult, fetch_robots_txt

logger = structlog.get_logger()


@dataclass
class EnrichmentResult:
    """Combined result of robots.txt fetch and impressum enrichment."""

    robots: RobotsResult | None = None
    enriched_address: str | None = None


async def enrich_dno_from_web(
    homepage_url: str,
    address: str | None = None,
) -> EnrichmentResult:
    """
    Fetch robots.txt and optionally enrich address via Impressum.

    Args:
        homepage_url: DNO homepage URL (e.g., "https://www.rheinnetz.de/")
        address: Street address from VNB Digital to enrich with postal code + city.
                 If None, impressum enrichment is skipped.

    Returns:
        EnrichmentResult with robots info and optionally enriched address.
    """
    log = logger.bind(homepage_url=homepage_url)
    result = EnrichmentResult()

    # Enrich address via Impressum (no HTTP client needed — extractor manages its own)
    if address:
        try:
            full_addr = await impressum_extractor.extract_full_address(homepage_url, address)
            if full_addr:
                result.enriched_address = full_addr.formatted
        except Exception as e:
            log.debug("Impressum enrichment failed", error=str(e))

    # Fetch robots.txt
    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": "DNO-Crawler/1.0"},
            follow_redirects=True,
            timeout=10.0,
        ) as http_client:
            result.robots = await fetch_robots_txt(http_client, homepage_url)
    except Exception as e:
        log.debug("Robots.txt fetch failed", error=str(e))

    return result
