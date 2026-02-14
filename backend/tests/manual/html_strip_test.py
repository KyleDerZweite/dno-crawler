#!/usr/bin/env python3
"""
Manual test script for HTML stripping service.

Usage:
    # Strip a single file and print result
    python -m tests.manual.html_strip_test strip path/to/file.html

    # Strip and split into year files
    python -m tests.manual.html_strip_test split path/to/file.html output_dir slug data_type

    # Test with the RheinNetz example
    python -m tests.manual.html_strip_test test-rheinnetz

Run from backend directory.
"""

import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.extraction.html_stripper import HtmlStripper, get_file_size_kb


def strip_file(html_path: Path) -> None:
    """Strip a file and print the result."""
    print(f"\n📄 Input file: {html_path}")
    print(f"   Size: {get_file_size_kb(html_path):.1f} KB")

    html_content = html_path.read_text(encoding="utf-8")

    stripper = HtmlStripper()
    stripped_html, years_found = stripper.strip_html(html_content)

    print("\n📊 Results:")
    print(f"   Years found: {years_found}")
    print(f"   Stripped size: {len(stripped_html) / 1024:.1f} KB")
    print(f"   Reduction: {(1 - len(stripped_html) / len(html_content)) * 100:.1f}%")

    print("\n📝 Stripped HTML (first 2000 chars):")
    print("-" * 60)
    print(stripped_html[:2000])
    print("-" * 60)

    # Save to temp file for inspection
    output_path = html_path.parent / f"{html_path.stem}_stripped.html"
    output_path.write_text(stripped_html, encoding="utf-8")
    print(f"\n✅ Saved stripped HTML to: {output_path}")


def split_file(html_path: Path, output_dir: Path, slug: str, data_type: str) -> None:
    """Strip and split a file into year-specific files."""
    print(f"\n📄 Input file: {html_path}")
    print(f"   Size: {get_file_size_kb(html_path):.1f} KB")
    print(f"   Output dir: {output_dir}")
    print(f"   Slug: {slug}")
    print(f"   Data type: {data_type}")

    html_content = html_path.read_text(encoding="utf-8")

    stripper = HtmlStripper()
    created_files = stripper.strip_and_split(
        html_content=html_content, output_dir=output_dir, slug=slug, data_type=data_type
    )

    print(f"\n✅ Created {len(created_files)} files:")
    for year, file_path in created_files:
        size_kb = get_file_size_kb(file_path)
        print(f"   - Year {year}: {file_path.name} ({size_kb:.1f} KB)")


def test_rheinnetz() -> None:
    """Test with the RheinNetz example file."""
    base_dir = Path(__file__).parent.parent.parent.parent
    html_path = (
        base_dir
        / "data"
        / "downloads"
        / "rheinnetz-gmbh-rng"
        / "Netzentgelte für die Stromnetznutzung _ RheinNetz.html"
    )

    if not html_path.exists():
        print(f"❌ Test file not found: {html_path}")
        return

    output_dir = base_dir / "data" / "downloads" / "rheinnetz-gmbh-rng" / "_test_output"

    print("=" * 60)
    print("Testing HTML Stripper with RheinNetz HLZF page")
    print("=" * 60)

    # First, just strip and show results
    print("\n--- Step 1: Strip only ---")
    strip_file(html_path)

    # Then, strip and split
    print("\n--- Step 2: Strip and split by year ---")
    split_file(
        html_path=html_path, output_dir=output_dir, slug="rheinnetz-gmbh-rng", data_type="hlzf"
    )

    # Now test extraction on the split files
    print("\n--- Step 3: Test extraction on split files ---")
    from app.services.extraction.html_extractor import extract_hlzf_from_html

    for year_file in output_dir.glob("*.html"):
        # Extract year from filename
        year_str = year_file.stem.split("-")[-1]
        try:
            year = int(year_str)
        except ValueError:
            continue

        html_content = year_file.read_text(encoding="utf-8")
        records = extract_hlzf_from_html(html_content, year)

        print(f"\n   📊 {year_file.name}:")
        print(f"      Records extracted: {len(records)}")

        for rec in records:
            print(f"      - {rec['voltage_level']}: Winter={rec['winter'] or 'entfällt'}")


def print_usage() -> None:
    """Print usage instructions."""
    print(__doc__)


def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print_usage()
        return

    command = sys.argv[1]

    if command == "strip":
        if len(sys.argv) < 3:
            print("Usage: python -m tests.manual.html_strip_test strip <html_file>")
            return
        html_path = Path(sys.argv[2])
        if not html_path.exists():
            print(f"File not found: {html_path}")
            return
        strip_file(html_path)

    elif command == "split":
        if len(sys.argv) < 6:
            print(
                "Usage: python -m tests.manual.html_strip_test split <html_file> <output_dir> <slug> <data_type>"
            )
            return
        html_path = Path(sys.argv[2])
        output_dir = Path(sys.argv[3])
        slug = sys.argv[4]
        data_type = sys.argv[5]

        if not html_path.exists():
            print(f"File not found: {html_path}")
            return

        split_file(html_path, output_dir, slug, data_type)

    elif command == "test-rheinnetz":
        test_rheinnetz()

    else:
        print_usage()


if __name__ == "__main__":
    main()
