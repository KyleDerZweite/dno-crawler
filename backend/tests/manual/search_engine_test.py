"""
Manual test script for DuckDuckGo search and URL probing.

This script helps you understand:
1. What raw results DuckDuckGo returns for a query
2. How the relevance filter works
3. How the URL prober validates each result

Run: python -m tests.manual.search_engine_test
"""

import asyncio

import httpx
from ddgs import DDGS

# =============================================================================
# CONFIGURATION - Modify these to test different scenarios
# =============================================================================

# Example queries (modify to test different DNOs/data types)
TEST_QUERIES = [
    "RheinNetz Netzentgelte 2024 filetype:pdf",
    "RheinNetz Preisblatt Strom 2024",
]

# Allowed domains (set to None to allow all, or specify DNO domain)
ALLOWED_DOMAINS = {"rheinnetz.de", "www.rheinnetz.de"}
# ALLOWED_DOMAINS = None  # Uncomment to allow all domains

# Data type for relevance filtering
DATA_TYPE = "netzentgelte"  # or "hlzf"

# Max results per query
MAX_RESULTS = 10


# =============================================================================
# RELEVANCE FILTER (copied from step_02_search.py for testing)
# =============================================================================

def is_relevant(url: str, data_type: str) -> bool:
    """Filter URLs likely to be data sources (quick heuristic)."""
    url_lower = url.lower()
    
    # Obvious non-documents
    skip_patterns = [
        "/blog/", "/news/", "/career/", "/jobs/", 
        "/contact", "/impressum", "/datenschutz",
        "twitter.com", "facebook.com", "linkedin.com", "youtube.com",
    ]
    if any(pattern in url_lower for pattern in skip_patterns):
        return False
    
    # Direct file links are best
    if any(url_lower.endswith(ext) for ext in [".pdf", ".xlsx", ".xls", ".docx"]):
        return True
    
    # Check for data-related keywords in URL
    keywords = {
        "netzentgelte": [
            "netzentgelte", "preisblatt", "netzzugang", 
            "netznutzung", "entgelt", "tarif"
        ],
        "hlzf": [
            "hlzf", "hochlast", "hochlastzeitfenster", 
            "stromnev", "zeitfenster"
        ],
    }
    kws = keywords.get(data_type, [])
    if any(kw in url_lower for kw in kws):
        return True
    
    return True  # Be lenient if on a known DNO domain


# =============================================================================
# URL PROBER (simplified for testing)
# =============================================================================

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "text/html",
}


async def probe_url(client: httpx.AsyncClient, url: str) -> dict:
    """Probe a URL and return detailed info."""
    result = {
        "url": url,
        "reachable": False,
        "status_code": None,
        "content_type": None,
        "final_url": None,
        "error": None,
    }
    
    try:
        response = await client.head(url, follow_redirects=True, timeout=10.0)
        result["reachable"] = response.status_code in (200, 206)
        result["status_code"] = response.status_code
        result["final_url"] = str(response.url)
        
        content_type = response.headers.get("content-type", "")
        result["content_type"] = content_type.split(";")[0].strip().lower()
        
    except httpx.TimeoutException:
        result["error"] = "Timeout"
    except httpx.RequestError as e:
        result["error"] = str(e)
    except Exception as e:
        result["error"] = str(e)
    
    return result


# =============================================================================
# MAIN TEST FUNCTION
# =============================================================================

async def run_search_test():
    print("=" * 80)
    print("🔍 DUCKDUCKGO SEARCH ENGINE TEST")
    print("=" * 80)
    
    ddgs = DDGS(timeout=10)
    
    async with httpx.AsyncClient(
        headers={"User-Agent": "DNO-Data-Crawler/1.0 (Test Script)"},
        follow_redirects=True,
    ) as client:
        
        for query in TEST_QUERIES:
            print(f"\n{'─' * 80}")
            print(f"📝 QUERY: {query}")
            print(f"{'─' * 80}")
            
            # Execute search
            try:
                raw_results = list(ddgs.text(
                    query, 
                    max_results=MAX_RESULTS,
                    region="de-de",
                    backend="duckduckgo"
                ))
            except Exception as e:
                print(f"❌ Search failed: {e}")
                continue
            
            print(f"\n📊 Raw results from DuckDuckGo: {len(raw_results)}")
            
            # Process each result
            relevant_count = 0
            probed_count = 0
            valid_count = 0
            
            for i, r in enumerate(raw_results, 1):
                url = r.get("href", "")
                title = r.get("title", "")[:60]
                
                print(f"\n  [{i}] {title}...")
                print(f"      URL: {url[:80]}...")
                
                # Check relevance
                relevant = is_relevant(url, DATA_TYPE)
                status_emoji = "✅" if relevant else "⏭️"
                print(f"      Relevance: {status_emoji} {'PASS' if relevant else 'SKIP'}")
                
                if not relevant:
                    continue
                relevant_count += 1
                
                # Probe URL
                probe_result = await probe_url(client, url)
                probed_count += 1
                
                if probe_result["error"]:
                    print(f"      Probe: ❌ {probe_result['error']}")
                    continue
                
                print(f"      Status: {probe_result['status_code']}")
                print(f"      Content-Type: {probe_result['content_type']}")
                
                if probe_result["final_url"] != url:
                    print(f"      Final URL: {probe_result['final_url'][:80]}...")
                
                if probe_result["reachable"]:
                    ct = probe_result["content_type"]
                    if ct in ALLOWED_CONTENT_TYPES or url.lower().endswith(".pdf"):
                        print(f"      Probe: ✅ VALID - Would be selected!")
                        valid_count += 1
                    else:
                        print(f"      Probe: ⚠️ Wrong content-type")
                else:
                    print(f"      Probe: ❌ Not reachable")
            
            # Summary
            print(f"\n📈 QUERY SUMMARY:")
            print(f"   Raw results:      {len(raw_results)}")
            print(f"   Passed relevance: {relevant_count}")
            print(f"   Probed:           {probed_count}")
            print(f"   Valid:            {valid_count}")
            
            # Wait between queries to avoid rate limiting
            print("\n   ⏳ Waiting 2s before next query...")
            await asyncio.sleep(2)
    
    print(f"\n{'=' * 80}")
    print("✅ TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_search_test())
