"""
Database seeder for DNO data.

Loads seed data from dnos_seed.json and upserts into the database.
This runs on application/worker startup.
"""

import json
from datetime import datetime
from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DNOModel

logger = structlog.get_logger()

# Path to seed data (relative to backend root)
SEED_DATA_PATH = Path(__file__).parent.parent.parent.parent / "data" / "seed-data" / "dnos_seed.json"


def parse_date(date_str: str | None) -> datetime | None:
    """Parse ISO date string to datetime."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        return None


async def seed_dnos(db: AsyncSession) -> tuple[int, int, int]:
    """
    Seed DNOs from dnos_seed.json.
    
    Uses PostgreSQL upsert (INSERT ... ON CONFLICT) for efficiency.
    Only updates records where enrichment_status is still 'pending' (not yet enriched).
    
    Returns:
        Tuple of (inserted, updated, skipped) counts.
    """
    if not SEED_DATA_PATH.exists():
        logger.warning("Seed data file not found", path=str(SEED_DATA_PATH))
        return 0, 0, 0
    
    logger.info("Loading seed data", path=str(SEED_DATA_PATH))
    
    with open(SEED_DATA_PATH, 'r', encoding='utf-8') as f:
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
        
        # Check if record already exists
        existing = await db.execute(
            select(DNOModel).where(DNOModel.mastr_nr == mastr_nr)
        )
        existing_dno = existing.scalar_one_or_none()
        
        if existing_dno:
            # Only update if enrichment hasn't happened yet
            if existing_dno.enrichment_status in ('completed', 'processing'):
                logger.debug(
                    "Skipping already enriched DNO",
                    mastr_nr=mastr_nr,
                    name=existing_dno.name,
                    enrichment_status=existing_dno.enrichment_status
                )
                skipped += 1
                continue
            
            # Update base fields from seed data
            existing_dno.name = record['name']
            existing_dno.slug = record['slug']
            existing_dno.region = record.get('region')
            existing_dno.acer_code = record.get('acer_code')
            existing_dno.address_components = record.get('address_components')
            existing_dno.contact_address = record.get('contact_address')
            existing_dno.marktrollen = record.get('marktrollen')
            existing_dno.registration_date = parse_date(record.get('registration_date'))
            existing_dno.mastr_last_updated = parse_date(record.get('last_updated'))
            existing_dno.closed_network = record.get('closed_network', False)
            existing_dno.is_active = record.get('is_active', True)
            existing_dno.source = 'seed'
            
            updated += 1
            logger.debug("Updated DNO from seed", mastr_nr=mastr_nr, name=record['name'])
        else:
            # Insert new record
            new_dno = DNOModel(
                slug=record['slug'],
                name=record['name'],
                mastr_nr=mastr_nr,
                acer_code=record.get('acer_code'),
                region=record.get('region'),
                address_components=record.get('address_components'),
                contact_address=record.get('contact_address'),
                marktrollen=record.get('marktrollen'),
                registration_date=parse_date(record.get('registration_date')),
                mastr_last_updated=parse_date(record.get('last_updated')),
                closed_network=record.get('closed_network', False),
                is_active=record.get('is_active', True),
                source='seed',
                enrichment_status='pending',
                status='uncrawled',
            )
            db.add(new_dno)
            inserted += 1
            logger.debug("Inserted new DNO from seed", mastr_nr=mastr_nr, name=record['name'])
    
    await db.commit()
    
    logger.info(
        "Seeding complete",
        inserted=inserted,
        updated=updated,
        skipped=skipped,
        total=len(seed_data)
    )
    
    return inserted, updated, skipped


async def get_pending_enrichment_dno_ids(db: AsyncSession, limit: int | None = None) -> list[int]:
    """
    Get DNO IDs that need enrichment (enrichment_status='pending').
    
    Args:
        db: Database session
        limit: Maximum number of IDs to return (None for all)
    
    Returns:
        List of DNO IDs needing enrichment.
    """
    query = select(DNOModel.id).where(
        DNOModel.enrichment_status == 'pending'
    ).order_by(DNOModel.id)
    
    if limit:
        query = query.limit(limit)
    
    result = await db.execute(query)
    return list(result.scalars().all())
