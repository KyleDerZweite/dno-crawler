#!/usr/bin/env python3
"""
Temporary script to re-check robots.txt and fetch sitemaps for all DNOs in the enriched JSON file.

Updates:
- robots_txt: Raw robots.txt content
- robots_fetched_at: Timestamp for TTL (150 days)
- sitemap_urls: URLs declared in robots.txt
- sitemap_parsed_urls: All URLs extracted from sitemaps (recursively)
- sitemap_fetched_at: Timestamp for TTL (120 days)
- crawlable: Whether site is crawlable
- blocked_reason: Why site is blocked (if any)

Usage:
    python scripts/recheck_robots.py [--limit LIMIT] [--delay DELAY]
"""

import argparse
import asyncio
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
import structlog

from app.services.robots_parser import fetch_and_verify_robots

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(colors=True),
    ]
)
logger = structlog.get_logger()


def parse_sitemap_content(xml_content: str) -> tuple[list[str], list[str]]:
    """
    Parse URLs from sitemap XML.

    Returns:
        Tuple of (urls, nested_sitemap_urls)
    """
    urls = []
    nested_sitemaps = []

    try:
        namespaces = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        root = ElementTree.fromstring(xml_content)

        # Check for sitemap index
        for sitemap_elem in root.findall(".//sm:sitemap", namespaces):
            loc = sitemap_elem.find("sm:loc", namespaces)
            if loc is not None and loc.text:
                nested_sitemaps.append(loc.text)

        # Try without namespace
        if not nested_sitemaps:
            for sitemap in root.iter("sitemap"):
                loc = sitemap.find("loc")
                if loc is not None and loc.text:
                    nested_sitemaps.append(loc.text)

        # Extract URLs from urlset
        for url_elem in root.findall(".//sm:url", namespaces):
            loc = url_elem.find("sm:loc", namespaces)
            if loc is not None and loc.text:
                urls.append(loc.text)

        # Try without namespace
        if not urls:
            for loc in root.iter("loc"):
                if loc.text and loc.text not in nested_sitemaps:
                    urls.append(loc.text)

    except ElementTree.ParseError:
        # Regex fallback
        pattern = r'<loc>([^<]+)</loc>'
        urls = re.findall(pattern, xml_content)

    return urls, nested_sitemaps


# Language path patterns to filter/prioritize
PREFERRED_LANG = "/de/"
FALLBACK_LANG = "/en/"
EXCLUDE_LANGS = ["/es/", "/it/", "/fr/", "/nl/", "/pt/", "/ru/", "/cn/", "/zh/", "/ja/", "/ko/", "/pl/", "/tr/"]


def filter_sitemaps_by_language(sitemap_urls: list[str]) -> list[str]:
    """
    Filter sitemap URLs to prefer German, fallback to English, exclude others.
    
    Priority:
    1. German (/de/) sitemaps
    2. English (/en/) sitemaps (if no German)
    3. Language-neutral sitemaps (no language path)
    """
    german_sitemaps = []
    english_sitemaps = []
    neutral_sitemaps = []

    for url in sitemap_urls:
        url_lower = url.lower()

        # Check for excluded languages first
        if any(lang in url_lower for lang in EXCLUDE_LANGS):
            continue

        # Categorize by language
        if PREFERRED_LANG in url_lower:
            german_sitemaps.append(url)
        elif FALLBACK_LANG in url_lower:
            english_sitemaps.append(url)
        else:
            # No language path - neutral
            neutral_sitemaps.append(url)

    # Return in priority order: German first, then English, then neutral
    if german_sitemaps:
        return german_sitemaps + neutral_sitemaps
    elif english_sitemaps:
        return english_sitemaps + neutral_sitemaps
    else:
        return neutral_sitemaps


async def fetch_sitemap_recursive(
    client: httpx.AsyncClient,
    sitemap_url: str,
    max_depth: int = 2,
    _current_depth: int = 0,
    delay: float = 0.3,
) -> list[str]:
    """
    Recursively fetch and parse sitemaps, following sitemap indexes.
    """
    all_urls = []

    if _current_depth >= max_depth:
        return all_urls

    try:
        # Add delay for politeness
        if _current_depth > 0:
            await asyncio.sleep(delay)

        response = await client.get(sitemap_url, timeout=15.0, follow_redirects=True)

        if response.status_code != 200:
            return all_urls

        content = response.text

        # Verify it's XML
        if not (content.strip().startswith("<?xml") or "<urlset" in content[:500] or "<sitemapindex" in content[:500]):
            return all_urls

        urls, nested_sitemaps = parse_sitemap_content(content)

        # Add direct URLs
        all_urls.extend(urls)

        # Filter nested sitemaps by language preference
        filtered_sitemaps = filter_sitemaps_by_language(nested_sitemaps)

        # Recursively fetch nested sitemaps
        for nested_url in filtered_sitemaps:
            nested_urls = await fetch_sitemap_recursive(
                client, nested_url, max_depth, _current_depth + 1, delay
            )
            all_urls.extend(nested_urls)

    except Exception as e:
        logger.debug("Sitemap fetch failed", url=sitemap_url[:60], error=str(e))

    return all_urls


async def recheck_robots_for_all(
    records: list[dict],
    delay: float = 0.5,
    limit: int | None = None,
) -> list[dict]:
    """
    Re-check robots.txt and fetch sitemaps for all records with a website.

    Updates: crawlable, blocked_reason, robots_txt, robots_fetched_at,
             sitemap_urls, sitemap_parsed_urls, sitemap_fetched_at, disallow_paths
    """
    log = logger.bind(total=len(records), limit=limit)
    log.info("Starting robots.txt and sitemap recheck")

    records_to_process = records[:limit] if limit else records
    updated = 0
    skipped = 0
    errors = 0

    now = datetime.now(UTC).isoformat()

    async with httpx.AsyncClient(
        headers={"User-Agent": "DNO-Crawler/1.0 (robots + sitemap check)"},
        follow_redirects=True,
    ) as client:
        for i, record in enumerate(records_to_process):
            name = record.get("name", "Unknown")[:40]
            website = record.get("website")

            if not website:
                skipped += 1
                continue

            record_log = log.bind(index=i + 1, name=name, website=website)

            try:
                # Add politeness delay
                if i > 0:
                    await asyncio.sleep(delay)

                result = await fetch_and_verify_robots(client, website, timeout=15.0)

                old_crawlable = record.get("crawlable", True)
                old_reason = record.get("blocked_reason")

                # Update record with full robots.txt data
                record["crawlable"] = result.crawlable
                record["blocked_reason"] = result.blocked_reason
                record["robots_txt"] = result.raw_content
                record["robots_fetched_at"] = now  # TTL: 150 days
                record["disallow_paths"] = result.disallow_paths

                # Set status to "protected" if blocked
                if result.blocked_reason:
                    record["status"] = "protected"

                # Filter sitemap URLs by language preference before storing
                filtered_sitemap_urls = filter_sitemaps_by_language(result.sitemap_urls or [])
                record["sitemap_urls"] = filtered_sitemap_urls  # Store only relevant sitemaps

                # Fetch and parse sitemaps recursively
                sitemap_parsed_urls = []
                if filtered_sitemap_urls:
                    record_log.info(
                        "Fetching sitemaps",
                        total=len(result.sitemap_urls or []),
                        filtered=len(filtered_sitemap_urls),
                    )
                    for sitemap_url in filtered_sitemap_urls:
                        urls = await fetch_sitemap_recursive(client, sitemap_url, delay=0.3)
                        sitemap_parsed_urls.extend(urls)
                    record_log.info("Parsed sitemap URLs", count=len(sitemap_parsed_urls))

                record["sitemap_parsed_urls"] = sitemap_parsed_urls
                record["sitemap_fetched_at"] = now if sitemap_parsed_urls else None  # TTL: 120 days

                if old_crawlable != result.crawlable or old_reason != result.blocked_reason:
                    record_log.info(
                        "Updated crawlability",
                        old_crawlable=old_crawlable,
                        new_crawlable=result.crawlable,
                        old_reason=old_reason,
                        new_reason=result.blocked_reason,
                        sitemap_verified=result.sitemap_verified,
                        sitemap_url_count=len(sitemap_parsed_urls),
                    )
                    updated += 1
                else:
                    record_log.debug(
                        "No change",
                        crawlable=result.crawlable,
                        sitemap_urls=len(sitemap_parsed_urls),
                    )

            except Exception as e:
                record_log.error("Failed to check", error=str(e))
                record["crawlable"] = False
                record["blocked_reason"] = "check_failed"
                record["status"] = "protected"
                record["robots_fetched_at"] = now
                errors += 1

            # Progress report
            if (i + 1) % 25 == 0:
                log.info("Progress", processed=i + 1, updated=updated, skipped=skipped, errors=errors)

    log.info("Recheck complete", updated=updated, skipped=skipped, errors=errors)
    return records


async def main():
    parser = argparse.ArgumentParser(description="Re-check robots.txt and sitemaps for enriched DNOs")
    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=Path(__file__).parent.parent.parent / "data" / "seed-data" / "dnos_enriched.json",
        help="Input JSON file path",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="Output JSON file path (defaults to input file - in-place update)",
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=None,
        help="Limit number of records to process",
    )
    parser.add_argument(
        "--delay", "-d",
        type=float,
        default=0.5,
        help="Delay between requests in seconds (default: 0.5)",
    )

    args = parser.parse_args()
    output_path = args.output or args.input

    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}")
        return 1

    print(f"Reading from: {args.input}")
    print(f"Writing to: {output_path}")
    print(f"Delay between requests: {args.delay}s")

    with open(args.input, encoding="utf-8") as f:
        records = json.load(f)

    print(f"Loaded {len(records)} records")

    if args.limit:
        print(f"Limiting to {args.limit} records")

    # Estimate time
    num_with_website = sum(1 for r in records if r.get("website"))
    num_to_check = min(num_with_website, args.limit) if args.limit else num_with_website
    est_time = num_to_check * args.delay * 1.5  # 1.5x for sitemap fetches
    print(f"Found {num_with_website} records with websites")
    print(f"Estimated time: ~{est_time / 60:.1f} minutes")

    updated_records = await recheck_robots_for_all(
        records,
        delay=args.delay,
        limit=args.limit,
    )

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(updated_records, f, ensure_ascii=False, indent=2)

    print(f"\nOutput written to: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
