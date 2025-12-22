"""
VNB Digital API Client for DNO lookup.

Provides DNO (Verteilnetzbetreiber) resolution via the vnbdigital.de GraphQL API.
Supports two lookup methods:
1. Address-based: Address → Coordinates → DNO
2. Coordinate-based: Coordinates → DNO (direct)

All methods are async to match FastAPI's async architecture.

Rate limiting: Configurable delay between requests (default 1s, can increase to 10s).
"""

import asyncio
import time
import urllib.parse
from dataclasses import dataclass
from typing import Optional

import httpx
import structlog

logger = structlog.get_logger()


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class VNBResult:
    """Result from VNB Digital API lookup."""
    name: str
    vnb_id: str
    types: list[str]  # e.g., ["STROM", "GAS"]
    voltage_types: list[str]  # e.g., ["Niederspannung", "Mittelspannung"]
    logo_url: Optional[str] = None
    official_name: Optional[str] = None  # Full legal name (e.g., "Westnetz GmbH")
    
    @property
    def is_electricity(self) -> bool:
        """Check if this VNB handles electricity."""
        return "STROM" in self.types


@dataclass
class LocationResult:
    """Result from address search."""
    title: str
    coordinates: str  # "lat,lon" format
    url: str


@dataclass
class DNODetails:
    """Extended DNO details from VNBdigital GraphQL API.
    
    Contains homepage URL and contact information for BFS crawl seeding.
    """
    vnb_id: str
    name: str
    homepage_url: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None


# =============================================================================
# GraphQL Queries
# =============================================================================

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

VNB_DETAILS_QUERY = """
query ($id: ID!) {
  vnb_vnb(id: $id) {
    _id
    name
    address
    phone
    website
    contact
  }
}
"""


# =============================================================================
# Async Client
# =============================================================================

class VNBDigitalClient:
    """
    Async client for VNB Digital GraphQL API.
    
    Implements rate limiting to avoid overloading the API.
    Default: 1 request per second, configurable up to 10s between requests.
    
    All methods are async for FastAPI compatibility.
    """
    
    API_URL = "https://www.vnbdigital.de/gateway/graphql"
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Accept": "*/*",
        "Origin": "https://www.vnbdigital.de",
        "Referer": "https://www.vnbdigital.de/",
    }
    
    def __init__(
        self,
        request_delay: float = 1.0,
        timeout: float = 15.0,
    ):
        """
        Initialize the VNB Digital API client.
        
        Args:
            request_delay: Minimum seconds between requests (1.0 - 10.0)
            timeout: Request timeout in seconds
        """
        self.request_delay = max(1.0, min(10.0, request_delay))
        self.timeout = timeout
        self._last_request_time: float = 0.0
        self.log = logger.bind(component="VNBDigitalClient")
    
    async def _wait_for_rate_limit(self) -> None:
        """Wait to respect rate limiting."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.request_delay:
            sleep_time = self.request_delay - elapsed
            self.log.debug("Rate limiting", sleep_seconds=sleep_time)
            await asyncio.sleep(sleep_time)
        self._last_request_time = time.time()
    
    def _parse_coordinates_from_url(self, url: str) -> Optional[str]:
        """Extract coordinates from URL query parameter."""
        try:
            parsed = urllib.parse.urlparse(url)
            params = urllib.parse.parse_qs(parsed.query)
            return params.get("coordinates", [None])[0]
        except Exception:
            return None
    
    async def search_address(self, address: str) -> Optional[LocationResult]:
        """
        Search for an address and return location with coordinates.
        
        Args:
            address: Full address string (e.g., "Musterstr 5, 50667 Köln")
            
        Returns:
            LocationResult with coordinates, or None if not found
        """
        await self._wait_for_rate_limit()
        
        log = self.log.bind(address=address[:50])
        log.info("Searching address")
        
        payload = {
            "query": SEARCH_QUERY,
            "variables": {"searchTerm": address}
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.API_URL,
                    json=payload,
                    headers=self.HEADERS,
                )
                response.raise_for_status()
                data = response.json()
            
            if "errors" in data:
                log.error("GraphQL errors", errors=data["errors"])
                return None
            
            results = data.get("data", {}).get("vnb_search", [])
            if not results:
                log.warning("No location found")
                return None
            
            location = results[0]
            coordinates = self._parse_coordinates_from_url(location.get("url", ""))
            
            if not coordinates:
                log.warning("Could not extract coordinates from URL")
                return None
            
            log.info("Found location", title=location["title"], coords=coordinates)
            
            return LocationResult(
                title=location["title"],
                coordinates=coordinates,
                url=location.get("url", ""),
            )
            
        except httpx.TimeoutException:
            log.error("Request timeout")
            return None
        except Exception as e:
            log.error("Request failed", error=str(e))
            return None
    
    async def lookup_by_coordinates(
        self,
        coordinates: str,
        voltage_types: Optional[list[str]] = None,
    ) -> list[VNBResult]:
        """
        Look up VNBs for given coordinates.
        
        Args:
            coordinates: Coordinates in "lat,lon" format
            voltage_types: Filter by voltage types (default: Niederspannung, Mittelspannung)
            
        Returns:
            List of VNBResult objects
        """
        await self._wait_for_rate_limit()
        
        if voltage_types is None:
            voltage_types = ["Niederspannung", "Mittelspannung"]
        
        log = self.log.bind(coordinates=coordinates)
        log.info("Looking up VNBs by coordinates")
        
        payload = {
            "query": COORDINATES_QUERY,
            "variables": {
                "filter": {
                    "onlyNap": False,
                    "voltageTypes": voltage_types,
                    "withRegions": True,
                },
                "coordinates": coordinates,
                "withCoordinates": True,
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.API_URL,
                    json=payload,
                    headers=self.HEADERS,
                )
                response.raise_for_status()
                data = response.json()
            
            if "errors" in data:
                log.error("GraphQL errors", errors=data["errors"])
                return []
            
            vnbs_data = data.get("data", {}).get("vnb_coordinates", {}).get("vnbs", [])
            
            if not vnbs_data:
                log.warning("No VNBs found for coordinates")
                return []
            
            results = []
            for vnb in vnbs_data:
                logo = vnb.get("logo", {})
                result = VNBResult(
                    name=vnb.get("name", ""),
                    vnb_id=vnb.get("_id", ""),
                    types=vnb.get("types", []),
                    voltage_types=vnb.get("voltageTypes", []),
                    logo_url=logo.get("url") if logo else None,
                )
                results.append(result)
            
            log.info("Found VNBs", count=len(results))
            return results
            
        except httpx.TimeoutException:
            log.error("Request timeout")
            return []
        except Exception as e:
            log.error("Request failed", error=str(e))
            return []
    
    async def resolve_address_to_dno(
        self,
        address: str,
        prefer_electricity: bool = True,
    ) -> Optional[str]:
        """
        Full resolution: Address → Coordinates → DNO name.
        
        This is the main entry point for address-based DNO lookup.
        
        Args:
            address: Full address string
            prefer_electricity: If True, prefer VNBs with STROM type
            
        Returns:
            DNO name if found, None otherwise
        """
        log = self.log.bind(address=address[:50])
        
        location = await self.search_address(address)
        if not location:
            log.warning("Could not resolve address to coordinates")
            return None
        
        vnbs = await self.lookup_by_coordinates(location.coordinates)
        if not vnbs:
            log.warning("No VNBs found for coordinates")
            return None
        
        if prefer_electricity:
            electricity_vnbs = [v for v in vnbs if v.is_electricity]
            if electricity_vnbs:
                vnbs = electricity_vnbs
        
        dno_name = vnbs[0].name
        log.info("Resolved DNO", dno_name=dno_name)
        return dno_name
    
    async def resolve_coordinates_to_dno(
        self,
        latitude: float,
        longitude: float,
        prefer_electricity: bool = True,
    ) -> Optional[str]:
        """
        Direct coordinate-based DNO lookup.
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            prefer_electricity: If True, prefer VNBs with STROM type
            
        Returns:
            DNO name if found, None otherwise
        """
        coordinates = f"{latitude},{longitude}"
        log = self.log.bind(lat=latitude, lon=longitude)
        
        vnbs = await self.lookup_by_coordinates(coordinates)
        if not vnbs:
            log.warning("No VNBs found for coordinates")
            return None
        
        if prefer_electricity:
            electricity_vnbs = [v for v in vnbs if v.is_electricity]
            if electricity_vnbs:
                vnbs = electricity_vnbs
        
        dno_name = vnbs[0].name
        log.info("Resolved DNO from coordinates", dno_name=dno_name)
        return dno_name
    
    async def get_vnb_details(self, vnb_id: str) -> Optional[DNODetails]:
        """
        Fetch extended DNO details via VNBdigital GraphQL API.
        
        Uses the vnb_vnb query to get homepage URL (website), contact email,
        phone, and address directly from the API.
        
        Args:
            vnb_id: VNB ID (e.g., "7399" for RheinNetz)
            
        Returns:
            DNODetails with homepage_url and contact info, or None on error
        """
        await self._wait_for_rate_limit()
        
        log = self.log.bind(vnb_id=vnb_id)
        log.info("Fetching VNB details via GraphQL")
        
        payload = {
            "query": VNB_DETAILS_QUERY,
            "variables": {"id": vnb_id}
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.API_URL,
                    json=payload,
                    headers=self.HEADERS,
                )
                response.raise_for_status()
                data = response.json()
            
            if "errors" in data:
                log.error("GraphQL errors", errors=data["errors"])
                return None
            
            vnb_data = data.get("data", {}).get("vnb_vnb")
            if not vnb_data:
                log.warning("No VNB found for ID")
                return None
            
            log.info(
                "Fetched VNB details",
                name=vnb_data.get("name"),
                website=vnb_data.get("website"),
                has_phone=bool(vnb_data.get("phone")),
                has_contact=bool(vnb_data.get("contact")),
            )
            
            return DNODetails(
                vnb_id=vnb_id,
                name=vnb_data.get("name", f"VNB {vnb_id}"),
                homepage_url=vnb_data.get("website"),
                phone=vnb_data.get("phone"),
                email=vnb_data.get("contact"),  # 'contact' field contains email
                address=vnb_data.get("address"),
            )
            
        except httpx.HTTPStatusError as e:
            log.error("HTTP error fetching VNB details", status=e.response.status_code)
            return None
        except httpx.TimeoutException:
            log.error("Timeout fetching VNB details")
            return None
        except Exception as e:
            log.error("Error fetching VNB details", error=str(e))
            return None


# =============================================================================
# Default client instance
# =============================================================================

# Default client with 1s delay
vnb_client = VNBDigitalClient(request_delay=1.0)