#!/usr/bin/env python3
"""
Temporary script to re-check robots.txt for all DNOs in the enriched JSON file.

Only updates crawlable and blocked_reason fields - does NOT re-run VNB/BDEW enrichment.

Usage:
    python scripts/recheck_robots.py [--limit LIMIT] [--delay DELAY]
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
import structlog

from app.services.robots_parser import fetch_robots_txt

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(colors=True),
    ]
)
logger = structlog.get_logger()


async def recheck_robots_for_all(
    records: list[dict],
    delay: float = 0.5,
    limit: int | None = None,
) -> list[dict]:
    """
    Re-check robots.txt for all records with a website.
    
    Only updates crawlable and blocked_reason fields.
    """
    log = logger.bind(total=len(records), limit=limit)
    log.info("Starting robots.txt recheck")
    
    records_to_process = records[:limit] if limit else records
    updated = 0
    skipped = 0
    errors = 0
    
    async with httpx.AsyncClient(
        headers={"User-Agent": "DNO-Crawler/1.0 (robots check)"},
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
                
                result = await fetch_robots_txt(client, website, timeout=15.0)
                
                old_crawlable = record.get("crawlable", True)
                old_reason = record.get("blocked_reason")
                
                # Update record
                record["crawlable"] = result.crawlable
                record["blocked_reason"] = result.blocked_reason
                
                if old_crawlable != result.crawlable or old_reason != result.blocked_reason:
                    record_log.info(
                        "Updated crawlability",
                        old_crawlable=old_crawlable,
                        new_crawlable=result.crawlable,
                        old_reason=old_reason,
                        new_reason=result.blocked_reason,
                    )
                    updated += 1
                else:
                    record_log.debug("No change", crawlable=result.crawlable)
                
            except Exception as e:
                record_log.error("Failed to check", error=str(e))
                record["crawlable"] = False
                record["blocked_reason"] = "check_failed"
                errors += 1
            
            # Progress report
            if (i + 1) % 25 == 0:
                log.info("Progress", processed=i + 1, updated=updated, skipped=skipped, errors=errors)
    
    log.info("Recheck complete", updated=updated, skipped=skipped, errors=errors)
    return records


async def main():
    parser = argparse.ArgumentParser(description="Re-check robots.txt for enriched DNOs")
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
    
    with open(args.input, "r", encoding="utf-8") as f:
        records = json.load(f)
    
    print(f"Loaded {len(records)} records")
    
    if args.limit:
        print(f"Limiting to {args.limit} records")
    
    # Estimate time
    num_with_website = sum(1 for r in records if r.get("website"))
    num_to_check = min(num_with_website, args.limit) if args.limit else num_with_website
    est_time = num_to_check * args.delay
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
    exit(asyncio.run(main()))
