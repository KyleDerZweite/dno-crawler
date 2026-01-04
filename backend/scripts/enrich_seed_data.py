#!/usr/bin/env python3
"""
Enrich DNO Seed Data.

This script enriches the dnos_seed.json with additional data from:
1. VNB Digital API - website, phone, email, contact address
2. BDEW Codes API - BDEW code, internal IDs, market function

Usage:
    python enrich_seed_data.py [--input INPUT] [--output OUTPUT] [--limit LIMIT]

The script uses politeness delays to respect API constraints:
- VNB Digital: 1.0s base delay with jitter
- BDEW: 0.3s base delay with jitter

Output: dnos_enriched.json with additional fields:
- website: Company website URL
- vnb_id: VNB Digital ID
- phone: Contact phone
- email: Contact email
- bdew_code: 13-digit BDEW code
- bdew_internal_id: BDEW internal ID
- bdew_company_uid: BDEW Company UID
- enrichment_source: "vnb_digital" | "bdew" | "both" | null
"""

import argparse
import asyncio
import json
import random
import sys
from datetime import datetime, UTC
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog
from app.services.bdew_client import BDEWClient
from app.services.vnb import VNBDigitalClient

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(colors=True),
    ]
)
logger = structlog.get_logger()


async def politeness_delay(base_delay: float, min_jitter: float = 0.5, max_jitter: float = 1.5):
    """
    Apply a politeness delay with jitter.
    
    Args:
        base_delay: Base delay in seconds
        min_jitter: Minimum jitter multiplier (e.g., 0.5 = 50% of base)
        max_jitter: Maximum jitter multiplier (e.g., 1.5 = 150% of base)
    """
    jitter = random.uniform(min_jitter, max_jitter)
    delay = max(0.3, base_delay * jitter)  # Minimum 300ms
    await asyncio.sleep(delay)


async def enrich_with_vnb_digital(
    client: VNBDigitalClient,
    record: dict,
    log,
) -> dict:
    """
    Enrich a single record with VNB Digital data.
    
    Returns dict with enriched fields (may be empty).
    """
    enriched = {}
    name = record.get("name", "")
    
    try:
        # First try searching by name
        vnb_results = await client.search_vnb(name)
        
        if not vnb_results:
            log.debug("No VNB results for name search", name=name)
            return enriched
        
        # Find best match (first result is usually best)
        vnb = vnb_results[0]
        
        # Politeness delay before detail fetch
        await politeness_delay(0.5)
        
        # Get detailed info
        details = await client.get_vnb_details(vnb.vnb_id)
        
        if details:
            enriched["vnb_id"] = vnb.vnb_id
            if details.homepage_url:
                enriched["website"] = details.homepage_url
            if details.phone:
                enriched["phone"] = details.phone
            if details.email:
                enriched["email"] = details.email
            
            log.debug(
                "VNB Digital enrichment successful",
                vnb_id=vnb.vnb_id,
                website=details.homepage_url,
            )
        
    except Exception as e:
        log.warning("VNB Digital enrichment failed", error=str(e), name=name)
    
    return enriched


async def enrich_with_bdew(
    client: BDEWClient,
    record: dict,
    log,
) -> dict:
    """
    Enrich a single record with BDEW data.
    
    Uses on-demand lookup to fetch BDEW code and all identifiers.
    
    Returns dict with bdew_code, bdew_internal_id, bdew_company_uid if found.
    """
    enriched = {}
    name = record.get("name", "")
    
    try:
        # Use the new get_bdew_record_for_name for full data
        result = await client.get_bdew_record_for_name(name)
        
        if result:
            enriched["bdew_code"] = result.bdew_code
            enriched["bdew_internal_id"] = result.bdew_internal_id
            enriched["bdew_company_uid"] = result.bdew_company_uid
            if result.market_function:
                enriched["bdew_market_function"] = result.market_function
            log.debug(
                "BDEW enrichment successful",
                name=name,
                bdew_code=result.bdew_code,
                market_function=result.market_function,
            )
        else:
            log.debug("BDEW code not found", name=name)
    
    except Exception as e:
        log.warning("BDEW enrichment failed", error=str(e), name=name)
    
    return enriched


async def enrich_all_records(
    records: list[dict],
    limit: int | None = None,
    skip_vnb: bool = False,
    skip_bdew: bool = False,
    vnb_delay: float = 1.0,
    bdew_delay: float = 0.3,
) -> list[dict]:
    """
    Enrich all records with VNB Digital and BDEW data.
    
    Args:
        records: List of seed records
        limit: Optional limit for testing
        skip_vnb: Skip VNB Digital enrichment
        skip_bdew: Skip BDEW enrichment
        vnb_delay: Base delay between VNB requests (seconds)
        bdew_delay: Base delay between BDEW requests (seconds)
    
    Returns:
        List of enriched records
    """
    log = logger.bind(total=len(records), limit=limit)
    log.info("Starting enrichment")
    
    # Initialize clients
    vnb_client = VNBDigitalClient(request_delay=vnb_delay)
    bdew_client = BDEWClient(request_delay=bdew_delay)
    
    # Pre-fetch BDEW company list (needed for name lookups)
    if not skip_bdew:
        log.info("Fetching BDEW company list...")
        companies = await bdew_client.fetch_company_list()
        log.info("BDEW company list loaded", count=len(companies))
    
    # Process records
    enriched_records = []
    records_to_process = records[:limit] if limit else records
    
    stats = {
        "total": len(records_to_process),
        "vnb_enriched": 0,
        "bdew_enriched": 0,
        "both_enriched": 0,
        "none_enriched": 0,
        "errors": 0,
    }
    
    for i, record in enumerate(records_to_process):
        record_log = log.bind(
            index=i + 1,
            name=record.get("name", "")[:40],
        )
        
        # Create copy for enrichment
        enriched = record.copy()
        vnb_data = {}
        bdew_data = {}
        
        # VNB Digital enrichment
        if not skip_vnb:
            try:
                # Politeness delay before request
                if i > 0:
                    await politeness_delay(vnb_delay)
                
                vnb_data = await enrich_with_vnb_digital(vnb_client, record, record_log)
                enriched.update(vnb_data)
            except Exception as e:
                record_log.error("VNB enrichment error", error=str(e))
                stats["errors"] += 1
        
        # BDEW enrichment (on-demand lookup)
        if not skip_bdew:
            try:
                # Politeness delay before BDEW detail fetch
                await politeness_delay(bdew_delay)
                
                bdew_data = await enrich_with_bdew(bdew_client, record, record_log)
                enriched.update(bdew_data)
            except Exception as e:
                record_log.error("BDEW enrichment error", error=str(e))
                stats["errors"] += 1
        
        # Track enrichment source
        has_vnb = bool(vnb_data)
        has_bdew = bool(bdew_data)
        
        if has_vnb and has_bdew:
            enriched["enrichment_source"] = "both"
            stats["both_enriched"] += 1
        elif has_vnb:
            enriched["enrichment_source"] = "vnb_digital"
            stats["vnb_enriched"] += 1
        elif has_bdew:
            enriched["enrichment_source"] = "bdew"
            stats["bdew_enriched"] += 1
        else:
            enriched["enrichment_source"] = None
            stats["none_enriched"] += 1
        
        # Add enrichment timestamp
        enriched["enriched_at"] = datetime.now(UTC).isoformat()
        
        enriched_records.append(enriched)
        
        # Progress logging every 25 records
        if (i + 1) % 25 == 0:
            log.info(
                "Progress",
                processed=i + 1,
                vnb=stats["vnb_enriched"] + stats["both_enriched"],
                bdew=stats["bdew_enriched"] + stats["both_enriched"],
                errors=stats["errors"],
            )
    
    log.info("Enrichment complete", **stats)
    return enriched_records


async def main():
    parser = argparse.ArgumentParser(
        description="Enrich DNO seed data with VNB Digital and BDEW data"
    )
    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=Path(__file__).parent.parent.parent / "data" / "seed-data" / "dnos_seed.json",
        help="Input JSON file path"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path(__file__).parent.parent.parent / "data" / "seed-data" / "dnos_enriched.json",
        help="Output JSON file path"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=None,
        help="Limit number of records to process (for testing)"
    )
    parser.add_argument(
        "--skip-vnb",
        action="store_true",
        help="Skip VNB Digital enrichment"
    )
    parser.add_argument(
        "--skip-bdew",
        action="store_true",
        help="Skip BDEW enrichment"
    )
    parser.add_argument(
        "--vnb-delay",
        type=float,
        default=1.0,
        help="Base delay between VNB requests in seconds (default: 1.0)"
    )
    parser.add_argument(
        "--bdew-delay",
        type=float,
        default=0.3,
        help="Base delay between BDEW requests in seconds (default: 0.3)"
    )
    
    args = parser.parse_args()
    
    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}")
        return 1
    
    print(f"Reading from: {args.input}")
    print(f"Writing to: {args.output}")
    print(f"Politeness delays: VNB={args.vnb_delay}s, BDEW={args.bdew_delay}s")
    
    # Load seed data
    with open(args.input, "r", encoding="utf-8") as f:
        records = json.load(f)
    
    print(f"Loaded {len(records)} records")
    
    if args.limit:
        print(f"Limiting to {args.limit} records")
    
    # Estimate time
    num_records = min(len(records), args.limit) if args.limit else len(records)
    est_time_vnb = num_records * args.vnb_delay * 1.5 if not args.skip_vnb else 0
    est_time_bdew = num_records * args.bdew_delay * 1.5 if not args.skip_bdew else 0
    est_total = est_time_vnb + est_time_bdew
    print(f"Estimated time: ~{est_total / 60:.1f} minutes")
    
    # Enrich
    enriched = await enrich_all_records(
        records,
        limit=args.limit,
        skip_vnb=args.skip_vnb,
        skip_bdew=args.skip_bdew,
        vnb_delay=args.vnb_delay,
        bdew_delay=args.bdew_delay,
    )
    
    # Write output
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)
    
    print(f"\nSuccessfully enriched {len(enriched)} records")
    print(f"Output written to: {args.output}")
    
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
