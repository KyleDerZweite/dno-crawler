#!/usr/bin/env python3
"""
Transform OeffentlicheMarktakteure.csv to dnos_seed.json.

This script parses the MaStR (Marktstammdatenregister) CSV export and
produces a clean JSON format for database seeding.

Usage:
    python transform_csv_to_json.py [--input INPUT] [--output OUTPUT]

The CSV has the following columns (semicolon-delimited):
- MaStR-Nr.: Unique MaStR identifier (e.g., SNB982046657236)
- Name des Marktakteurs: Company name
- Marktfunktion: Market function (always "Stromnetzbetreiber" in this dataset)
- Marktrollen: Market roles (comma-separated)
- Bundesland: Federal state/region
- Postleitzahl: ZIP code
- Ort: City
- Straße: Street name
- Hausnummer: House number
- Land: Country
- Registrierungsdatum: Registration date (M/D/YYYY format)
- Datum der letzten Aktualisierung: Last update date
- ACER-Code: ACER identifier (nullable)
- Geschlossenes Verteilernetz: Closed distribution network flag
- Tätigkeitsstatus: Activity status
- Tätigkeitsbeginn: Activity start date
- Tätigkeitsende: Activity end date (usually empty)
"""

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path


def slugify(name: str) -> str:
    """Convert company name to URL-friendly slug."""
    # Lowercase
    slug = name.lower()
    # Replace German umlauts and ß
    replacements = {
        'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss',
        'Ä': 'ae', 'Ö': 'oe', 'Ü': 'ue'
    }
    for old, new in replacements.items():
        slug = slug.replace(old, new)
    # Replace spaces and special chars with hyphens
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    # Remove leading/trailing hyphens and collapse multiple hyphens
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug


def parse_date(date_str: str) -> str | None:
    """Parse US format date (M/D/YYYY) to ISO format (YYYY-MM-DD)."""
    if not date_str or not date_str.strip():
        return None
    try:
        # Handle M/D/YYYY format
        dt = datetime.strptime(date_str.strip(), "%m/%d/%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        # Try alternative formats
        for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d.%m.%Y"]:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None


def parse_market_roles(roles_str: str) -> list[str]:
    """Parse comma-separated market roles into a list."""
    if not roles_str or not roles_str.strip():
        return []
    return [role.strip() for role in roles_str.split(',') if role.strip()]


def parse_boolean(value: str) -> bool:
    """Parse Ja/Nein to boolean."""
    return value.strip().lower() == 'ja'


def transform_row(row: dict) -> dict:
    """Transform a single CSV row to the output JSON format."""
    # Extract and clean fields
    mastr_nr = row.get('MaStR-Nr.', '').strip()
    name = row.get('Name des Marktakteurs', '').strip()

    # Address components
    street = row.get('Straße', '').strip()
    house_number = row.get('Hausnummer', '').strip()
    zip_code = row.get('Postleitzahl', '').strip()
    city = row.get('Ort', '').strip()
    region = row.get('Bundesland', '').strip()
    country = row.get('Land', '').strip()

    # Build address_components dict
    address_components = {}
    if street:
        address_components['street'] = street
    if house_number:
        address_components['house_number'] = house_number
    if zip_code:
        address_components['zip_code'] = zip_code
    if city:
        address_components['city'] = city
    if country:
        address_components['country'] = country

    # Build formatted contact_address for display
    parts = []
    if street and house_number:
        parts.append(f"{street} {house_number}")
    elif street:
        parts.append(street)
    if zip_code and city:
        parts.append(f"{zip_code} {city}")
    elif city:
        parts.append(city)
    contact_address = ", ".join(parts) if parts else None

    # ACER code (can be empty)
    acer_code = row.get('ACER-Code', '').strip() or None

    # Market roles
    marktrollen = parse_market_roles(row.get('Marktrollen', ''))

    # Dates
    registration_date = parse_date(row.get('Registrierungsdatum', ''))
    last_updated = parse_date(row.get('Datum der letzten Aktualisierung', ''))
    activity_start = parse_date(row.get('Tätigkeitsbeginn', ''))
    activity_end = parse_date(row.get('Tätigkeitsende', ''))

    # Boolean flags
    closed_network = parse_boolean(row.get('Geschlossenes Verteilernetz', 'Nein'))

    # Activity status
    activity_status = row.get('Tätigkeitsstatus', '').strip()
    is_active = activity_status.lower() == 'aktiv'

    return {
        'mastr_nr': mastr_nr,
        'name': name,
        'slug': slugify(name),
        'region': region or None,
        'acer_code': acer_code,
        'address_components': address_components if address_components else None,
        'contact_address': contact_address,
        'marktrollen': marktrollen if marktrollen else None,
        'registration_date': registration_date,
        'last_updated': last_updated,
        'activity_start': activity_start,
        'activity_end': activity_end,
        'closed_network': closed_network,
        'is_active': is_active,
    }


def transform_csv_to_json(input_path: Path, output_path: Path) -> int:
    """
    Transform the CSV file to JSON format.

    Returns the number of records processed.
    """
    records = []

    # Use utf-8-sig to handle BOM (Byte Order Mark)
    with open(input_path, encoding='utf-8-sig') as f:
        # CSV is semicolon-delimited
        reader = csv.DictReader(f, delimiter=';')

        for row in reader:
            # Skip empty rows
            if not row.get('MaStR-Nr.', '').strip():
                continue

            record = transform_row(row)
            records.append(record)

    # Sort by name for consistent output
    records.sort(key=lambda x: x['name'].lower())

    # Write JSON output
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    return len(records)


def main():
    parser = argparse.ArgumentParser(
        description='Transform OeffentlicheMarktakteure.csv to dnos_seed.json'
    )
    parser.add_argument(
        '--input', '-i',
        type=Path,
        default=Path(__file__).parent.parent.parent / 'data' / 'seed-data' / 'OeffentlicheMarktakteure.csv',
        help='Input CSV file path'
    )
    parser.add_argument(
        '--output', '-o',
        type=Path,
        default=Path(__file__).parent.parent.parent / 'data' / 'seed-data' / 'dnos_seed.json',
        help='Output JSON file path'
    )

    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}")
        return 1

    print(f"Reading from: {args.input}")
    print(f"Writing to: {args.output}")

    count = transform_csv_to_json(args.input, args.output)

    print(f"Successfully transformed {count} records")
    return 0


if __name__ == '__main__':
    sys.exit(main())
