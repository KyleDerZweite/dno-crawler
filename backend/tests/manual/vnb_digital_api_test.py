"""
Automated test script for VNBdigital.de GraphQL API.
Implements the 2-step discovery flow:
1. Search for address -> Get coordinates
2. Query coordinates -> Get VNB (Network Operator)
"""

import asyncio
import json
import httpx
import urllib.parse

# =============================================================================
# API CONFIGURATION
# =============================================================================

URL = "https://www.vnbdigital.de/gateway/graphql"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Origin": "https://www.vnbdigital.de",
    "Referer": "https://www.vnbdigital.de/",
}

# Query 1: Search for Address
SEARCH_QUERY = """
query ($searchTerm: String!) {
  vnb_search(searchTerm: $searchTerm) {
    _id
    title
    subtitle
    logo {
      url
    }
    url
    type
  }
}
"""

# Query 2: Get Provider from Coordinates
COORDINATES_QUERY = """
fragment vnb_Region on vnb_Region {
  _id
  name
  logo {
    url
  }
  bbox
  layerUrl
  slug
  vnbs {
    _id
  }
}

fragment vnb_VNB on vnb_VNB {
  _id
  name
  logo {
    url
  }
  services {
    type {
      name
      type
    }
    activated
  }
  bbox
  layerUrl
  types
  voltageTypes
}

query (
  $coordinates: String
  $filter: vnb_FilterInput
  $withCoordinates: Boolean = false
) {
  vnb_coordinates(coordinates: $coordinates) @include(if: $withCoordinates) {
    geometry
    regions(filter: $filter) {
      ...vnb_Region
    }
    vnbs(filter: $filter) {
      ...vnb_VNB
    }
  }
}
"""

async def find_provider(address: str):
    print(f"🔎 Searching for: '{address}'")
    
    async with httpx.AsyncClient() as client:
        # --- STEP 1: Search Address ---
        payload_search = {
            "query": SEARCH_QUERY,
            "variables": {"searchTerm": address}
        }
        
        try:
            resp_search = await client.post(URL, json=payload_search, headers=HEADERS, timeout=10.0)
            data_search = resp_search.json()
            
            if "errors" in data_search:
                print(f"❌ Search Error: {json.dumps(data_search['errors'], indent=2)}")
                return

            results = data_search.get("data", {}).get("vnb_search", [])
            if not results:
                print("❌ No location found.")
                return

            # Pick the first location result
            location = results[0]
            print(f"✅ Found Location: {location['title']}")
            print(f"   URL: {location['url']}")
            
            # Extract coordinates from URL parameter
            # URL format: /overview?coordinates=50.94834,6.82052&searchType=LOCATION
            parsed_url = urllib.parse.urlparse(location['url'])
            query_params = urllib.parse.parse_qs(parsed_url.query)
            coordinates = query_params.get("coordinates", [None])[0]
            
            if not coordinates:
                print("❌ Could not extract coordinates from URL.")
                return
                
            print(f"📍 Extracted Coordinates: {coordinates}")

        except Exception as e:
            print(f"❌ Search Exception: {e}")
            return

        # --- STEP 2: Query Provider ---
        payload_coords = {
            "query": COORDINATES_QUERY,
            "variables": {
                "filter": {
                    "onlyNap": False,
                    "voltageTypes": ["Niederspannung", "Mittelspannung"],
                    "withRegions": True
                },
                "coordinates": coordinates,
                "withCoordinates": True
            }
        }
        
        try:
            print(f"🌍 Querying Provider for {coordinates}...")
            resp_coords = await client.post(URL, json=payload_coords, headers=HEADERS, timeout=10.0)
            data_coords = resp_coords.json()
            
            if "errors" in data_coords:
                print(f"❌ Provider Query Error: {json.dumps(data_coords['errors'], indent=2)}")
                return

            vnbs = data_coords.get("data", {}).get("vnb_coordinates", {}).get("vnbs", [])
            
            if not vnbs:
                print("❌ No network operator (VNB) found for these coordinates.")
                return
            
            print("\n🏆 FOUND NETWORK OPERATORS:")
            for vnb in vnbs:
                print(f"   - Name: {vnb['name']}")
                print(f"     ID: {vnb['_id']}")
                print(f"     Types: {', '.join(vnb.get('types', []))}")
                print(f"     Voltage: {', '.join(vnb.get('voltageTypes', []))}")
                print("-" * 30)

        except Exception as e:
            print(f"❌ Provider Query Exception: {e}")

if __name__ == "__main__":
    TEST_ADDRESS = "An der Ronne 160, 50859 Köln"
    asyncio.run(find_provider(TEST_ADDRESS))