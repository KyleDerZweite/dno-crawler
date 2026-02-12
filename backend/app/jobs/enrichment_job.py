"""
DNO Enrichment Job.

Background job that enriches DNO records with data from external sources:
1. VNB Digital API - website, contact info
2. robots.txt - crawlability, sitemaps, disallow paths
3. Impressum extraction - additional contact details (future)
4. BDEW codes - (future, requires separate lookup)

This job runs asynchronously with low priority to avoid blocking
high-priority crawl jobs.
"""

from datetime import UTC, datetime

import httpx
import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DNOModel
from app.services.robots_parser import fetch_robots_txt
from app.services.vnb import VNBDigitalClient
from app.services.vnb.models import VNBResult

logger = structlog.get_logger()


async def enrich_dno(ctx: dict, dno_id: int) -> dict:
    """
    Enrich a single DNO with external data.

    This is the main ARQ job function.

    Args:
        ctx: ARQ context (contains db session factory)
        dno_id: ID of the DNO to enrich

    Returns:
        Result dict with status and details
    """
    from app.db import get_db

    log = logger.bind(dno_id=dno_id)
    log.info("Starting DNO enrichment")

    result = {
        "dno_id": dno_id,
        "status": "failed",
        "vnb_lookup": False,
        "robots_check": False,
        "website_found": None,
        "crawlable": None,
        "error": None,
    }

    async for db in get_db():
        try:
            # Mark as processing
            await db.execute(
                update(DNOModel)
                .where(DNOModel.id == dno_id)
                .values(enrichment_status="processing")
            )
            await db.commit()

            # Get DNO record
            stmt = select(DNOModel).where(DNOModel.id == dno_id)
            dno = (await db.execute(stmt)).scalar_one_or_none()

            if not dno:
                log.error("DNO not found")
                result["error"] = "DNO not found"
                return result

            log = log.bind(dno_name=dno.name, dno_slug=dno.slug)

            # === Step 1: VNB Digital Lookup ===
            website, vnb_data = await _lookup_vnb_digital(dno, log)
            result["vnb_lookup"] = True
            result["website_found"] = website

            if vnb_data:
                # Update DNO with VNB data
                dno.vnb_id = vnb_data.get("vnb_id")
                dno.website = website
                dno.official_name = vnb_data.get("official_name")
                if vnb_data.get("phone"):
                    dno.phone = vnb_data["phone"]
                if vnb_data.get("email"):
                    dno.email = vnb_data["email"]
                if vnb_data.get("contact_address") and not dno.contact_address:
                    dno.contact_address = vnb_data["contact_address"]

            # === Step 2: Robots.txt Check ===
            if website:
                robots_result = await _check_robots(website, log)
                result["robots_check"] = True
                result["crawlable"] = robots_result.get("crawlable", True)

                dno.robots_txt = robots_result.get("raw_content")
                dno.sitemap_urls = robots_result.get("sitemap_urls")
                dno.disallow_paths = robots_result.get("disallow_paths")
                dno.crawlable = robots_result.get("crawlable", True)
                dno.crawl_blocked_reason = robots_result.get("blocked_reason")
            else:
                log.warning("No website found, skipping robots.txt check")

            # === Step 3: Mark as Completed ===
            dno.enrichment_status = "completed"
            dno.last_enriched_at = datetime.now(UTC)

            await db.commit()

            result["status"] = "completed"
            log.info(
                "DNO enrichment completed",
                website=website,
                crawlable=result.get("crawlable"),
            )

        except Exception as e:
            log.error("Enrichment failed", error=str(e))
            result["error"] = str(e)

            # Mark as failed
            try:
                await db.execute(
                    update(DNOModel)
                    .where(DNOModel.id == dno_id)
                    .values(enrichment_status="failed")
                )
                await db.commit()
            except Exception:
                pass

    return result


async def _lookup_vnb_digital(dno: DNOModel, log) -> tuple[str | None, dict | None]:
    """
    Look up DNO in VNB Digital API.

    Tries multiple strategies:
    1. Search by address (if available)
    2. Search by name, then get details

    Returns:
        (website_url, vnb_data_dict) or (None, None)
    """
    try:
        client = VNBDigitalClient(request_delay=1.0)

        # Try address search first if we have address components
        if dno.address_components:
            addr = dno.address_components
            street = addr.get("street", "")
            house_nr = addr.get("house_number", "")
            zip_code = addr.get("zip_code", "")
            city = addr.get("city", "")

            if street and zip_code:
                address_query = f"{street} {house_nr}, {zip_code} {city}".strip()
                log.debug("Searching VNB Digital by address", query=address_query)

                location = await client.search_address(address_query)
                if location and location.coordinates:
                    # Look up DNO at these coordinates
                    vnb_results = await client.lookup_by_coordinates(location.coordinates)
                    if vnb_results:
                        # Find best match by name similarity
                        vnb = _find_best_match(dno.name, vnb_results)
                        if vnb:
                            # Get detailed info including website
                            details = await client.get_vnb_details(vnb.vnb_id)
                            if details:
                                return details.homepage_url, {
                                    "vnb_id": vnb.vnb_id,
                                    "official_name": details.name,
                                    "phone": details.phone,
                                    "email": details.email,
                                    "contact_address": details.address,
                                }

        # Fallback: Search by name
        log.debug("Searching VNB Digital by name", name=dno.name)
        vnb_results = await client.search_vnb(dno.name)
        if vnb_results:
            # Get first match and fetch details
            vnb = vnb_results[0]
            details = await client.get_vnb_details(vnb.vnb_id)
            if details:
                return details.homepage_url, {
                    "vnb_id": vnb.vnb_id,
                    "official_name": details.name,
                    "phone": details.phone,
                    "email": details.email,
                    "contact_address": details.address,
                }

        log.warning("No VNB Digital result found")
        return None, None

    except Exception as e:
        log.error("VNB Digital lookup failed", error=str(e))
        return None, None


def _find_best_match(target_name: str, results: list[VNBResult]) -> VNBResult | None:
    """Find best matching VNB result by name similarity."""
    target_lower = target_name.lower()

    for result in results:
        result_name = result.name.lower()
        # Simple containment check
        if target_lower in result_name or result_name in target_lower:
            return result

    # Return first result as fallback
    return results[0] if results else None


async def _check_robots(website: str, log) -> dict:
    """
    Check robots.txt for a website.

    Returns dict with:
    - raw_content: Full robots.txt
    - sitemap_urls: List of sitemap URLs
    - disallow_paths: List of disallowed paths
    - crawlable: Boolean
    - blocked_reason: String if blocked
    """
    try:
        async with httpx.AsyncClient() as client:
            result = await fetch_robots_txt(client, website)

        return {
            "raw_content": result.raw_content,
            "sitemap_urls": result.sitemap_urls if result.sitemap_urls else None,
            "disallow_paths": result.disallow_paths if result.disallow_paths else None,
            "crawlable": result.crawlable,
            "blocked_reason": result.blocked_reason,
        }

    except Exception as e:
        log.error("Robots.txt check failed unexpectedly", error=str(e), error_type=type(e).__name__)
        return {
            "raw_content": None,
            "sitemap_urls": None,
            "disallow_paths": None,
            "crawlable": False,  # Assume NOT crawlable if check fails - safer default
            "blocked_reason": "check_failed",
        }


async def queue_enrichment_jobs(db: AsyncSession, limit: int = 100) -> int:
    """
    Queue enrichment jobs for DNOs with pending enrichment status.

    Args:
        db: Database session
        limit: Maximum number of jobs to queue

    Returns:
        Number of jobs queued
    """
    from arq import create_pool
    from arq.connections import RedisSettings

    from app.core.config import settings

    # Get DNOs needing enrichment
    stmt = select(DNOModel.id).where(
        DNOModel.enrichment_status == "pending"
    ).limit(limit)

    result = await db.execute(stmt)
    dno_ids = list(result.scalars().all())

    if not dno_ids:
        logger.info("No DNOs need enrichment")
        return 0

    logger.info("Queueing enrichment jobs", count=len(dno_ids))

    # Create Redis pool and enqueue jobs
    redis = await create_pool(RedisSettings.from_dsn(str(settings.redis_url)))

    for dno_id in dno_ids:
        await redis.enqueue_job(
            "enrich_dno",
            dno_id,
            _job_id=f"enrich-{dno_id}",
            _queue_name="crawl",
        )

    await redis.close()

    logger.info("Enrichment jobs queued", count=len(dno_ids))
    return len(dno_ids)


async def enqueue_enrichment_job(dno_id: int) -> bool:
    """Enqueue a single enrichment job for a given DNO ID."""
    from arq import create_pool
    from arq.connections import RedisSettings

    from app.core.config import settings

    redis = await create_pool(RedisSettings.from_dsn(str(settings.redis_url)))
    try:
        await redis.enqueue_job(
            "enrich_dno",
            dno_id,
            _job_id=f"enrich-{dno_id}",
            _queue_name="crawl",
        )
        logger.info("Enqueued enrichment job", dno_id=dno_id)
        return True
    finally:
        await redis.close()
