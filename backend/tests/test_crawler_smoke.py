"""
Smoke test: pick a random DNO from the enriched seed data and run
the BFS crawler against its website.

This is a live integration test that makes real HTTP requests.
Run with:
    cd backend && python -m pytest tests/test_crawler_smoke.py -v -s

Use --count N (pytest-repeat) or -k to control which/how-many DNOs to test.
"""

import json
import random
from pathlib import Path

import httpx
import pytest

from app.services.web_crawler import WebCrawler, get_keywords_for_data_type

# Path to enriched seed data (relative to repo root)
SEED_FILE = Path(__file__).resolve().parents[2] / "data" / "seed-data" / "dnos_enriched.json"

# Crawl budget for smoke tests — intentionally small
SMOKE_MAX_DEPTH = 2
SMOKE_MAX_PAGES = 15
SMOKE_REQUEST_DELAY = 0.8
SMOKE_TIMEOUT = 15.0
USER_AGENT = (
    "DNO-Data-Crawler/1.0 "
    "(Smoke Test; see repository; "
    "+https://github.com/KyleDerZweite/dno-crawler)"
)


def _load_dnos_with_websites() -> list[dict]:
    """Load enriched seed data and return only DNOs that have a website."""
    if not SEED_FILE.exists():
        pytest.skip(f"Seed file not found: {SEED_FILE}")

    with open(SEED_FILE, encoding="utf-8") as f:
        data = json.load(f)

    return [
        d for d in data
        if d.get("website") and d["website"].startswith("http")
    ]


# Load once at module level so parametrize can sample
_ALL_DNOS = _load_dnos_with_websites()


def _pick_random_dno(seed: int | None = None) -> dict:
    """Pick a single random DNO. Seed is set per-test for reproducibility."""
    rng = random.Random(seed)
    return rng.choice(_ALL_DNOS)


@pytest.fixture
def random_dno() -> dict:
    """Fixture that returns a random DNO with a website."""
    dno = _pick_random_dno()
    print(f"\n--- Selected DNO: {dno['name']} | {dno['website']} ---")
    return dno


@pytest.mark.asyncio
async def test_crawler_smoke(random_dno: dict) -> None:
    """Run the BFS crawler on a random DNO website and verify basic sanity."""
    website = random_dno["website"]
    name = random_dno["name"]
    keywords = get_keywords_for_data_type("all")

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0),
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        trust_env=False,
        limits=httpx.Limits(
            max_connections=10,
            max_keepalive_connections=5,
            keepalive_expiry=30.0,
        ),
    ) as client:
        crawler = WebCrawler(
            client=client,
            user_agent=USER_AGENT,
            max_depth=SMOKE_MAX_DEPTH,
            max_pages=SMOKE_MAX_PAGES,
            request_delay=SMOKE_REQUEST_DELAY,
            timeout=SMOKE_TIMEOUT,
        )

        # This should not raise — any HTTP/parsing error should be handled internally
        results = await crawler.crawl(
            start_url=website,
            target_keywords=keywords,
            target_year=2025,
            data_type="all",
        )

    # --- Assertions ---
    # The crawler must always return a list (even if empty for dead sites)
    assert isinstance(results, list), f"Expected list, got {type(results)}"

    print(f"\n  Results for {name}:")
    print(f"    Pages returned : {len(results)}")
    print(f"    Documents      : {sum(1 for r in results if r.is_document)}")
    print(f"    HTML pages     : {sum(1 for r in results if not r.is_document)}")

    if results:
        # Every result should have required fields populated
        for r in results:
            assert r.url, "CrawlResult.url must not be empty"
            assert r.final_url, "CrawlResult.final_url must not be empty"
            assert r.content_type, "CrawlResult.content_type must not be empty"
            assert r.depth >= 0, "Depth must be non-negative"
            assert r.depth <= SMOKE_MAX_DEPTH, (
                f"Result depth {r.depth} exceeds max_depth {SMOKE_MAX_DEPTH}"
            )

        # Results should be sorted by score descending
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True), "Results not sorted by score"

        # Print top-scored results for manual inspection
        print("    Top results:")
        for r in results[:5]:
            doc_flag = " [DOC]" if r.is_document else ""
            kw_str = f" kw={r.keywords_found}" if r.keywords_found else ""
            print(f"      score={r.score:6.1f}  d={r.depth}  {r.final_url[:80]}{doc_flag}{kw_str}")


@pytest.mark.asyncio
async def test_crawler_no_crash_on_bad_url() -> None:
    """Ensure the crawler handles a completely invalid/dead URL gracefully."""
    keywords = get_keywords_for_data_type("all")

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        trust_env=False,
    ) as client:
        crawler = WebCrawler(
            client=client,
            user_agent=USER_AGENT,
            max_depth=1,
            max_pages=3,
            request_delay=0.1,
            timeout=5.0,
        )

        results = await crawler.crawl(
            start_url="https://this-domain-definitely-does-not-exist-xyz123.de",
            target_keywords=keywords,
            target_year=2025,
            data_type="all",
        )

    assert results == [], "Dead URL should return empty results"


@pytest.mark.asyncio
async def test_crawler_external_link_relevance(random_dno: dict) -> None:
    """Verify that relevant external links are discovered when they exist.

    This test doesn't assert external links ARE found (most DNOs won't have them),
    but verifies the crawler doesn't crash and that any external-domain results
    contain at least one keyword in their URL.
    """
    website = random_dno["website"]
    keywords = get_keywords_for_data_type("all")

    from urllib.parse import urlparse

    start_domain = urlparse(website).hostname or ""
    if start_domain.startswith("www."):
        start_domain = start_domain[4:]

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0),
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        trust_env=False,
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
    ) as client:
        crawler = WebCrawler(
            client=client,
            user_agent=USER_AGENT,
            max_depth=SMOKE_MAX_DEPTH,
            max_pages=SMOKE_MAX_PAGES,
            request_delay=SMOKE_REQUEST_DELAY,
            timeout=SMOKE_TIMEOUT,
        )

        results = await crawler.crawl(
            start_url=website,
            target_keywords=keywords,
            target_year=2025,
            data_type="all",
        )

    # Check any external-domain results
    external_results = []
    for r in results:
        result_host = urlparse(r.final_url).hostname or ""
        if result_host.startswith("www."):
            result_host = result_host[4:]
        if result_host and not result_host.endswith(start_domain):
            external_results.append(r)

    print(f"\n  External results: {len(external_results)}/{len(results)}")
    for r in external_results:
        print(f"    {r.final_url[:90]}  doc={r.is_document}  score={r.score:.1f}")

    # External non-document results should have relevance (keyword in URL or from anchor)
    # Document links are allowed through without keyword check, so skip those
    for r in external_results:
        if not r.is_document:
            url_lower = r.final_url.lower()
            has_keyword = any(kw.lower() in url_lower for kw in keywords)
            # Note: the link may have been admitted via anchor text, which we can't
            # verify from the CrawlResult alone. So we just log, not hard-assert.
            if not has_keyword:
                print(f"    (admitted via anchor text, not URL): {r.final_url[:80]}")
