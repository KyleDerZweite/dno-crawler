"""
Step 01: Discover

Combined strategy and discovery step. Finds data sources via:
1. Cached file (if exists) → Skip crawling
2. Exact URL from profile → Try known URL with year substitution
2.5. Sitemap discovery → Fast sitemap-based discovery via DiscoveryManager
3. Learned patterns → Try top patterns on DNO domain
4. BFS crawl → Full website crawl with keyword scoring

Content verification before accepting a candidate:
- Verifies content matches expected data_type (netzentgelte vs hlzf)
- Tries multiple candidates if first doesn't verify
- Stores verification confidence and rejected candidates

Output stored in job.context:
- strategy: "use_cache" | "exact_url" | "sitemap_*" | "pattern_match" | "bfs_crawl"
- found_url: URL of discovered data source
- discovered_via_pattern: Which pattern found it (if pattern_match)
- pages_crawled: Number of pages crawled (for metrics)
- sitemap_urls_checked: Number of URLs checked from sitemap
- verification_confidence: Confidence score from content verification
- rejected_candidates: List of URLs that failed verification
"""

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import CrawlJobModel
from app.jobs.steps.base import BaseStep
from app.services.content_verifier import ContentVerifier
from app.services.discovery import DiscoveryManager
from app.services.pattern_learner import PatternLearner
from app.services.url_utils import UrlProber
from app.services.user_agent import build_user_agent, require_contact_for_bfs
from app.services.web_crawler import WebCrawler, get_keywords_for_data_type

logger = structlog.get_logger()

# Maximum candidates to try before giving up
MAX_CANDIDATES_TO_TRY = 5

# Minimum confidence required to accept a candidate
MIN_VERIFICATION_CONFIDENCE = 0.4


class DiscoverStep(BaseStep):
    """Discover data source via BFS crawling or cached patterns."""

    label = "Discovering Source"
    description = "Finding data source via web crawling..."

    async def run(self, db: AsyncSession, job: CrawlJobModel) -> str:
        ctx = job.context or {}
        log = logger.bind(dno=ctx.get("dno_name"), data_type=job.data_type, year=job.year)

        # Initialize context fields
        ctx["pages_crawled"] = 0
        ctx["needs_headless_review"] = False
        ctx["discovered_via_pattern"] = None
        ctx["verification_confidence"] = None
        ctx["rejected_candidates"] = []

        # =========================================================================
        # Strategy 1: Use cached file
        # =========================================================================
        if ctx.get("cached_file"):
            ctx["strategy"] = "use_cache"
            ctx["file_to_process"] = ctx["cached_file"]
            job.context = ctx
            await db.commit()
            log.info("Using cached file", path=ctx["cached_file"])
            return f"Strategy: USE_CACHE → {ctx['cached_file']}"

        # =========================================================================
        # Check: If DNO is protected and no cached file, cancel gracefully
        # =========================================================================
        dno_crawlable = ctx.get("dno_crawlable", True)
        if not dno_crawlable:
            blocked_reason = ctx.get("crawl_blocked_reason", "unknown protection")
            from app.jobs.steps.base import StepError
            raise StepError(
                f"Cancelled: Site is protected ({blocked_reason}) and no local file found "
                f"for {job.data_type} {job.year}. Please upload the file manually."
            )

        # Build User-Agent for non-BFS strategies (sitemap, pattern match)
        initiator_ip = ctx.get("initiator_ip")
        user_agent = build_user_agent(initiator_ip)

        # Need HTTP client for remaining strategies
        async with httpx.AsyncClient(
            timeout=15.0,
            headers={"User-Agent": user_agent},
            follow_redirects=True,
            trust_env=False,
        ) as client:
            prober = UrlProber(client)
            learner = PatternLearner()
            verifier = ContentVerifier(client)

            # Get allowed domains from DNO website
            allowed_domains = self._get_allowed_domains(ctx)

            # =====================================================================
            # Strategy 2: Try exact URL from profile (with year substitution)
            # =====================================================================
            if ctx.get("profile_url_pattern"):
                pattern = ctx["profile_url_pattern"]
                exact_url = pattern.replace("{year}", str(job.year))

                log.info("Trying exact URL from profile", url=exact_url[:80])

                is_valid, content_type, final_url, _ = await prober.probe(
                    exact_url,
                    allowed_domains=allowed_domains,
                )

                if is_valid and final_url:
                    # Verify content matches expected data type
                    verification = await verifier.verify_url(
                        final_url, job.data_type, job.year
                    )

                    if verification.is_verified:
                        ctx["strategy"] = "exact_url"
                        ctx["found_url"] = final_url
                        ctx["found_content_type"] = content_type
                        ctx["verification_confidence"] = verification.confidence
                        job.context = ctx
                        await db.commit()
                        return f"Strategy: EXACT_URL → {final_url} (verified: {verification.confidence:.0%})"
                    else:
                        log.warning(
                            "Exact URL failed verification",
                            url=final_url[:60],
                            detected=verification.detected_data_type,
                            expected=job.data_type,
                            confidence=verification.confidence,
                        )
                        ctx["rejected_candidates"].append({
                            "url": final_url,
                            "reason": "content_verification_failed",
                            "detected": verification.detected_data_type,
                            "confidence": verification.confidence,
                        })
                else:
                    log.info("Exact URL failed, trying sitemap")

            # =====================================================================
            # Strategy 2.5: Sitemap-based discovery (fast, low-impact)
            # =====================================================================
            dno_website = ctx.get("dno_website")
            if dno_website:
                discovery = DiscoveryManager(client)

                log.info("Trying sitemap discovery", website=dno_website[:50])

                discovery_result = await discovery.discover(
                    base_url=dno_website,
                    data_type=job.data_type,
                    target_year=job.year,
                    max_candidates=10,
                )

                if discovery_result.documents:
                    log.info(
                        "Sitemap discovered candidates",
                        count=len(discovery_result.documents),
                        strategy=discovery_result.strategy.value,
                    )

                    # Try top candidates with verification
                    for doc in discovery_result.documents[:MAX_CANDIDATES_TO_TRY]:
                        verification = await verifier.verify_url(
                            doc.url, job.data_type, job.year
                        )

                        if verification.is_verified:
                            ctx["strategy"] = f"sitemap_{discovery_result.strategy.value}"
                            ctx["found_url"] = doc.url
                            ctx["found_content_type"] = doc.file_type.value if doc.file_type else None
                            ctx["verification_confidence"] = verification.confidence
                            ctx["sitemap_urls_checked"] = discovery_result.sitemap_urls_checked
                            job.context = ctx
                            await db.commit()
                            return f"Strategy: SITEMAP → {doc.url} (verified: {verification.confidence:.0%})"
                        else:
                            ctx["rejected_candidates"].append({
                                "url": doc.url,
                                "reason": "content_verification_failed",
                                "source": "sitemap",
                                "detected": verification.detected_data_type,
                            })

                    log.info("Sitemap candidates failed verification, trying patterns")
                else:
                    log.info("No sitemap candidates found, trying patterns")

            # =====================================================================
            # Strategy 3: Try learned path patterns
            # =====================================================================
            dno_website = ctx.get("dno_website")
            if dno_website:
                patterns = await learner.get_priority_paths(db, job.data_type, limit=5)

                for pattern in patterns:
                    expanded = learner.expand_pattern(pattern, job.year)
                    test_url = dno_website.rstrip("/") + expanded

                    log.debug("Trying learned pattern", pattern=pattern, url=test_url[:80])

                    is_valid, content_type, final_url, _ = await prober.probe(
                        test_url,
                        allowed_domains=allowed_domains,
                    )

                    if is_valid and final_url:
                        # Verify content
                        verification = await verifier.verify_url(
                            final_url, job.data_type, job.year
                        )

                        if verification.is_verified:
                            ctx["strategy"] = "pattern_match"
                            ctx["found_url"] = final_url
                            ctx["found_content_type"] = content_type
                            ctx["discovered_via_pattern"] = pattern
                            ctx["verification_confidence"] = verification.confidence
                            job.context = ctx
                            await db.commit()
                            log.info(
                                "Found via learned pattern",
                                pattern=pattern,
                                url=final_url[:80],
                                confidence=verification.confidence,
                            )
                            return f"Strategy: PATTERN_MATCH → {pattern} → {final_url} (verified: {verification.confidence:.0%})"
                        else:
                            log.debug(
                                "Pattern URL failed verification",
                                pattern=pattern,
                                detected=verification.detected_data_type,
                            )
                            ctx["rejected_candidates"].append({
                                "url": final_url,
                                "reason": "content_verification_failed",
                                "pattern": pattern,
                                "detected": verification.detected_data_type,
                            })
                            # Record pattern failure
                            await learner.record_failure(db, pattern)
                    else:
                        # Record pattern failure (URL not found)
                        await learner.record_failure(db, pattern)

            # =====================================================================
            # Strategy 4: Full BFS crawl with multi-candidate verification
            # =====================================================================
            if not dno_website:
                raise ValueError(f"No website known for DNO {ctx.get('dno_name')}")

            log.info("Starting full BFS crawl", website=dno_website)

            # BFS crawling requires contact email in production
            # This will raise ValueError if in production without CONTACT_EMAIL
            bfs_user_agent = require_contact_for_bfs(initiator_ip)

            crawler = WebCrawler(
                client=client,
                user_agent=bfs_user_agent,
                max_depth=3,
                max_pages=getattr(settings, "crawler_max_pages", 50),
                request_delay=getattr(settings, "crawler_delay", 0.5),
            )

            keywords = get_keywords_for_data_type(job.data_type)
            patterns = await learner.get_priority_paths(db, job.data_type, limit=10)

            results = await crawler.crawl(
                start_url=dno_website,
                target_keywords=keywords,
                priority_paths=patterns,
                target_year=job.year,
                data_type=job.data_type,  # NEW: pass data_type for scoring
            )

            ctx["pages_crawled"] = len(results)

            # Try multiple document candidates with verification
            candidates_tried = 0
            document_results = [r for r in results if r.is_document]

            log.info(
                "Evaluating document candidates",
                total_documents=len(document_results),
                max_to_try=MAX_CANDIDATES_TO_TRY,
            )

            for result in document_results[:MAX_CANDIDATES_TO_TRY]:
                candidates_tried += 1

                # Verify content before accepting
                verification = await verifier.verify_url(
                    result.final_url, job.data_type, job.year
                )

                log.debug(
                    "Candidate verification",
                    url=result.final_url[:60],
                    score=round(result.score, 2),
                    verified=verification.is_verified,
                    confidence=verification.confidence,
                    detected=verification.detected_data_type,
                    keywords=verification.keywords_found[:5],
                )

                if verification.is_verified:
                    ctx["strategy"] = "bfs_crawl"
                    ctx["found_url"] = result.final_url
                    ctx["found_content_type"] = result.content_type
                    ctx["needs_headless_review"] = result.needs_headless
                    ctx["verification_confidence"] = verification.confidence
                    ctx["candidates_tried"] = candidates_tried
                    job.context = ctx
                    await db.commit()
                    log.info(
                        "Found verified document via BFS",
                        url=result.final_url[:80],
                        score=round(result.score, 2),
                        depth=result.depth,
                        confidence=verification.confidence,
                        candidates_tried=candidates_tried,
                    )
                    return (
                        f"Strategy: BFS_CRAWL → {result.final_url} "
                        f"(score: {result.score:.1f}, verified: {verification.confidence:.0%}, "
                        f"tried: {candidates_tried}/{len(document_results)})"
                    )
                else:
                    ctx["rejected_candidates"].append({
                        "url": result.final_url,
                        "reason": "content_verification_failed",
                        "score": result.score,
                        "detected": verification.detected_data_type,
                        "confidence": verification.confidence,
                    })

            # If no verified documents, try high-scoring pages as fallback
            # (might contain tables or embedded content)
            page_results = [r for r in results if not r.is_document and r.score > 20]

            for result in page_results[:3]:
                verification = await verifier.verify_url(
                    result.final_url, job.data_type, job.year
                )

                if verification.is_verified and verification.confidence >= 0.5:
                    ctx["strategy"] = "bfs_crawl"
                    ctx["found_url"] = result.final_url
                    ctx["found_content_type"] = result.content_type
                    ctx["needs_headless_review"] = result.needs_headless
                    ctx["verification_confidence"] = verification.confidence
                    job.context = ctx
                    await db.commit()
                    log.info(
                        "Found verified page via BFS (may contain tables/embedded content)",
                        url=result.final_url[:80],
                        score=round(result.score, 2),
                        confidence=verification.confidence,
                    )
                    return (
                        f"Strategy: BFS_CRAWL → {result.final_url} "
                        f"(landing page, score: {result.score:.1f}, verified: {verification.confidence:.0%})"
                    )

            # No verified results found - report what was rejected
            job.context = ctx
            await db.commit()

            rejected_count = len(ctx["rejected_candidates"])
            error_msg = (
                f"No verified data source found for {ctx.get('dno_name')} after crawling "
                f"{ctx['pages_crawled']} pages. "
                f"Tried {len(document_results)} documents, {rejected_count} failed verification."
            )

            if ctx["rejected_candidates"]:
                # Log rejected candidates for debugging
                log.warning(
                    "All candidates failed verification",
                    rejected_count=rejected_count,
                    first_rejected=ctx["rejected_candidates"][0] if ctx["rejected_candidates"] else None,
                )

                # Capture crawl error sample for debugging
                from app.services.sample_capture import SampleCapture
                sample_capture = SampleCapture()
                await sample_capture.capture_crawl_error(
                    dno_slug=ctx.get("dno_slug", "unknown"),
                    url=dno_website,
                    error_type="all_candidates_failed_verification",
                    error_message=error_msg,
                    status_code=None,
                    response_headers=None,
                    response_body_snippet=None,
                    request_headers={"User-Agent": bfs_user_agent},
                    job_id=str(job.id),
                    step="discover",
                )
                # Also capture details of what was tried
                await sample_capture.capture_crawl_log(
                    dno_slug=ctx.get("dno_slug", "unknown"),
                    job_id=str(job.id),
                    step="discover",
                    action="verification_failed",
                    success=False,
                    details={
                        "pages_crawled": ctx["pages_crawled"],
                        "documents_found": len(document_results),
                        "candidates_tried": candidates_tried,
                        "rejected_candidates": ctx["rejected_candidates"][:10],  # Cap at 10
                        "data_type": job.data_type,
                        "year": job.year,
                    },
                )

            raise ValueError(error_msg)

    def _get_allowed_domains(self, ctx: dict) -> set[str] | None:
        """Extract allowed domains from context."""
        website = ctx.get("dno_website")
        if not website:
            return None

        try:
            from urllib.parse import urlparse
            parsed = urlparse(website)
            if parsed.hostname:
                domain = parsed.hostname.lower()
                if domain.startswith("www."):
                    domain = domain[4:]
                return {domain, f"www.{domain}"}
        except Exception:
            pass

        return None
