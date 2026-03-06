#!/usr/bin/env python3
"""Recompute and persist DNO importance scores for all DNOs."""

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


async def recompute(dry_run: bool) -> dict[str, int]:
    from app.db.database import async_session_maker
    from app.db.models import DNOModel
    from app.services.importance import apply_importance_to_dno

    batch_size = 200

    stats = {
        "total": 0,
        "updated": 0,
    }

    async with async_session_maker() as session:
        last_id = 0

        while True:
            result = await session.execute(
                select(DNOModel)
                .options(selectinload(DNOModel.mastr_data))
                .where(DNOModel.id > last_id)
                .order_by(DNOModel.id.asc())
                .limit(batch_size)
            )
            dnos = result.scalars().all()
            if not dnos:
                break

            for dno in dnos:
                apply_importance_to_dno(dno)
                stats["updated"] += 1

            stats["total"] += len(dnos)
            last_id = dnos[-1].id

            if dry_run:
                await session.flush()
                session.expunge_all()
            else:
                await session.commit()

        if dry_run:
            await session.rollback()

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Recompute DNO importance scores")
    parser.add_argument("--dry-run", action="store_true", help="Validate without commit")
    args = parser.parse_args()

    summary = asyncio.run(recompute(dry_run=args.dry_run))
    print("Importance recompute summary")
    print(f"  total:   {summary['total']}")
    print(f"  updated: {summary['updated']}")


if __name__ == "__main__":
    main()
