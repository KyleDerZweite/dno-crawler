#!/usr/bin/env python3
"""
Enrich DNO Seed Data.

This script enriches the dnos_seed.json with additional data from:
1. VNB Digital API - website, phone, email, contact address
2. BDEW Codes API - BDEW code, internal IDs, market function

Supports two modes:
1. JSON mode (default): Outputs enriched data to dnos_enriched.json
2. Database mode (--db): Writes directly to database source tables

Usage:
    # JSON output mode
    python enrich_seed_data.py [--input INPUT] [--output OUTPUT] [--limit LIMIT]
    
    # Database mode (requires running PostgreSQL)
    python enrich_seed_data.py --db [--limit LIMIT]

The script uses politeness delays to respect API constraints:
- VNB Digital: 1.0s base delay with jitter
- BDEW: 0.3s base delay with jitter
"""

import argparse
import asyncio
import json
import random
import sys
from datetime import UTC, datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog

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


# =============================================================================
# VNB Digital Enrichment
# =============================================================================

async def enrich_with_vnb_digital(client, record: dict, log) -> dict:
    """
    Enrich a single record with VNB Digital data.
    
    Returns dict with enriched fields (may be empty).
    """

    enriched = {}
    name = record.get("name", "")

    try:
        vnb_results = await client.search_vnb(name)

        if not vnb_results:
            log.debug("No VNB results for name search", name=name)
            return enriched

        vnb = vnb_results[0]

        # Politeness delay before detail fetch
        await politeness_delay(0.5)

        details = await client.get_vnb_details(vnb.vnb_id)

        if details:
            enriched["vnb_id"] = vnb.vnb_id
            enriched["vnb_name"] = details.name
            if details.homepage_url:
                enriched["website"] = details.homepage_url
            if details.phone:
                enriched["phone"] = details.phone
            if details.email:
                enriched["email"] = details.email
            if details.address:
                enriched["vnb_address"] = details.address

            log.debug(
                "VNB Digital enrichment successful",
                vnb_id=vnb.vnb_id,
                website=details.homepage_url,
            )

    except Exception as e:
        log.warning("VNB Digital enrichment failed", error=str(e), name=name)

    return enriched


# =============================================================================
# BDEW Enrichment
# =============================================================================

async def enrich_with_bdew(client, record: dict, log) -> dict:
    """
    Enrich a single record with BDEW data.
    
    Returns dict with bdew_code, bdew_internal_id, bdew_company_uid if found.
    """
    enriched = {}
    name = record.get("name", "")

    try:
        result = await client.get_bdew_record_for_name(name)

        if result:
            enriched["bdew_code"] = result.bdew_code
            enriched["bdew_internal_id"] = result.bdew_internal_id
            enriched["bdew_company_uid"] = result.bdew_company_uid
            enriched["bdew_company_name"] = result.company_name
            if result.market_function:
                enriched["bdew_market_function"] = result.market_function
            if result.contact_name:
                enriched["bdew_contact_name"] = result.contact_name
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


# =============================================================================
# JSON Mode - Enrich and output to JSON file
# =============================================================================

async def enrich_all_records_json(
    records: list[dict],
    limit: int | None = None,
    skip_vnb: bool = False,
    skip_bdew: bool = False,
    vnb_delay: float = 1.0,
    bdew_delay: float = 0.3,
) -> list[dict]:
    """
    Enrich all records and return as list (for JSON output).
    """
    from app.services.bdew_client import BDEWClient

    log = logger.bind(total=len(records), limit=limit)
    log.info("Starting enrichment (JSON mode)")

    vnb_client = VNBDigitalClient(request_delay=vnb_delay)
    bdew_client = BDEWClient(request_delay=bdew_delay)

    if not skip_bdew:
        log.info("Fetching BDEW company list...")
        companies = await bdew_client.fetch_company_list()
        log.info("BDEW company list loaded", count=len(companies))

    enriched_records = []
    records_to_process = records[:limit] if limit else records

    stats = {"total": len(records_to_process), "vnb_enriched": 0, "bdew_enriched": 0,
             "both_enriched": 0, "none_enriched": 0, "errors": 0}

    for i, record in enumerate(records_to_process):
        record_log = log.bind(index=i + 1, name=record.get("name", "")[:40])

        enriched = record.copy()
        vnb_data = {}
        bdew_data = {}

        if not skip_vnb:
            try:
                if i > 0:
                    await politeness_delay(vnb_delay)
                vnb_data = await enrich_with_vnb_digital(vnb_client, record, record_log)
                enriched.update(vnb_data)
            except Exception as e:
                record_log.error("VNB enrichment error", error=str(e))
                stats["errors"] += 1

        if not skip_bdew:
            try:
                await politeness_delay(bdew_delay)
                bdew_data = await enrich_with_bdew(bdew_client, record, record_log)
                enriched.update(bdew_data)
            except Exception as e:
                record_log.error("BDEW enrichment error", error=str(e))
                stats["errors"] += 1

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

        enriched["enriched_at"] = datetime.now(UTC).isoformat()
        enriched_records.append(enriched)

        if (i + 1) % 25 == 0:
            log.info("Progress", processed=i + 1, vnb=stats["vnb_enriched"] + stats["both_enriched"],
                     bdew=stats["bdew_enriched"] + stats["both_enriched"], errors=stats["errors"])

    log.info("Enrichment complete", **stats)
    return enriched_records


# =============================================================================
# Database Mode - Enrich and write to source tables
# =============================================================================

async def enrich_dnos_database(
    limit: int | None = None,
    skip_vnb: bool = False,
    skip_bdew: bool = False,
    vnb_delay: float = 1.0,
    bdew_delay: float = 0.3,
) -> dict[str, int]:
    """
    Enrich DNOs directly in database by populating source tables.
    
    Fetches DNOs missing VNB/BDEW data and creates source records.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.db.database import async_session_maker
    from app.db.models import DNOModel
    from app.db.source_models import DNOBdewData, DNOVnbData
    from app.services.bdew_client import BDEWClient

    log = logger.bind(limit=limit)
    log.info("Starting enrichment (Database mode)")

    vnb_client = VNBDigitalClient(request_delay=vnb_delay)
    bdew_client = BDEWClient(request_delay=bdew_delay)

    # Pre-fetch BDEW company list
    if not skip_bdew:
        log.info("Fetching BDEW company list...")
        companies = await bdew_client.fetch_company_list()
        log.info("BDEW company list loaded", count=len(companies))

    stats = {"total": 0, "vnb_enriched": 0, "bdew_enriched": 0, "errors": 0}

    async with async_session_maker() as db:
        # Get DNOs that need enrichment (missing source data)
        query = (
            select(DNOModel)
            .options(
                selectinload(DNOModel.vnb_data),
                selectinload(DNOModel.bdew_data),
            )
            .order_by(DNOModel.id)
        )

        if limit:
            query = query.limit(limit)

        result = await db.execute(query)
        dnos = list(result.scalars().all())
        stats["total"] = len(dnos)
        log.info("Found DNOs to process", count=len(dnos))

        for i, dno in enumerate(dnos):
            dno_log = log.bind(index=i + 1, dno_id=dno.id, name=dno.name[:40])

            # Enrich with VNB if missing
            if not skip_vnb and not dno.vnb_data:
                try:
                    if i > 0:
                        await politeness_delay(vnb_delay)

                    vnb_data = await enrich_with_vnb_digital(
                        vnb_client, {"name": dno.name}, dno_log
                    )

                    if vnb_data.get("vnb_id"):
                        # Create VNB source record
                        vnb_record = DNOVnbData(
                            dno_id=dno.id,
                            vnb_id=str(vnb_data["vnb_id"]),
                            name=vnb_data.get("vnb_name", dno.name),
                            homepage_url=vnb_data.get("website"),
                            phone=vnb_data.get("phone"),
                            email=vnb_data.get("email"),
                            address=vnb_data.get("vnb_address"),
                            last_synced_at=datetime.now(UTC),
                        )
                        db.add(vnb_record)

                        # Update resolved fields on core DNO
                        dno.vnb_id = str(vnb_data["vnb_id"])
                        if vnb_data.get("website"):
                            dno.website = vnb_data["website"]
                        if vnb_data.get("phone"):
                            dno.phone = vnb_data["phone"]
                        if vnb_data.get("email"):
                            dno.email = vnb_data["email"]

                        stats["vnb_enriched"] += 1
                        dno_log.debug("Created VNB source record", vnb_id=vnb_data["vnb_id"])

                except Exception as e:
                    dno_log.error("VNB enrichment error", error=str(e))
                    stats["errors"] += 1

            # Enrich with BDEW if missing
            if not skip_bdew and not dno.bdew_data:
                try:
                    await politeness_delay(bdew_delay)

                    bdew_data = await enrich_with_bdew(
                        bdew_client, {"name": dno.name}, dno_log
                    )

                    if bdew_data.get("bdew_code"):
                        # Create BDEW source record
                        bdew_record = DNOBdewData(
                            dno_id=dno.id,
                            bdew_code=bdew_data["bdew_code"],
                            bdew_internal_id=bdew_data.get("bdew_internal_id", 0),
                            bdew_company_uid=bdew_data.get("bdew_company_uid", 0),
                            company_name=bdew_data.get("bdew_company_name", dno.name),
                            market_function=bdew_data.get("bdew_market_function"),
                            contact_name=bdew_data.get("bdew_contact_name"),
                            last_synced_at=datetime.now(UTC),
                        )
                        db.add(bdew_record)

                        # Update primary BDEW code on core DNO
                        dno.primary_bdew_code = bdew_data["bdew_code"]

                        stats["bdew_enriched"] += 1
                        dno_log.debug("Created BDEW source record", bdew_code=bdew_data["bdew_code"])

                except Exception as e:
                    dno_log.error("BDEW enrichment error", error=str(e))
                    stats["errors"] += 1

            # Commit every 25 records
            if (i + 1) % 25 == 0:
                await db.commit()
                log.info("Progress", processed=i + 1, vnb=stats["vnb_enriched"],
                         bdew=stats["bdew_enriched"], errors=stats["errors"])

        # Final commit
        await db.commit()

    log.info("Database enrichment complete", **stats)
    return stats


# =============================================================================
# Main
# =============================================================================

async def main():
    parser = argparse.ArgumentParser(
        description="Enrich DNO seed data with VNB Digital and BDEW data"
    )
    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=Path(__file__).parent.parent.parent / "data" / "seed-data" / "dnos_seed.json",
        help="Input JSON file path (JSON mode only)"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path(__file__).parent.parent.parent / "data" / "seed-data" / "dnos_enriched.json",
        help="Output JSON file path (JSON mode only)"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=None,
        help="Limit number of records to process (for testing)"
    )
    parser.add_argument(
        "--db",
        action="store_true",
        help="Database mode: write directly to source tables instead of JSON"
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

    print(f"Mode: {'Database' if args.db else 'JSON'}")
    print(f"Politeness delays: VNB={args.vnb_delay}s, BDEW={args.bdew_delay}s")

    if args.db:
        # Database mode
        stats = await enrich_dnos_database(
            limit=args.limit,
            skip_vnb=args.skip_vnb,
            skip_bdew=args.skip_bdew,
            vnb_delay=args.vnb_delay,
            bdew_delay=args.bdew_delay,
        )
        print(f"\nEnrichment complete: {stats}")
    else:
        # JSON mode
        if not args.input.exists():
            print(f"Error: Input file not found: {args.input}")
            return 1

        print(f"Reading from: {args.input}")
        print(f"Writing to: {args.output}")

        with open(args.input, encoding="utf-8") as f:
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

        enriched = await enrich_all_records_json(
            records,
            limit=args.limit,
            skip_vnb=args.skip_vnb,
            skip_bdew=args.skip_bdew,
            vnb_delay=args.vnb_delay,
            bdew_delay=args.bdew_delay,
        )

        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(enriched, f, ensure_ascii=False, indent=2)

        print(f"\nSuccessfully enriched {len(enriched)} records")
        print(f"Output written to: {args.output}")

    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
