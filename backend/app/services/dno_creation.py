"""Service helpers for DNO creation route orchestration."""

from dataclasses import dataclass
from typing import Any

from app.services.dno_enrichment import enrich_dno_from_web
from app.services.vnb import VNBDigitalClient


@dataclass
class DNOCreationResolvedData:
    """Resolved and enriched fields used for DNO creation."""

    official_name: str | None
    website: str | None
    phone: str | None
    email: str | None
    contact_address: str | None
    crawlable: bool
    crawl_blocked_reason: str | None
    robots_txt: str | None
    sitemap_urls: list[str] | None
    disallow_paths: list[str] | None
    tech_info: dict[str, Any] | None


async def resolve_dno_creation_data(
    *,
    vnb_id: str | None,
    official_name: str | None,
    website: str | None,
    phone: str | None,
    email: str | None,
    contact_address: str | None,
) -> DNOCreationResolvedData:
    """Resolve VNB and web-enrichment data for DNO creation."""
    resolved_official_name = official_name
    resolved_website = website
    resolved_phone = phone
    resolved_email = email
    resolved_contact_address = contact_address

    crawlable = True
    crawl_blocked_reason = None
    robots_txt = None
    sitemap_urls = None
    disallow_paths = None
    tech_info: dict[str, Any] | None = None

    vnb_details = None
    if vnb_id and not all([resolved_website, resolved_phone, resolved_email]):
        vnb_client = VNBDigitalClient(request_delay=0.5)
        try:
            vnb_details = await vnb_client.get_vnb_details(vnb_id)
        finally:
            await vnb_client.close()

        if vnb_details:
            resolved_website = resolved_website or vnb_details.homepage_url
            resolved_phone = resolved_phone or vnb_details.phone
            resolved_email = resolved_email or vnb_details.email
            resolved_official_name = resolved_official_name or vnb_details.name

    address_to_enrich: str | None = None
    if not resolved_contact_address and vnb_details and vnb_details.address:
        resolved_contact_address = vnb_details.address
        address_to_enrich = vnb_details.address

    if resolved_website:
        enrichment = await enrich_dno_from_web(
            resolved_website,
            address_to_enrich,
            verify_robots=True,
            include_tech_info=True,
        )

        if enrichment.robots:
            crawlable = enrichment.robots.crawlable
            crawl_blocked_reason = enrichment.robots.blocked_reason
            robots_txt = enrichment.robots.raw_content
            sitemap_urls = enrichment.robots.sitemap_urls
            disallow_paths = enrichment.robots.disallow_paths

        tech_info = enrichment.tech_info

        if address_to_enrich:
            resolved_contact_address = enrichment.enriched_address or address_to_enrich

    return DNOCreationResolvedData(
        official_name=resolved_official_name,
        website=resolved_website,
        phone=resolved_phone,
        email=resolved_email,
        contact_address=resolved_contact_address,
        crawlable=crawlable,
        crawl_blocked_reason=crawl_blocked_reason,
        robots_txt=robots_txt,
        sitemap_urls=sitemap_urls,
        disallow_paths=disallow_paths,
        tech_info=tech_info,
    )
