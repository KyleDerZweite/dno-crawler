#!/usr/bin/env python3
"""
Discovery Test - Sitemap + BFS Discovery Mode.

Given only a domain and data type, discovers what files/pages exist.
Strategy:
1. Try sitemap discovery first (fast, low impact)
2. Fall back to BFS crawl if no sitemap

Run:
    python -m tests.manual.bfs_discovery_test --url https://www.rheinnetz.de --data-type netzentgelte
    python -m tests.manual.bfs_discovery_test --url https://www.netze-bw.de --data-type hlzf --year 2025 --download
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import httpx
from bs4 import BeautifulSoup

from app.services.html_content_detector import score_html_page_for_data
from app.services.sitemap_discovery import discover_via_sitemap
from app.services.url_utils import normalize_url
from app.services.web_crawler import NEGATIVE_KEYWORDS, WebCrawler, get_keywords_for_data_type

USER_AGENT = "DNO-Data-Crawler/1.0 (Discovery Test)"


@dataclass
class DiscoveredDocument:
    """A discovered document/file or HTML page with embedded data."""
    url: str
    found_on_page: str
    link_text: str
    is_external: bool
    file_type: str  # "pdf", "xlsx", "html" for embedded data
    score: float = 0.0
    keywords_in_url: list[str] = field(default_factory=list)
    has_year: bool = False
    is_html_data: bool = False
    years_in_page: list[int] = field(default_factory=list)


def _get_file_type(url: str) -> str | None:
    """Detect file type from URL."""
    url_lower = url.lower()
    if ".pdf" in url_lower:
        return "pdf"
    elif ".xlsx" in url_lower:
        return "xlsx"
    elif ".xls" in url_lower:
        return "xls"
    elif ".docx" in url_lower or ".doc" in url_lower:
        return "doc"
    return None


async def _scan_for_hlzf_html(
    client: httpx.AsyncClient,
    start_url: str,
    target_year: int | None,
    all_documents: list,
    verbose: bool,
):
    """
    Quick scan for HTML pages containing HLZF data tables.

    Tries common URL patterns where HLZF data is often found.
    """
    from urllib.parse import urlparse

    parsed = urlparse(start_url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    # Common patterns where HLZF/netzentgelte HTML tables are found
    candidate_paths = [
        "/netzentgelte-strom",
        "/netzentgelte",
        "/strom/netzentgelte",
        "/de/netzentgelte",
        "/de/strom/netzentgelte",
        "/netzzugang/netzentgelte",
        "/veroeffentlichungen/netzentgelte",
    ]

    if verbose:
        print(f"      Checking {len(candidate_paths)} common page patterns for HLZF tables...")

    for path in candidate_paths:
        url = base + path
        try:
            response = await client.get(url, timeout=10.0)
            if response.status_code != 200:
                continue

            html_score, html_result = score_html_page_for_data(
                response.text, "hlzf", target_year
            )

            if html_result.has_data_table and html_score > 30:
                has_target_year = target_year in html_result.years_found if target_year else False
                all_documents.append(DiscoveredDocument(
                    url=url,
                    found_on_page="(embedded data)",
                    link_text="",
                    is_external=False,
                    file_type="html",
                    score=html_score + 50,  # Base bonus for having HLZF table
                    keywords_in_url=html_result.keywords_found,
                    has_year=has_target_year,
                    is_html_data=True,
                    years_in_page=html_result.years_found,
                ))
                if verbose:
                    print(f"      📊 Found HLZF data at {url}... Years: {html_result.years_found}")

        except Exception as e:
            if verbose:
                print(f"      ⚠️ Error checking {url}: {e}")



async def discover_documents(
    start_url: str,
    data_type: str,
    target_year: int | None = None,
    max_pages: int = 100,
    max_depth: int = 5,
    verbose: bool = True,
    force_bfs: bool = False,
) -> dict:
    """
    Discovery starting from a URL.

    Strategy:
    1. Try sitemap discovery first (fast, low impact)
    2. Fall back to BFS crawl if no sitemap
    """
    print(f"\n{'=' * 70}")
    print("🔍 DISCOVERY MODE")
    print(f"   Start URL: {start_url}")
    print(f"   Data Type: {data_type}")
    print(f"   Target Year: {target_year or 'any'}")
    print(f"   Max Pages: {max_pages}")
    print("=" * 70)

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=15.0,
    ) as client:

        all_documents: list[DiscoveredDocument] = []
        discovery_strategy = "unknown"
        pages_crawled = 0
        top_pages = []

        # Strategy 1: Try sitemap first (fast, low impact)
        if not force_bfs:
            print("\n📄 Trying sitemap discovery...")
            sitemap_results, sitemap_found = await discover_via_sitemap(
                client=client,
                base_url=start_url,
                data_type=data_type,
                target_year=target_year,
                max_candidates=50,
            )

            if sitemap_found and sitemap_results:
                # For HLZF, check if we found HLZF-specific files (not just netzentgelte PDFs)
                hlzf_specific = False
                if data_type == "hlzf":
                    hlzf_keywords = ["hlzf", "hochlast", "zeitfenster"]
                    for r in sitemap_results[:10]:
                        url_lower = r.url.lower()
                        if any(kw in url_lower for kw in hlzf_keywords):
                            hlzf_specific = True
                            break

                    if not hlzf_specific:
                        print("   ⚠️ Sitemap has no HLZF-specific files, will also check HTML pages")
                else:
                    hlzf_specific = True  # Not looking for HLZF, so don't require specific files

                print(f"   ✅ Found sitemap with {len(sitemap_results)} relevant URLs")
                discovery_strategy = "sitemap"

                for r in sitemap_results:
                    all_documents.append(DiscoveredDocument(
                        url=r.url,
                        found_on_page="(sitemap)",
                        link_text="",
                        is_external=False,
                        file_type=r.file_type or "unknown",
                        score=r.score,
                        keywords_in_url=r.keywords_found,
                        has_year=r.has_year,
                    ))

                # For HLZF without specific files, also do BFS to find HTML tables
                if data_type == "hlzf" and not hlzf_specific:
                    print("   🔍 Doing BFS scan to find HTML pages with embedded HLZF data...")
                    await _scan_for_hlzf_html(
                        client, start_url, target_year, all_documents, verbose
                    )
            elif sitemap_found:
                print("   ⚠️ Sitemap found but no relevant URLs")
            else:
                print("   ⚠️ No sitemap found")

        # Strategy 2: Fall back to BFS crawl
        if not all_documents:
            print("\n🕸️ Starting BFS crawl...")
            discovery_strategy = "bfs"

            crawler = WebCrawler(
                client=client,
                max_depth=max_depth,
                max_pages=max_pages,
                request_delay=0.3,
            )

            keywords = get_keywords_for_data_type(data_type)

            if verbose:
                print(f"   📋 Using keywords: {keywords[:8]}...")

            crawl_results = await crawler.crawl(
                start_url=start_url,
                target_keywords=keywords,
                target_year=target_year,
                data_type=data_type,
            )

            pages_crawled = len(crawl_results)
            print(f"   Crawled {pages_crawled} pages")

            internal_docs = [r for r in crawl_results if r.is_document]
            pages = [r for r in crawl_results if not r.is_document]

            print(f"   Found {len(internal_docs)} internal documents")
            print(f"   Found {len(pages)} HTML pages")

            for doc in internal_docs:
                all_documents.append(DiscoveredDocument(
                    url=doc.final_url,
                    found_on_page="(direct discovery)",
                    link_text="",
                    is_external=False,
                    file_type=_get_file_type(doc.final_url),
                    score=doc.score,
                    keywords_in_url=doc.keywords_found,
                    has_year=bool(target_year and str(target_year) in doc.final_url),
                ))

            top_pages_crawl = sorted(pages, key=lambda r: r.score, reverse=True)[:15]
            top_pages = [(p.final_url, p.score, p.title) for p in top_pages_crawl[:5]]

            if verbose:
                print(f"\n📄 Scanning top {len(top_pages_crawl)} pages for document links...")

            parsed_start = urlparse(start_url)
            start_domain = parsed_start.hostname or ""

            for page in top_pages_crawl:
                if verbose:
                    print(f"   Scanning: {page.final_url[:60]}...")

                try:
                    response = await client.get(page.final_url, timeout=10.0)
                    if response.status_code != 200:
                        continue

                    html_content = response.text
                    soup = BeautifulSoup(html_content, "lxml")

                    # Check for embedded data (HLZF only)
                    if data_type == "hlzf":
                        html_score, html_result = score_html_page_for_data(
                            html_content, data_type, target_year
                        )

                        if html_result.has_data_table and html_score > 30:
                            has_target_year = target_year in html_result.years_found if target_year else False
                            all_documents.append(DiscoveredDocument(
                                url=page.final_url,
                                found_on_page="(embedded data)",
                                link_text=page.title or "",
                                is_external=False,
                                file_type="html",
                                score=html_score + page.score,
                                keywords_in_url=html_result.keywords_found,
                                has_year=has_target_year,
                                is_html_data=True,
                                years_in_page=html_result.years_found,
                            ))
                            if verbose:
                                print(f"      📊 Embedded data found! Years: {html_result.years_found}")

                    # Find document links
                    for link in soup.find_all("a", href=True):
                        href = link["href"]
                        full_url = urljoin(page.final_url, href)
                        url_lower = full_url.lower()

                        file_type = _get_file_type(full_url)
                        if not file_type:
                            continue

                        parsed_url = urlparse(full_url)
                        is_external = parsed_url.hostname and start_domain not in parsed_url.hostname

                        score = 0.0
                        keywords_found = []

                        for kw in keywords:
                            if kw.lower() in url_lower:
                                score += 10
                                keywords_found.append(kw)

                        link_text = link.get_text(strip=True)[:100]
                        for kw in keywords:
                            if kw.lower() in link_text.lower() and kw not in keywords_found:
                                score += 5
                                keywords_found.append(kw)

                        has_year = False
                        if target_year and str(target_year) in full_url:
                            score += 20
                            has_year = True

                        if file_type == "pdf":
                            score += 10
                        elif file_type in ("xlsx", "xls"):
                            score += 8

                        if data_type in NEGATIVE_KEYWORDS:
                            for neg_kw, penalty in NEGATIVE_KEYWORDS[data_type]:
                                if neg_kw.lower() in url_lower or neg_kw.lower() in link_text.lower():
                                    score += penalty

                        if score > 0 or file_type:
                            all_documents.append(DiscoveredDocument(
                                url=full_url,
                                found_on_page=page.final_url,
                                link_text=link_text,
                                is_external=is_external,
                                file_type=file_type,
                                score=score,
                                keywords_in_url=keywords_found,
                                has_year=has_year,
                            ))

                except Exception as e:
                    if verbose:
                        print(f"      ⚠️ Error: {e}")

        # Deduplicate
        seen_urls = set()
        unique_docs = []
        for doc in all_documents:
            normalized = normalize_url(doc.url)
            if normalized not in seen_urls:
                seen_urls.add(normalized)
                doc.url = normalized
                unique_docs.append(doc)

        unique_docs.sort(key=lambda d: d.score, reverse=True)

        return {
            "start_url": start_url,
            "data_type": data_type,
            "target_year": target_year,
            "discovery_strategy": discovery_strategy,
            "pages_crawled": pages_crawled,
            "documents_found": unique_docs,
            "top_pages": top_pages,
        }


async def download_top_result(
    results: dict,
    client: httpx.AsyncClient,
    base_dir: Path = Path("data"),
) -> Path | None:
    """Download the top-scoring discovery result."""
    docs = results.get("documents_found", [])
    if not docs:
        print("❌ No documents to download")
        return None

    top_doc = docs[0]

    start_url = results.get("start_url", "")
    parsed = urlparse(start_url)
    hostname = parsed.hostname or "unknown"
    slug = hostname.replace("www.", "").replace(".", "-")

    data_type = results.get("data_type", "unknown")
    year = results.get("target_year", "")
    year_str = f"-{year}" if year else ""

    if top_doc.is_html_data:
        filename = f"{slug}-{data_type}{year_str}.html"
    else:
        ext = top_doc.file_type or "pdf"
        filename = f"{slug}-{data_type}{year_str}.{ext}"

    output_dir = base_dir / slug / "test"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename

    print("\n📥 Downloading top result...")
    print(f"   URL: {top_doc.url[:80]}")
    print(f"   Score: {top_doc.score}")
    print(f"   Type: {'HTML (embedded data)' if top_doc.is_html_data else top_doc.file_type}")
    print(f"   Saving to: {output_path}")

    try:
        response = await client.get(top_doc.url, timeout=30.0)
        response.raise_for_status()

        if top_doc.is_html_data:
            from app.services.extraction.html_stripper import HtmlStripper
            stripper = HtmlStripper()
            stripped_html, years = stripper.strip_html(response.text)
            output_path.write_text(stripped_html, encoding="utf-8")
            print(f"   ✅ Saved stripped HTML ({len(stripped_html):,} bytes, years: {years})")
        else:
            output_path.write_bytes(response.content)
            print(f"   ✅ Downloaded ({len(response.content):,} bytes)")

        return output_path

    except Exception as e:
        print(f"   ❌ Download failed: {e}")
        return None


def print_results(results: dict, verbose: bool):
    """Print discovery results."""
    print(f"\n{'=' * 70}")
    print("📊 DISCOVERY RESULTS")
    print(f"   Strategy: {results.get('discovery_strategy', 'unknown')}")
    print("=" * 70)

    print("\n📈 Stats:")
    print(f"   Pages crawled: {results['pages_crawled']}")
    print(f"   Documents found: {len(results['documents_found'])}")

    docs = results["documents_found"]

    pdf_docs = [d for d in docs if d.file_type == "pdf"]
    xlsx_docs = [d for d in docs if d.file_type in ("xlsx", "xls")]
    html_docs = [d for d in docs if d.is_html_data]

    print(f"   - PDFs: {len(pdf_docs)}")
    print(f"   - Excel: {len(xlsx_docs)}")
    print(f"   - HTML pages with data: {len(html_docs)}")

    if results.get("top_pages"):
        print("\n📄 Top Pages (by keyword relevance):")
        for url, score, title in results["top_pages"]:
            title_str = f' "{title[:40]}"' if title else ""
            print(f"   [{score:5.1f}] {url[:60]}{title_str}")

    if docs:
        print("\n📎 Top Documents (sorted by relevance):")
        for i, doc in enumerate(docs[:20]):
            external = " [EXT]" if doc.is_external else ""
            html_data = " [HTML]" if doc.is_html_data else ""
            year_mark = " 📅" if doc.has_year else ""

            print(f"\n   {i+1}. [{doc.score:5.1f}]{external}{html_data}{year_mark}")
            print(f"      URL: {doc.url[:80]}")
            if doc.link_text:
                print(f"      Link: \"{doc.link_text[:60]}\"")
            if doc.is_html_data and doc.years_in_page:
                print(f"      Years in page: {doc.years_in_page}")
    else:
        print("\n   ❌ No documents found!")

    print(f"\n{'=' * 70}")
    relevant_docs = [d for d in docs if d.score > 20]
    if relevant_docs:
        print(f"✅ Found {len(relevant_docs)} highly relevant documents (score > 20)")
    elif docs:
        print(f"⚠️ Found {len(docs)} documents, but none scored highly")
    else:
        print("❌ No documents discovered - site may use JavaScript or different structure")


async def main():
    parser = argparse.ArgumentParser(description="Discovery Test - Sitemap + BFS")
    parser.add_argument("--url", required=True, help="Start URL")
    parser.add_argument("--data-type", required=True, choices=["netzentgelte", "hlzf"])
    parser.add_argument("--year", type=int, help="Target year")
    parser.add_argument("--max-pages", type=int, default=50, help="Max pages for BFS")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--download", "-d", action="store_true", help="Download top result")
    parser.add_argument("--force-bfs", action="store_true", help="Skip sitemap, force BFS")

    args = parser.parse_args()

    print("=" * 70)
    print("🔍 DISCOVERY TEST")
    print(f"   Time: {datetime.now().isoformat()}")
    print("=" * 70)

    results = await discover_documents(
        start_url=args.url,
        data_type=args.data_type,
        target_year=args.year,
        max_pages=args.max_pages,
        verbose=args.verbose,
        force_bfs=args.force_bfs,
    )

    print_results(results, args.verbose)

    if args.download and results.get("documents_found"):
        async with httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            timeout=30.0,
        ) as client:
            downloaded = await download_top_result(results, client)
            if downloaded:
                print(f"\n✅ Test file saved: {downloaded}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
