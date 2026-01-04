"""
Database seeder for DNO data.

Loads seed data from dnos_seed.json (or dnos_enriched.json if available)
and upserts into the database using the hub-and-spoke model structure.

This runs on application/worker startup.
"""

import json
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DNOModel
from app.db.source_models import DNOMastrData, DNOVnbData, DNOBdewData

logger = structlog.get_logger()

# Path to seed data (relative to backend root)
SEED_DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "seed-data"
ENRICHED_DATA_PATH = SEED_DATA_DIR / "dnos_enriched.json"
BASE_SEED_PATH = SEED_DATA_DIR / "dnos_seed.json"


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


def transform_csv_to_seed(csv_path: Path, out_path: Path) -> Path:
    """Transform CSV (OeffentlicheMarktakteure.csv) into base seed JSON.

    Extracts basic fields required for seeding: mastr_nr, name, slug, region, is_active
    and writes them to `out_path` as a JSON array.
    """
    import csv
    from app.services.vnb.skeleton import generate_slug

    records = []
    with csv_path.open(newline='', encoding='utf-8') as fh:
        # CSV uses semicolon delimiter and quoted fields
        reader = csv.DictReader(fh, delimiter=';')
        for row in reader:
            mastr_nr = (row.get('MaStR-Nr.') or row.get('MaStR-Nr') or '').strip()
            name = (row.get('Name des Marktakteurs') or row.get('Name') or '').strip()
            region = (row.get('Bundesland') or '').strip()
            zip_code = (row.get('Postleitzahl') or row.get('PLZ') or '').strip()
            city = (row.get('Ort') or '').strip()
            street = (row.get('Straße') or '').strip()
            house = (row.get('Hausnummer') or '').strip()

            if not mastr_nr or not name:
                continue

            record = {
                'mastr_nr': mastr_nr,
                'slug': generate_slug(name),
                'name': name,
                'region': region or None,
                'address_components': {
                    'street': street or None,
                    'house_number': house or None,
                    'zip_code': zip_code or None,
                    'city': city or None,
                },
                'is_active': True,
            }
            records.append(record)

    # Write out as JSON
    with out_path.open('w', encoding='utf-8') as outfh:
        json.dump(records, outfh, ensure_ascii=False, indent=2)

    logger.info('Transformed CSV to seed JSON', csv=str(csv_path), out=str(out_path), count=len(records))
    return out_path


def get_seed_file() -> Path | None:
    """Get the best available seed file (enriched preferred).

    If CSV is present and base seed is missing, transform CSV -> base seed JSON and use it.
    """
    if ENRICHED_DATA_PATH.exists():
        return ENRICHED_DATA_PATH
    if BASE_SEED_PATH.exists():
        return BASE_SEED_PATH

    # If CSV exists, transform to base seed
    csv_path = SEED_DATA_DIR / 'OeffentlicheMarktakteure.csv'
    if csv_path.exists():
        try:
            transform_csv_to_seed(csv_path, BASE_SEED_PATH)
            return BASE_SEED_PATH
        except Exception as e:
            logger.error('Failed to transform CSV to seed JSON', error=str(e))
            return None

    return None


async def seed_dnos(db: AsyncSession) -> tuple[int, int, int, str | None]:
    """
    Seed DNOs from seed data JSON.

    Creates/updates:
    - DNOModel (core hub)
    - DNOMastrData (MaStR source data)
    - DNOVnbData (VNB Digital data, if enriched)
    - DNOBdewData (BDEW data, if enriched)

    Returns:
        Tuple of (inserted, updated, skipped, seed_source).
        seed_source: 'enriched' | 'base' | 'generated_from_csv' | None
    """
    seed_file = get_seed_file()
    seed_source = None
    if not seed_file:
        logger.warning("No seed data file found", paths=[str(ENRICHED_DATA_PATH), str(BASE_SEED_PATH)])
        return 0, 0, 0, None

    if seed_file == ENRICHED_DATA_PATH:
        seed_source = 'enriched'
    elif seed_file == BASE_SEED_PATH:
        # If we created this from a CSV transform, tag accordingly
        seed_source = 'base' if BASE_SEED_PATH.exists() and ENRICHED_DATA_PATH.exists() is False else 'base'
        # If CSV exists and we transformed it just above, mark as generated_from_csv
        csv_path = SEED_DATA_DIR / 'OeffentlicheMarktakteure.csv'
        if csv_path.exists() and not ENRICHED_DATA_PATH.exists() and BASE_SEED_PATH.exists():
            seed_source = 'generated_from_csv'

    logger.info("Loading seed data", path=str(seed_file), enriched=seed_source == 'enriched')

    with open(seed_file, 'r', encoding='utf-8') as f:
        seed_data = json.load(f)

    logger.info("Loaded seed records", count=len(seed_data))

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
        seed_source=seed_source,
    )

    return inserted, updated, skipped, seed_source


async def upsert_dno_from_seed(db: AsyncSession, record: dict[str, Any]) -> str:
    """
    Upsert a single DNO and its source data from seed record.
    
    Returns: 'inserted', 'updated', or 'skipped'
    """
    mastr_nr = record['mastr_nr']
    
    # Check if DNO already exists by mastr_nr
    result = await db.execute(
        select(DNOModel).where(DNOModel.mastr_nr == mastr_nr)
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

    # Create BDEW data if present in enriched record
    if record.get('bdew_code'):
        await upsert_bdew_data(db, dno, record)
        # Update primary BDEW code on core
        dno.primary_bdew_code = record['bdew_code']
    
    logger.debug(f"{action.capitalize()} DNO from seed", mastr_nr=mastr_nr, name=record['name'])
    return action


async def upsert_mastr_data(db: AsyncSession, dno: DNOModel, record: dict[str, Any]) -> None:
    """Create or update MaStR source data for a DNO."""
    
    # Check if MaStR data already exists
    if dno.mastr_data:
        mastr = dno.mastr_data
    else:
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
    
    # Check if VNB data already exists
    if dno.vnb_data:
        vnb = dno.vnb_data
    else:
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
