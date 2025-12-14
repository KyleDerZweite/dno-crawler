"""
VNB Digital API Client for DNO lookup.

Provides DNO (Verteilnetzbetreiber) resolution via the vnbdigital.de GraphQL API.
Supports two lookup methods:
1. Address-based: Address → Coordinates → DNO
2. Coordinate-based: Coordinates → DNO (direct)

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


# =============================================================================
# Main Client
# =============================================================================

class VNBDigitalClient:
    """
    Client for VNB Digital GraphQL API.
    
    Implements rate limiting to avoid overloading the API.
    Default: 1 request per second, configurable up to 10s between requests.
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
    
    def _wait_for_rate_limit(self) -> None:
        """Wait to respect rate limiting."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.request_delay:
            sleep_time = self.request_delay - elapsed
            self.log.debug("Rate limiting", sleep_seconds=sleep_time)
            time.sleep(sleep_time)
        self._last_request_time = time.time()
    
    async def _wait_for_rate_limit_async(self) -> None:
        """Async version of rate limit wait."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.request_delay:
            sleep_time = self.request_delay - elapsed
            self.log.debug("Rate limiting (async)", sleep_seconds=sleep_time)
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
    
    def search_address(self, address: str) -> Optional[LocationResult]:
        """
        Search for an address and return location with coordinates.
        
        Args:
            address: Full address string (e.g., "Musterstr 5, 50667 Köln")
            
        Returns:
            LocationResult with coordinates, or None if not found
        """
        self._wait_for_rate_limit()
        
        log = self.log.bind(address=address[:50])
        log.info("Searching address")
        
        payload = {
            "query": SEARCH_QUERY,
            "variables": {"searchTerm": address}
        }
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
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
            
            # Get first result
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
    
    def lookup_by_coordinates(
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
        self._wait_for_rate_limit()
        
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
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
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
    
    def resolve_address_to_dno(
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
        
        # Step 1: Get coordinates from address
        location = self.search_address(address)
        if not location:
            log.warning("Could not resolve address to coordinates")
            return None
        
        # Step 2: Lookup VNBs by coordinates
        vnbs = self.lookup_by_coordinates(location.coordinates)
        if not vnbs:
            log.warning("No VNBs found for coordinates")
            return None
        
        # Step 3: Select best VNB
        if prefer_electricity:
            electricity_vnbs = [v for v in vnbs if v.is_electricity]
            if electricity_vnbs:
                vnbs = electricity_vnbs
        
        # Return first (most relevant) VNB name
        dno_name = vnbs[0].name
        log.info("Resolved DNO", dno_name=dno_name)
        return dno_name
    
    def resolve_coordinates_to_dno(
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
        
        vnbs = self.lookup_by_coordinates(coordinates)
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


# =============================================================================
# Async Variants
# =============================================================================

class AsyncVNBDigitalClient(VNBDigitalClient):
    """Async version of VNB Digital API client."""
    
    async def search_address_async(self, address: str) -> Optional[LocationResult]:
        """Async version of search_address."""
        await self._wait_for_rate_limit_async()
        
        log = self.log.bind(address=address[:50])
        log.info("Searching address (async)")
        
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
    
    async def lookup_by_coordinates_async(
        self,
        coordinates: str,
        voltage_types: Optional[list[str]] = None,
    ) -> list[VNBResult]:
        """Async version of lookup_by_coordinates."""
        await self._wait_for_rate_limit_async()
        
        if voltage_types is None:
            voltage_types = ["Niederspannung", "Mittelspannung"]
        
        log = self.log.bind(coordinates=coordinates)
        log.info("Looking up VNBs by coordinates (async)")
        
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
    
    async def resolve_address_to_dno_async(
        self,
        address: str,
        prefer_electricity: bool = True,
    ) -> Optional[str]:
        """Async version of resolve_address_to_dno."""
        log = self.log.bind(address=address[:50])
        
        location = await self.search_address_async(address)
        if not location:
            log.warning("Could not resolve address to coordinates")
            return None
        
        vnbs = await self.lookup_by_coordinates_async(location.coordinates)
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
    
    async def resolve_coordinates_to_dno_async(
        self,
        latitude: float,
        longitude: float,
        prefer_electricity: bool = True,
    ) -> Optional[str]:
        """Async version of resolve_coordinates_to_dno."""
        coordinates = f"{latitude},{longitude}"
        log = self.log.bind(lat=latitude, lon=longitude)
        
        vnbs = await self.lookup_by_coordinates_async(coordinates)
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


# =============================================================================
# Singleton instance for easy import
# =============================================================================

# Default client with 1s delay
vnb_client = VNBDigitalClient(request_delay=1.0)
async_vnb_client = AsyncVNBDigitalClient(request_delay=1.0)
