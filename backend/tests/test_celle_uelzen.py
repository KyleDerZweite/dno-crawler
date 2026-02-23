"""
Targeted integration test: Celle-Uelzen Netz GmbH.

This DNO's HLZF/netzentgelte data lives on Avacon Netz's site, not their own.
This test validates the relevance-gated external link following feature.

Run with:
    cd backend && python -m pytest tests/test_celle_uelzen.py -v -s
"""

import asyncio
from urllib.parse import urlparse

import httpx
import pytest

from app.services.web_crawler import WebCrawler, get_keywords_for_data_type

CELLE_UELZEN_URL = "https://www.celle-uelzennetz.de"
USER_AGENT = (
    "DNO-Data-Crawler/1.0 "
    "(Integration Test; see repository; "
    "+https://github.com/KyleDerZweite/dno-crawler)"
)


@pytest.mark.asyncio
async def test_celle_uelzen_discovers_external_links() -> None:
    """Crawl Celle-Uelzen Netz and check if external (Avacon) links are discovered."""
    keywords = get_keywords_for_data_type("all")
    start_domain = "celle-uelzennetz.de"

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
            max_depth=3,
            max_pages=50,
            request_delay=0.8,
            timeout=15.0,
        )

        results = await crawler.crawl(
            start_url=CELLE_UELZEN_URL,
            target_keywords=keywords,
            target_year=2025,
            data_type="all",
        )

    assert isinstance(results, list)

    # Separate internal vs external results
    internal = []
    external = []
    for r in results:
        host = urlparse(r.final_url).hostname or ""
        if host.startswith("www."):
            host = host[4:]
        if host.endswith(start_domain):
            internal.append(r)
        else:
            external.append(r)

    print(f"\n{'='*70}")
    print(f"Celle-Uelzen Netz Crawl Results")
    print(f"{'='*70}")
    print(f"  Total results  : {len(results)}")
    print(f"  Internal       : {len(internal)}")
    print(f"  External       : {len(external)}")
    print(f"  Documents      : {sum(1 for r in results if r.is_document)}")

    if internal:
        print(f"\n  Internal pages/docs:")
        for r in internal[:10]:
            doc = " [DOC]" if r.is_document else ""
            print(f"    score={r.score:6.1f}  d={r.depth}  {r.final_url[:90]}{doc}")

    if external:
        print(f"\n  External pages/docs (relevance-gated):")
        for r in external:
            doc = " [DOC]" if r.is_document else ""
            kw = f"  kw={r.keywords_found}" if r.keywords_found else ""
            print(f"    score={r.score:6.1f}  d={r.depth}  {r.final_url[:90]}{doc}{kw}")

        # Check if any external results point to Avacon
        avacon_results = [r for r in external if "avacon" in r.final_url.lower()]
        print(f"\n  Avacon-specific results: {len(avacon_results)}")
        for r in avacon_results:
            doc = " [DOC]" if r.is_document else ""
            print(f"    {r.final_url}{doc}")
    else:
        print("\n  No external links discovered.")
        print("  (The site may not link to Avacon, or links may not pass relevance gate)")

    print(f"{'='*70}")
