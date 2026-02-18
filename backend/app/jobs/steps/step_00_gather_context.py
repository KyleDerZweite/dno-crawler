"""
Step 00: Gather Context + Pre-Flight Checks

First step in the crawl pipeline. Loads all relevant information
about the DNO and runs pre-flight checks before discovery begins.

What it does:
- Load DNO details (name, slug, website)
- Pre-flight: cancel early for no-website, robots blocking, Cloudflare
- Load source profiles for BOTH data types (netzentgelte and hlzf)
- Check for cached files in data/downloads/{slug}/ for both types

Output stored in job.context:
- dno_id, dno_slug, dno_name, dno_website
- profiles: dict of {data_type: {url_pattern, source_format}} for each type
- cached_files: dict of {data_type: path} for existing files
- dno_crawlable, crawl_blocked_reason
"""

from pathlib import Path

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import CrawlJobModel, DNOModel, DNOSourceProfile
from app.jobs.steps.base import BaseStep, StepError
from app.services.user_agent import build_user_agent

logger = structlog.get_logger()

# Cloudflare challenge markers in response body
_CF_CHALLENGE_MARKERS = [
    "cf-browser-verification",
    "cf_chl_opt",
    "cf-challenge-running",
    "Checking your browser",
    "challenges.cloudflare.com",
]


class GatherContextStep(BaseStep):
    label = "Gathering Context"
    description = "Loading DNO info, running pre-flight checks, and checking for cached files..."

    async def run(self, db: AsyncSession, job: CrawlJobModel) -> str:
        log = logger.bind(dno_id=job.dno_id, job_id=job.id)

        # 1. Load DNO from database
        dno = await db.get(DNOModel, job.dno_id)
        if not dno:
            raise ValueError(f"DNO not found: {job.dno_id}")

        # =================================================================
        # Pre-flight check A: No website
        # =================================================================
        if not dno.website or not dno.website.strip():
            log.warning("preflight_no_website", dno=dno.name)
            dno.crawlable = False
            dno.crawl_blocked_reason = "no_website"
            await db.commit()
            raise StepError(
                f"DNO '{dno.name}' has no website configured. Cannot crawl without a known domain."
            )

        # =================================================================
        # Pre-flight checks B & C: robots.txt and Cloudflare
        # =================================================================
        initiator_ip = (job.context or {}).get("initiator_ip")
        user_agent = build_user_agent(initiator_ip)

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=10.0, write=5.0, pool=5.0),
            headers={"User-Agent": user_agent},
            follow_redirects=True,
            trust_env=False,
        ) as client:
            # B) robots.txt blocks root
            from app.services.url_utils import RobotsChecker

            robots = RobotsChecker(client)
            root_allowed = await robots.can_fetch(dno.website)
            if not root_allowed:
                log.warning("preflight_robots_blocked", dno=dno.name, url=dno.website)
                dno.crawlable = False
                dno.crawl_blocked_reason = "robots_txt_disallow"
                await db.commit()
                raise StepError(
                    f"robots.txt disallows crawling the root of {dno.website}. "
                    f"DNO marked as not crawlable."
                )

            # C) Cloudflare/challenge page detection
            try:
                response = await client.get(dno.website)
                if response.status_code == 403 and any(
                    marker in response.text for marker in _CF_CHALLENGE_MARKERS
                ):
                    log.warning("preflight_cloudflare", dno=dno.name, url=dno.website)
                    dno.crawlable = False
                    dno.crawl_blocked_reason = "cloudflare"
                    await db.commit()
                    raise StepError(
                        f"Cloudflare challenge page detected on {dno.website}. "
                        f"DNO marked as not crawlable."
                    )
            except StepError:
                raise
            except Exception as e:
                # Non-fatal: homepage fetch failed, but we can still try crawling
                log.debug("preflight_homepage_fetch_failed", error=str(e), url=dno.website)

        # If the DNO was previously blocked, clear the flag (pre-flight passed)
        if getattr(dno, "crawlable", True) is False:
            dno.crawlable = True
            dno.crawl_blocked_reason = None

        # =================================================================
        # 2. Load source profiles for BOTH data types
        # =================================================================
        profiles = {}
        for dt in ("netzentgelte", "hlzf"):
            profile_query = select(DNOSourceProfile).where(
                DNOSourceProfile.dno_id == job.dno_id, DNOSourceProfile.data_type == dt
            )
            result = await db.execute(profile_query)
            profile = result.scalar_one_or_none()
            if profile:
                profiles[dt] = {
                    "url_pattern": profile.url_pattern,
                    "source_format": profile.source_format,
                    "source_domain": getattr(profile, "source_domain", None),
                }

        # =================================================================
        # 3. Check for cached files for both types (path traversal protection)
        # =================================================================
        base_dir = Path(settings.downloads_path)
        cache_dir = base_dir / dno.slug
        if not cache_dir.resolve().is_relative_to(base_dir.resolve()):
            raise ValueError(f"Invalid slug for path construction: {dno.slug}")

        cached_files = {}
        if cache_dir.exists():
            for dt in ("netzentgelte", "hlzf"):
                pattern = f"{dno.slug}-{dt}-{job.year}.*"
                found = list(cache_dir.glob(pattern))
                if found:
                    cached_files[dt] = str(found[0])

        # =================================================================
        # 4. Build context
        # =================================================================
        job.context = {
            **(job.context or {}),
            "dno_id": dno.id,
            "dno_slug": dno.slug,
            "dno_name": dno.name,
            "dno_website": dno.website,
            "profiles": profiles,
            "cached_files": cached_files,
            "dno_crawlable": getattr(dno, "crawlable", True),
            "crawl_blocked_reason": getattr(dno, "crawl_blocked_reason", None),
        }
        await db.commit()

        # Return summary based on what we found
        profile_types = list(profiles.keys())
        cached_types = list(cached_files.keys())
        parts = []
        if cached_types:
            parts.append(f"cached: {', '.join(cached_types)}")
        if profile_types:
            parts.append(f"profiles: {', '.join(profile_types)}")
        if parts:
            return f"Context loaded for {dno.name} ({'; '.join(parts)})"
        return f"No prior knowledge for {dno.name} - will search from scratch"
