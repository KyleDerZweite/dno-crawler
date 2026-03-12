"""
Example usage of the DNO Crawler API client.

Demonstrates public search (no auth) and authenticated flows.
Config is loaded from .env in this directory automatically.
"""

from __future__ import annotations

import json
import sys

from client import DNOCrawlerClient


def public_search_demo(client: DNOCrawlerClient) -> None:
    """Search by address without authentication."""
    print("=== Public Search Demo ===\n")

    result = client.search_by_address(
        street="Musterstr. 1",
        zip_code="10115",
        city="Berlin",
        year=2025,
    )

    status = result.get("status")
    print(f"Search status: {status}")

    if status == "found":
        data = result.get("data", {})
        dno = data.get("dno", {})
        print(f"DNO: {dno.get('name')} (ID: {dno.get('id')})")

        netzentgelte = data.get("netzentgelte", [])
        if netzentgelte:
            print(f"\nNetzentgelte ({len(netzentgelte)} records):")
            for ne in netzentgelte[:3]:
                print(
                    f"  {ne.get('year')} | {ne.get('voltage_level')}"
                    f" | Leistung: {ne.get('leistung')} | Arbeit: {ne.get('arbeit')}"
                )
        else:
            print("No Netzentgelte data available.")
    elif status == "registered":
        print("DNO was registered as a skeleton. Data will be available after crawling.")
    else:
        print(f"Response:\n{json.dumps(result, indent=2, ensure_ascii=False)}")


def authenticated_demo(client: DNOCrawlerClient) -> None:
    """Demonstrate authenticated endpoints."""
    print("\n=== Authenticated Demo ===\n")

    user = client.me()
    print(f"Logged in as: {user.get('data', {}).get('name', 'unknown')}")

    dnos = client.list_dnos(per_page=5, sort_by="name_asc")
    items = dnos.get("data", {}).get("items", [])
    print(f"\nFirst {len(items)} DNOs:")
    for dno in items:
        print(f"  [{dno.get('id')}] {dno.get('name')} -- {dno.get('status', 'n/a')}")

    if items:
        dno_id = items[0]["id"]
        detail = client.get_dno(dno_id)
        dno_data = detail.get("data", {})
        print(f"\nDetails for {dno_data.get('name')}:")
        print(f"  Region: {dno_data.get('region')}")
        print(f"  Website: {dno_data.get('website')}")

        data = client.get_dno_data(dno_id)
        records = data.get("data", {})
        ne_count = len(records.get("netzentgelte", []))
        hlzf_count = len(records.get("hlzf", []))
        print(f"  Data: {ne_count} Netzentgelte, {hlzf_count} HLZF records")


def main() -> None:
    with DNOCrawlerClient() as client:
        # Health check
        health = client.health()
        print(f"API health: {health.get('status')}\n")

        # Public search works without a token
        public_search_demo(client)

        # Authenticated flow requires a token
        if client.token:
            authenticated_demo(client)
        else:
            print("\nSkipping authenticated demo (no DNO_TOKEN in .env).")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
