#!/usr/bin/env python3
"""
Recursively clean and format HTML files in bulk-data.

For each .html file under the given root directory, this script:
1) Removes inline style attributes
2) Removes <style> tags
3) Removes stylesheet link tags (<link rel="stylesheet" ...>)
4) Writes a prettified HTML version back to the same file

Usage:
    python backend/scripts/format_bulk_html.py
    python backend/scripts/format_bulk_html.py --root data/bulk-data
    python backend/scripts/format_bulk_html.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def _is_stylesheet_link(tag) -> bool:
    if tag.name != "link":
        return False

    rel_values = tag.get("rel")
    if not rel_values:
        return False

    if isinstance(rel_values, str):
        rel_values = [rel_values]

    rel_normalized = {str(value).strip().lower() for value in rel_values}
    return "stylesheet" in rel_normalized


def clean_html(content: str) -> tuple[str, int, int, int]:
    soup = BeautifulSoup(content, "html.parser")

    style_tag_count = 0
    style_attr_count = 0
    stylesheet_link_count = 0

    for style_tag in soup.find_all("style"):
        style_tag.decompose()
        style_tag_count += 1

    for tag in soup.find_all(True):
        if tag.has_attr("style"):
            del tag["style"]
            style_attr_count += 1

    for link_tag in soup.find_all(_is_stylesheet_link):
        link_tag.decompose()
        stylesheet_link_count += 1

    formatted = soup.prettify(formatter="minimal")
    if not formatted.endswith("\n"):
        formatted += "\n"

    return formatted, style_tag_count, style_attr_count, stylesheet_link_count


def process_html_file(file_path: Path, dry_run: bool) -> tuple[bool, int, int, int]:
    original = file_path.read_text(encoding="utf-8", errors="ignore")
    cleaned, style_tags, style_attrs, stylesheet_links = clean_html(original)

    changed = cleaned != original
    if changed and not dry_run:
        file_path.write_text(cleaned, encoding="utf-8")

    return changed, style_tags, style_attrs, stylesheet_links


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recursively format HTML files and remove style-related parts"
    )
    parser.add_argument(
        "--root",
        "-r",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "data" / "bulk-data",
        help="Root directory to scan recursively (default: data/bulk-data)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing files",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    if not root.exists() or not root.is_dir():
        print(f"Error: root directory does not exist or is not a directory: {root}")
        return 1

    html_files = sorted(root.rglob("*.html"))
    if not html_files:
        print(f"No .html files found under: {root}")
        return 0

    changed_files = 0
    total_style_tags = 0
    total_style_attrs = 0
    total_stylesheet_links = 0

    print(f"Scanning {len(html_files)} HTML files under: {root}")
    if args.dry_run:
        print("Dry run enabled: no files will be modified")

    for file_path in html_files:
        changed, style_tags, style_attrs, stylesheet_links = process_html_file(
            file_path=file_path,
            dry_run=args.dry_run,
        )
        total_style_tags += style_tags
        total_style_attrs += style_attrs
        total_stylesheet_links += stylesheet_links

        if changed:
            changed_files += 1
            print(f"updated: {file_path}")

    print("---")
    print(f"HTML files scanned: {len(html_files)}")
    print(f"HTML files changed: {changed_files}")
    print(f"<style> tags removed: {total_style_tags}")
    print(f"style attributes removed: {total_style_attrs}")
    print(f"stylesheet links removed: {total_stylesheet_links}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
