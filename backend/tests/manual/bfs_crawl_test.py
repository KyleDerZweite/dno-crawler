"""
Manual test script for BFS Web Crawler.

Tests the new BFS crawler against real DNO websites to verify:
1. robots.txt compliance
2. URL normalization and deduplication
3. Priority queue scoring
4. Document detection (PDFs, XLSX)
5. Pattern learning

Run:
    python -m tests.manual.bfs_crawl_test

Options:
    --dno rheinnetz|westnetz|generic
    --data-type netzentgelte|hlzf
    --year 2024
    --max-pages 20
    --verbose
"""

import argparse
import asyncio
from datetime import datetime

import httpx

from app.services.pattern_learner import PatternLearner
from app.services.url_utils import RobotsChecker, normalize_url
from app.services.web_crawler import WebCrawler, get_keywords_for_data_type

# =============================================================================
# Test DNO Websites
# =============================================================================

DNO_WEBSITES = {
    "rheinnetz": "https://www.rheinnetz.de",
    "westnetz": "https://www.westnetz.de",
    "enbw": "https://www.netze-bw.de",
    "avacon": "https://www.avacon-netz.de",
}


# =============================================================================
# Test Functions
# =============================================================================


async def test_robots_compliance(client: httpx.AsyncClient, base_url: str):
    """Test robots.txt fetching and compliance checking."""
    print("\n" + "=" * 60)
    print("🤖 ROBOTS.TXT COMPLIANCE TEST")
    print("=" * 60)

    checker = RobotsChecker(client)

    # Test some URLs
    test_paths = [
        "/",
        "/netzentgelte/",
        "/downloads/",
        "/veroeffentlichungen/",
        "/karriere/",  # Usually blocked
        "/admin/",     # Usually blocked
    ]

    for path in test_paths:
        url = base_url + path
        allowed = await checker.can_fetch(url)
        status = "✅ ALLOWED" if allowed else "🚫 BLOCKED"
        print(f"  {status}: {path}")

    return True


async def test_url_normalization():
    """Test URL normalization for deduplication."""
    print("\n" + "=" * 60)
    print("🔗 URL NORMALIZATION TEST")
    print("=" * 60)

    test_cases = [
        ("https://www.example.de/path/", "https://example.de/path/"),
        ("https://example.de/path?utm_source=google", "https://example.de/path/"),
        ("https://example.de/path#section", "https://example.de/path/"),
        ("https://example.de//path//to//file", "https://example.de/path/to/file/"),
        ("https://example.de/file.pdf", "https://example.de/file.pdf"),
        ("https://example.de/2024/data/", "https://example.de/2024/data/"),
    ]

    passed = 0
    for original, expected in test_cases:
        result = normalize_url(original)
        if result == expected:
            print(f"  ✅ {original[:40]} → {result}")
            passed += 1
        else:
            print(f"  ❌ {original[:40]}")
            print(f"     Expected: {expected}")
            print(f"     Got:      {result}")

    print(f"\n  Passed: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


async def test_pattern_extraction():
    """Test pattern learning year normalization."""
    print("\n" + "=" * 60)
    print("📝 PATTERN EXTRACTION TEST")
    print("=" * 60)

    learner = PatternLearner()

    test_urls = [
        "https://dno.de/downloads/2023/strom/preisblatt.pdf",
        "https://dno.de/veroeffentlichungen/netzentgelte/2024/",
        "https://dno.de/netz/preisblaetter/netzentgelte-2024.pdf",
        "https://dno.de/service/downloads/hlzf.pdf",
    ]

    for url in test_urls:
        patterns = learner._extract_path_patterns(url)
        print(f"\n  URL: {url}")
        print(f"  Patterns: {patterns}")

    return True


async def test_bfs_crawl(
    client: httpx.AsyncClient,
    base_url: str,
    data_type: str,
    year: int,
    max_pages: int,
    verbose: bool,
):
    """Test full BFS crawl on a DNO website."""
    print("\n" + "=" * 60)
    print(f"🕸️  BFS CRAWL TEST: {base_url}")
    print("=" * 60)
    print(f"  Data Type: {data_type}")
    print(f"  Year: {year}")
    print(f"  Max Pages: {max_pages}")

    crawler = WebCrawler(
        client=client,
        max_depth=3,
        max_pages=max_pages,
        request_delay=0.5,
    )

    keywords = get_keywords_for_data_type(data_type)
    print(f"  Keywords: {keywords[:5]}...")

    # Get some priority patterns (would normally come from DB)
    mock_patterns = [
        "/veroeffentlichungen/",
        "/downloads/",
        "/netzentgelte/",
        "/netz/",
        "/downloads/{year}/",
    ]

    start_time = datetime.now()

    results = await crawler.crawl(
        start_url=base_url,
        target_keywords=keywords,
        priority_paths=mock_patterns,
        target_year=year,
    )

    elapsed = (datetime.now() - start_time).total_seconds()

    print(f"\n  ⏱️  Crawl completed in {elapsed:.1f}s")
    print(f"  📄 Total results: {len(results)}")

    # Separate documents from pages
    documents = [r for r in results if r.is_document]
    pages = [r for r in results if not r.is_document]

    print(f"  📎 Documents found: {len(documents)}")
    print(f"  🌐 Pages found: {len(pages)}")

    # Show top documents
    if documents:
        print("\n  📎 TOP DOCUMENTS:")
        for doc in documents[:10]:
            print(f"     [{doc.score:5.1f}] {doc.final_url}")
            if verbose:
                print(f"           Type: {doc.content_type}")
                print(f"           Keywords: {doc.keywords_found}")

    # Show top pages
    if pages and verbose:
        print("\n  🌐 TOP PAGES:")
        for page in pages[:5]:
            print(f"     [{page.score:5.1f}] {page.final_url}")
            if page.title:
                print(f"           Title: {page.title[:60]}")
            print(f"           Keywords: {page.keywords_found}")

    # Check for SPA warnings
    spa_pages = [r for r in results if r.needs_headless]
    if spa_pages:
        print(f"\n  ⚠️  SPA DETECTED ({len(spa_pages)} pages may need headless browser)")

    return len(documents) > 0


# =============================================================================
# Main
# =============================================================================


async def main():
    parser = argparse.ArgumentParser(description="Test BFS Web Crawler")
    parser.add_argument("--dno", default="rheinnetz", choices=list(DNO_WEBSITES.keys()))
    parser.add_argument("--data-type", default="netzentgelte", choices=["netzentgelte", "hlzf"])
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--skip-crawl", action="store_true", help="Skip actual crawl test")

    args = parser.parse_args()

    base_url = DNO_WEBSITES.get(args.dno, args.dno)
    if not base_url.startswith("http"):
        base_url = "https://" + base_url

    print("=" * 60)
    print("🔍 BFS WEB CRAWLER TEST SUITE")
    print("=" * 60)
    print(f"Target: {base_url}")
    print(f"Time: {datetime.now().isoformat()}")

    async with httpx.AsyncClient(
        headers={"User-Agent": "DNO-Data-Crawler/1.0 (Test Script)"},
        follow_redirects=True,
        timeout=15.0,
    ) as client:

        # Run tests
        results = {}

        # Test 1: URL Normalization
        results["normalization"] = await test_url_normalization()

        # Test 2: Pattern Extraction
        results["patterns"] = await test_pattern_extraction()

        # Test 3: Robots.txt
        results["robots"] = await test_robots_compliance(client, base_url)

        # Test 4: Full BFS Crawl
        if not args.skip_crawl:
            results["crawl"] = await test_bfs_crawl(
                client=client,
                base_url=base_url,
                data_type=args.data_type,
                year=args.year,
                max_pages=args.max_pages,
                verbose=args.verbose,
            )

        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        for test_name, passed in results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"  {status}: {test_name}")

        all_passed = all(results.values())
        print("\n" + ("✅ ALL TESTS PASSED" if all_passed else "❌ SOME TESTS FAILED"))

        return 0 if all_passed else 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
