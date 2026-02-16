#!/usr/bin/env python3
"""Import MaStR statistics from dno_stats.json into the backend database."""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _to_decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (ArithmeticError, ValueError, TypeError):
        return None


def _normalize_connection_points(connection_points: dict) -> dict[str, int | None]:
    """Normalize MaStR connection-point buckets from legacy or canonical formats."""
    by_voltage = connection_points.get("by_voltage") or {}
    by_canonical = connection_points.get("by_canonical_level") or {}

    if by_canonical:
        level_ns = by_canonical.get("NS") or 0
        level_ns_ms = by_canonical.get("Umspannung NS/MS") or by_canonical.get("MS/NS") or 0
        level_ms = by_canonical.get("MS") or 0
        level_ms_hs = by_canonical.get("Umspannung MS/HS") or by_canonical.get("HS/MS") or 0
        level_hs = by_canonical.get("HS") or 0
        level_hs_hoe = by_canonical.get("Umspannung HS/HöS") or by_canonical.get("HöS/HS") or 0
        level_hoe = by_canonical.get("HöS") or 0
        ns = level_ns + level_ns_ms
        ms = level_ms + level_ms_hs
        hs = level_hs + level_hs_hoe
        hoe = level_hoe
        return {
            "total": connection_points.get("total"),
            "by_level": {
                "NS": level_ns,
                "Umspannung NS/MS": level_ns_ms,
                "MS": level_ms,
                "Umspannung MS/HS": level_ms_hs,
                "HS": level_hs,
                "Umspannung HS/HöS": level_hs_hoe,
                "HöS": level_hoe,
            },
            "ns": ns,
            "ms": ms,
            "hs": hs,
            "hoe": hoe,
        }

    return {
        "total": connection_points.get("total"),
        "by_level": {
            "NS": by_voltage.get("ns") or 0,
            "Umspannung NS/MS": 0,
            "MS": by_voltage.get("ms") or 0,
            "Umspannung MS/HS": 0,
            "HS": by_voltage.get("hs") or 0,
            "Umspannung HS/HöS": 0,
            "HöS": by_voltage.get("hoe") or 0,
        },
        "ns": by_voltage.get("ns"),
        "ms": by_voltage.get("ms"),
        "hs": by_voltage.get("hs"),
        "hoe": by_voltage.get("hoe"),
    }


async def import_stats(file_path: Path, dry_run: bool) -> dict[str, int]:
    from app.db.database import async_session_maker
    from app.db.models import DNOModel
    from app.db.source_models import DNOMastrData

    with file_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    dnos_payload = payload.get("dnos") or {}

    stats = {
        "total": len(dnos_payload),
        "found": 0,
        "not_found": 0,
        "updated": 0,
        "created_mastr": 0,
    }

    async with async_session_maker() as session:
        for mastr_nr, dno_stats in dnos_payload.items():
            result = await session.execute(select(DNOModel).where(DNOModel.mastr_nr == mastr_nr))
            dno = result.scalar_one_or_none()
            if dno is None:
                stats["not_found"] += 1
                continue

            stats["found"] += 1

            mastr_result = await session.execute(
                select(DNOMastrData).where(DNOMastrData.dno_id == dno.id)
            )
            mastr = mastr_result.scalar_one_or_none()
            if mastr is None:
                mastr = DNOMastrData(
                    dno_id=dno.id,
                    mastr_nr=mastr_nr,
                    registered_name=dno.name,
                )
                session.add(mastr)
                stats["created_mastr"] += 1

            connection_points = dno_stats.get("connection_points") or {}
            normalized_cp = _normalize_connection_points(connection_points)
            mastr.connection_points_total = normalized_cp.get("total")
            mastr.connection_points_by_level = normalized_cp.get("by_level")
            mastr.connection_points_ns = normalized_cp.get("ns")
            mastr.connection_points_ms = normalized_cp.get("ms")
            mastr.connection_points_hs = normalized_cp.get("hs")
            mastr.connection_points_hoe = normalized_cp.get("hoe")

            networks = dno_stats.get("networks") or {}
            mastr.networks_count = networks.get("count")
            mastr.has_customers = networks.get("has_customers")
            mastr.closed_distribution_network = networks.get("closed_distribution_network")

            capacity = dno_stats.get("installed_capacity_mw") or {}
            mastr.total_capacity_mw = _to_decimal(capacity.get("total"))
            mastr.solar_capacity_mw = _to_decimal(capacity.get("solar"))
            mastr.wind_capacity_mw = _to_decimal(capacity.get("wind"))
            mastr.storage_capacity_mw = _to_decimal(capacity.get("storage"))
            mastr.biomass_capacity_mw = _to_decimal(capacity.get("biomass"))
            mastr.hydro_capacity_mw = _to_decimal(capacity.get("hydro"))

            units = dno_stats.get("unit_counts") or {}
            mastr.solar_units = units.get("solar")
            mastr.wind_units = units.get("wind")
            mastr.storage_units = units.get("storage")

            mastr.stats_data_quality = "full" if dno_stats.get("has_full_data") else "partial"
            mastr.stats_computed_at = datetime.now(UTC)
            mastr.last_synced_at = datetime.now(UTC)

            dno.connection_points_count = mastr.connection_points_total
            dno.total_capacity_mw = mastr.total_capacity_mw

            stats["updated"] += 1

        if dry_run:
            await session.rollback()
        else:
            await session.commit()

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Import MaStR DNO stats JSON into database")
    parser.add_argument("--file", required=True, help="Path to dno_stats.json")
    parser.add_argument("--dry-run", action="store_true", help="Validate without commit")
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    summary = asyncio.run(import_stats(file_path=file_path, dry_run=args.dry_run))
    print("MaStR stats import summary")
    print(f"  total:        {summary['total']}")
    print(f"  found:        {summary['found']}")
    print(f"  not_found:    {summary['not_found']}")
    print(f"  updated:      {summary['updated']}")
    print(f"  created_mastr:{summary['created_mastr']}")


if __name__ == "__main__":
    main()
