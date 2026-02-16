#!/usr/bin/env python3
"""
MaStR Data Transformation Script.

Transforms Marktstammdatenregister XML exports into pre-computed DNO statistics.

Usage:
    python transform_mastr.py --data-dir ./data --output dno_stats.json
    python transform_mastr.py --data-dir ./data --output dno_stats.json --quick  # Skip energy units (faster)

The output JSON file can be:
1. Embedded in the DNO seed parquet file
2. Imported directly into the database via import_mastr_stats.py

Output format:
    {
        "metadata": {...},
        "dnos": {
            "SNB123456789": {
                "name": "Example DNO",
                "connection_points": {"total": 100, "by_voltage": {...}},
                "networks": {...},
                "installed_capacity_mw": {...},
                "unit_counts": {...}
            }
        }
    }
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from mastr.parsers import (
    parse_connection_points,
    parse_energy_units,
    parse_locations,
    parse_market_actors,
    parse_market_roles,
    parse_networks,
    build_location_to_dno_map,
)
from mastr.aggregators import aggregate_dno_stats


def find_export_date(data_dir: str) -> str | None:
    """
    Try to determine the MaStR export date from file timestamps.
    
    Returns ISO date string or None.
    """
    # Check for Dokumentation file
    doc_files = list(Path(data_dir).glob("Dokumentation*.zip"))
    if doc_files:
        # Parse date from filename like "Dokumentation MaStR Gesamtdatenexport.zip"
        mtime = datetime.fromtimestamp(doc_files[0].stat().st_mtime)
        return mtime.date().isoformat()
    
    # Fall back to newest XML file
    xml_files = list(Path(data_dir).glob("*.xml"))
    if xml_files:
        newest = max(xml_files, key=lambda f: f.stat().st_mtime)
        mtime = datetime.fromtimestamp(newest.stat().st_mtime)
        return mtime.date().isoformat()
    
    return None


def transform_mastr(
    data_dir: str,
    output_file: str,
    skip_energy_units: bool = False,
    verbose: bool = True,
) -> dict:
    """
    Main transformation function.
    
    Args:
        data_dir: Path to directory containing MaStR XML files
        output_file: Path to output JSON file
        skip_energy_units: If True, skip energy unit parsing (faster)
        verbose: Print progress messages
    
    Returns:
        The output dictionary
    """
    data_dir = os.path.abspath(data_dir)
    
    if not os.path.isdir(data_dir):
        raise NotADirectoryError(f"Data directory not found: {data_dir}")
    
    print(f"Transforming MaStR data from: {data_dir}")
    print(f"Output file: {output_file}")
    
    # Phase 1: Parse DNOs from market roles
    print("\n[Phase 1/6] Parsing market roles...")
    dnos = parse_market_roles(data_dir)
    print(f"  Found {len(dnos)} DNOs")
    
    # Phase 2: Enrich DNO details from market actors
    print("\n[Phase 2/6] Parsing market actors...")
    dnos = parse_market_actors(data_dir, dnos)
    
    # Phase 3: Parse networks
    print("\n[Phase 3/6] Parsing networks...")
    networks = parse_networks(data_dir)
    print(f"  Found {len(networks)} networks")
    
    # Phase 4: Parse connection points
    print("\n[Phase 4/6] Parsing connection points...")
    connection_points, dno_to_cps = parse_connection_points(data_dir)
    print(f"  Found {len(connection_points)} connection points")
    print(f"  Mapped to {len(dno_to_cps)} DNOs")
    
    # Phase 5: Parse locations (needed for energy unit linkage)
    print("\n[Phase 5/6] Parsing locations...")
    locations = parse_locations(data_dir)
    print(f"  Found {len(locations)} locations")
    
    # Build location -> DNO map
    loc_to_dno = build_location_to_dno_map(locations, connection_points)
    print(f"  Mapped {len(loc_to_dno)} locations to DNOs")
    
    # Phase 6: Parse energy units (optional, slow)
    dno_units = {}
    if not skip_energy_units:
        print("\n[Phase 6/6] Parsing energy units...")
        dno_units = parse_energy_units(data_dir, loc_to_dno)
        total_units = sum(len(units) for units in dno_units.values())
        print(f"  Found {total_units} units across {len(dno_units)} DNOs")
    else:
        print("\n[Phase 6/6] Skipping energy units (--quick mode)")
    
    # Aggregate all statistics
    print("\n[Aggregating] Computing DNO statistics...")
    dno_stats, metadata = aggregate_dno_stats(
        dnos=dnos,
        connection_points=connection_points,
        dno_to_cps=dno_to_cps,
        networks=networks,
        dno_units=dno_units,
    )
    
    # Set export date
    metadata.mastr_export_date = find_export_date(data_dir)
    if skip_energy_units:
        metadata.data_quality = "partial"  # No energy capacity data
    
    # Build output
    output = {
        "metadata": metadata.to_dict(),
        "dnos": {mastr_nr: stats.to_dict() for mastr_nr, stats in dno_stats.items()},
    }
    
    # Write output
    print(f"\n[Writing] Saving to {output_file}...")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print("\n" + "=" * 60)
    print("TRANSFORMATION COMPLETE")
    print("=" * 60)
    print(f"Total DNOs:          {metadata.total_dnos}")
    print(f"With connection pts: {metadata.dnos_with_connection_points}")
    print(f"With capacity data:  {metadata.dnos_with_capacity_data}")
    print(f"Data quality:        {metadata.data_quality}")
    print(f"Output file:         {output_file}")
    print("=" * 60)
    
    return output


def main():
    parser = argparse.ArgumentParser(
        description="Transform MaStR XML data into DNO statistics JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Full transformation (1-2 hours)
    python transform_mastr.py --data-dir ./data --output dno_stats.json

    # Quick mode without energy units (10-30 minutes)
    python transform_mastr.py --data-dir ./data --output dno_stats.json --quick

Output can be:
    1. Merged into dnos_enriched.parquet for seeding
    2. Imported directly via scripts/import_mastr_stats.py
        """,
    )
    
    parser.add_argument(
        "--data-dir",
        required=True,
        help="Directory containing MaStR XML files",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output JSON file path",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Skip energy unit parsing (faster, but no capacity data)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )
    
    args = parser.parse_args()
    
    try:
        transform_mastr(
            data_dir=args.data_dir,
            output_file=args.output,
            skip_energy_units=args.quick,
            verbose=not args.quiet,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
