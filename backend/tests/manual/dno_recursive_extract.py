



import asyncio
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

async def simple_recursive_extract(start_url: str, year: int, max_depth: int = 1):
    """
    A simple crawler that looks for PDF links related to a specific year.
    """
    visited = set()
    to_visit = [(start_url, 0)]
    found_pdfs = set()
    
    keywords = ["netzentgelt", "preisblatt", "strom", "hlzf", "hochlast"]
    
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as client:
        while to_visit:
            url, depth = to_visit.pop(0)
            if url in visited or depth > max_depth:
                continue
            
            visited.add(url)
            print(f"🔍 Visiting (d={depth}): {url}")
            
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    continue
                
                soup = BeautifulSoup(resp.text, "html.parser")
                
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    full_url = urljoin(url, href)
                    text = a.get_text().strip().lower()
                    link_lower = full_url.lower()
                    
                    # 1. Check if it's a PDF
                    if link_lower.endswith(".pdf"):
                        if str(year) in link_lower or str(year) in text:
                            if any(k in link_lower or k in text for k in keywords):
                                print(f"  ✨ Found PDF: {full_url}")
                                found_pdfs.add(full_url)
                    
                    # 2. Check if we should crawl deeper
                    elif depth < max_depth:
                        # Only same domain
                        if urlparse(full_url).netloc == urlparse(start_url).netloc:
                            # Only if it looks relevant
                            if any(k in link_lower or k in text for k in keywords):
                                if full_url not in visited:
                                    to_visit.append((full_url, depth + 1))
                                    
            except Exception as e:
                print(f"  ⚠️ Error: {e}")

    return found_pdfs

if __name__ == "__main__":
    # Example usage for testing
    START_URL = "https://www.rhein-netz.de/service/veroeffentlichungen/netzentgelte-strom/"
    YEAR = 2025
    
    print(f"--- Recursive Extract Test for {YEAR} ---")
    pdfs = asyncio.run(simple_recursive_extract(START_URL, YEAR))
    
    print(f"\n✅ Done! Found {len(pdfs)} PDFs.")
    for p in pdfs:
        print(f" -> {p}")
