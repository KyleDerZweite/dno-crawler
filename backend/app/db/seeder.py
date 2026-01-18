"""
Database seeder for DNO data.

Loads seed data from dnos_enriched.parquet and upserts into the database
using the hub-and-spoke model structure.

This runs on application/worker startup.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import DNOModel
from app.db.source_models import DNOBdewData, DNOMastrData, DNOVnbData

logger = structlog.get_logger()

# Path to seed data (relative to backend root)
SEED_DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "seed-data"
SEED_PARQUET_PATH = SEED_DATA_DIR / "dnos_enriched.parquet"


def parse_date(date_str: str | None) -> datetime | None:
    """Parse ISO date string to datetime."""
    if not date_str:
        return None
    try:
        # Handle both date-only and datetime strings
        if 'T' in date_str:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return datetime.fromisoformat(date_str)
    except ValueError:
        return None


def load_seed_data() -> list[dict[str, Any]] | None:
    """Load seed data from parquet file.

    Returns:
        List of record dicts, or None if file doesn't exist.
    """
    import math

    if not SEED_PARQUET_PATH.exists():
        return None

    df = pd.read_parquet(SEED_PARQUET_PATH)
    # Convert DataFrame to list of dicts
    records = df.to_dict('records')

    # Clean up values: convert numpy types to Python types
    for record in records:
        for key, value in list(record.items()):
            # Convert numpy arrays to lists
            if hasattr(value, 'tolist'):
                record[key] = value.tolist()
            # Convert NaN/NaT to None
            elif value is None:
                pass
            elif isinstance(value, float) and math.isnan(value):
                record[key] = None
            elif pd.isna(value):
                record[key] = None

    return records


async def seed_dnos(db: AsyncSession) -> tuple[int, int, int]:
    """
    Seed DNOs from parquet seed data.

    Creates/updates:
    - DNOModel (core hub)
    - DNOMastrData (MaStR source data)
    - DNOVnbData (VNB Digital data, if enriched)
    - DNOBdewData (BDEW data, if enriched)

    Returns:
        Tuple of (inserted, updated, skipped).
    """
    seed_data = load_seed_data()
    if not seed_data:
        logger.warning("No seed data file found", path=str(SEED_PARQUET_PATH))
        return 0, 0, 0

    logger.info("Loading seed data", path=str(SEED_PARQUET_PATH), count=len(seed_data))

    inserted = 0
    updated = 0
    skipped = 0

    for record in seed_data:
        mastr_nr = record.get('mastr_nr')
        if not mastr_nr:
            logger.warning("Skipping record without mastr_nr", name=record.get('name'))
            skipped += 1
            continue

        try:
            result = await upsert_dno_from_seed(db, record)
            if result == 'inserted':
                inserted += 1
            elif result == 'updated':
                updated += 1
            else:
                skipped += 1
        except Exception as e:
            logger.error("Error seeding DNO", mastr_nr=mastr_nr, error=str(e))
            skipped += 1

    # Commit after processing all records
    await db.commit()

    logger.info(
        "Seeding complete",
        inserted=inserted,
        updated=updated,
        skipped=skipped,
        total=len(seed_data),
    )

    return inserted, updated, skipped


async def upsert_dno_from_seed(db: AsyncSession, record: dict[str, Any]) -> str:
    """
    Upsert a single DNO and its source data from seed record.

    Returns: 'inserted', 'updated', or 'skipped'
    """
    mastr_nr = record['mastr_nr']

    # Check if DNO already exists by mastr_nr (eagerly load mastr_data to avoid lazy load in async)
    result = await db.execute(
        select(DNOModel)
        .options(selectinload(DNOModel.mastr_data))
        .where(DNOModel.mastr_nr == mastr_nr)
    )
    existing_dno = result.scalar_one_or_none()

    if existing_dno:
        # Check if we should update (only if source data is newer or missing)
        if existing_dno.mastr_data:
            # Skip if already has MaStR data (don't overwrite)
            logger.debug("Skipping existing DNO with MaStR data", mastr_nr=mastr_nr)
            return 'skipped'

        dno = existing_dno
        action = 'updated'
    else:
        # Create new DNO
        dno = DNOModel(
            slug=record['slug'],
            name=record['name'],
            mastr_nr=mastr_nr,
            source='seed',
            status='uncrawled',
            is_active=record.get('is_active', True),
        )
        db.add(dno)
        await db.flush()  # Get the ID
        action = 'inserted'

    # Update core fields (resolved values)
    dno.name = record['name']
    dno.slug = record['slug']
    dno.region = record.get('region')
    dno.is_active = record.get('is_active', True)

    # Create/update MaStR source data
    await upsert_mastr_data(db, dno, record)

    # Create VNB data if present in enriched record
    if record.get('vnb_id'):
        await upsert_vnb_data(db, dno, record)
        # Update resolved fields from VNB
        dno.vnb_id = record['vnb_id']
        dno.website = record.get('website') or dno.website
        dno.phone = record.get('phone') or dno.phone
        dno.email = record.get('email') or dno.email
        # Mark as enriched
        dno.enrichment_status = 'completed'
        dno.last_enriched_at = datetime.now(UTC)
    else:
        # No VNB data present – mark as pending enrichment
        dno.enrichment_status = 'pending'
        dno.last_enriched_at = None

    # Seed robots/crawlability data if present
    if record.get('status'):
        dno.status = record['status']
    if record.get('crawlable') is not None:
        dno.crawlable = record['crawlable']
    if record.get('blocked_reason'):
        dno.crawl_blocked_reason = record['blocked_reason']
    if record.get('robots_txt'):
        dno.robots_txt = record['robots_txt']
    if record.get('robots_fetched_at'):
        dno.robots_fetched_at = parse_date(record['robots_fetched_at'])
    if record.get('sitemap_urls'):
        dno.sitemap_urls = record['sitemap_urls']
    if record.get('sitemap_parsed_urls'):
        dno.sitemap_parsed_urls = record['sitemap_parsed_urls']
    if record.get('sitemap_fetched_at'):
        dno.sitemap_fetched_at = parse_date(record['sitemap_fetched_at'])
    if record.get('disallow_paths'):
        dno.disallow_paths = record['disallow_paths']

    # Create BDEW data if present in enriched record
    if record.get('bdew_code'):
        await upsert_bdew_data(db, dno, record)
        # Update primary BDEW code on core (convert to string)
        dno.primary_bdew_code = str(int(record['bdew_code']))

    logger.debug(f"{action.capitalize()} DNO from seed", mastr_nr=mastr_nr, name=record['name'])
    return action


async def upsert_mastr_data(db: AsyncSession, dno: DNOModel, record: dict[str, Any]) -> None:
    """Create or update MaStR source data for a DNO."""

    # Check if MaStR data already exists via explicit query (avoids lazy loading)
    result = await db.execute(
        select(DNOMastrData).where(DNOMastrData.dno_id == dno.id)
    )
    mastr = result.scalar_one_or_none()

    if mastr is None:
        mastr = DNOMastrData(dno_id=dno.id)
        db.add(mastr)

    # Update fields
    mastr.mastr_nr = record['mastr_nr']
    mastr.registered_name = record['name']
    mastr.acer_code = record.get('acer_code')
    mastr.region = record.get('region')
    mastr.address_components = record.get('address_components')
    mastr.contact_address = record.get('contact_address')
    mastr.marktrollen = record.get('marktrollen')
    mastr.is_active = record.get('is_active', True)
    mastr.closed_network = record.get('closed_network', False)
    mastr.registration_date = parse_date(record.get('registration_date'))
    mastr.mastr_last_updated = parse_date(record.get('last_updated'))
    mastr.activity_start = parse_date(record.get('activity_start'))
    mastr.activity_end = parse_date(record.get('activity_end'))
    mastr.last_synced_at = datetime.now(UTC)


async def upsert_vnb_data(db: AsyncSession, dno: DNOModel, record: dict[str, Any]) -> None:
    """Create or update VNB Digital source data for a DNO."""

    vnb_id = record.get('vnb_id')
    if not vnb_id:
        return

    # Check if VNB data already exists via explicit query (avoids lazy loading)
    result = await db.execute(
        select(DNOVnbData).where(DNOVnbData.dno_id == dno.id)
    )
    vnb = result.scalar_one_or_none()

    if vnb is None:
        vnb = DNOVnbData(dno_id=dno.id, vnb_id=str(vnb_id), name=record['name'])
        db.add(vnb)

    # Update fields
    vnb.vnb_id = str(vnb_id)
    vnb.name = record['name']
    vnb.homepage_url = record.get('website')
    vnb.phone = record.get('phone')
    vnb.email = record.get('email')
    vnb.last_synced_at = datetime.now(UTC)


async def upsert_bdew_data(db: AsyncSession, dno: DNOModel, record: dict[str, Any]) -> None:
    """Create or update BDEW source data for a DNO."""

    bdew_code = record.get('bdew_code')
    if not bdew_code:
        return

    # Convert to string (parquet stores as int, DB expects string)
    bdew_code = str(int(bdew_code))

    # Check if this BDEW code already exists
    result = await db.execute(
        select(DNOBdewData).where(DNOBdewData.bdew_code == bdew_code)
    )
    existing_bdew = result.scalar_one_or_none()

    if existing_bdew:
        bdew = existing_bdew
    else:
        bdew = DNOBdewData(
            dno_id=dno.id,
            bdew_code=bdew_code,
            company_name=record['name'],
        )
        db.add(bdew)

    # Update fields
    bdew.bdew_internal_id = record.get('bdew_internal_id', 0)
    bdew.bdew_company_uid = record.get('bdew_company_uid', 0)
    bdew.company_name = record['name']
    bdew.market_function = record.get('bdew_market_function')
    bdew.last_synced_at = datetime.now(UTC)


async def get_dnos_needing_enrichment(
    db: AsyncSession,
    source: str | None = None,
    limit: int | None = None,
) -> list[DNOModel]:
    """
    Get DNOs that need enrichment from a specific source.

    Args:
        db: Database session
        source: 'vnb', 'bdew', or None for any
        limit: Maximum number of DNOs to return

    Returns:
        List of DNOModel instances needing enrichment.
    """
    query = select(DNOModel)

    if source == 'vnb':
        # DNOs without VNB data
        query = query.outerjoin(DNOVnbData).where(DNOVnbData.id.is_(None))
    elif source == 'bdew':
        # DNOs without BDEW data
        query = query.outerjoin(DNOBdewData).where(DNOBdewData.id.is_(None))

    query = query.order_by(DNOModel.id)

    if limit:
        query = query.limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())


async def get_dno_enrichment_stats(db: AsyncSession) -> dict[str, int]:
    """Get statistics on DNO enrichment status."""

    # Total DNOs
    total_result = await db.execute(select(DNOModel.id))
    total = len(list(total_result.scalars().all()))

    # With MaStR data
    mastr_result = await db.execute(
        select(DNOModel.id).join(DNOMastrData)
    )
    with_mastr = len(list(mastr_result.scalars().all()))

    # With VNB data
    vnb_result = await db.execute(
        select(DNOModel.id).join(DNOVnbData)
    )
    with_vnb = len(list(vnb_result.scalars().all()))

    # With BDEW data
    bdew_result = await db.execute(
        select(DNOModel.id).join(DNOBdewData)
    )
    with_bdew = len(list(bdew_result.scalars().all()))

    return {
        'total': total,
        'with_mastr': with_mastr,
        'with_vnb': with_vnb,
        'with_bdew': with_bdew,
        'missing_vnb': total - with_vnb,
        'missing_bdew': total - with_bdew,
    }
