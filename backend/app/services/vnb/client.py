"""
VNB Digital Module - API Client.

Async client for VNB Digital GraphQL API.
Implements rate limiting to avoid overloading the API.
"""

import asyncio
import time
import urllib.parse

import httpx
import structlog

from app.services.vnb.models import (
    DNODetails,
    LocationResult,
    VNBResult,
    VNBSearchResult,
)
from app.services.vnb.queries import (
    COORDINATES_QUERY,
    SEARCH_QUERY,
    VNB_DETAILS_QUERY,
)

logger = structlog.get_logger()


class VNBDigitalClient:
    """
    Async client for VNB Digital GraphQL API.

    Implements rate limiting to avoid overloading the API.
    Default: 1 request per second, configurable up to 10s between requests.
    """

    API_URL = "https://www.vnbdigital.de/gateway/graphql"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
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

    def _parse_coordinates_from_url(self, url: str) -> str | None:
        """Extract coordinates from URL query parameter."""
        try:
            parsed = urllib.parse.urlparse(url)
            params = urllib.parse.parse_qs(parsed.query)
            return params.get("coordinates", [None])[0]
        except Exception:
            return None

    async def search_address(self, address: str) -> LocationResult | None:
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
        voltage_types: list[str] | None = None,
    ) -> list[VNBResult]:
        """
        Look up VNBs for given coordinates.

        Args:
            coordinates: Coordinates in "lat,lon" format
            voltage_types: Filter by voltage types

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
    ) -> str | None:
        """Full resolution: Address → Coordinates → DNO name."""
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
    ) -> str | None:
        """Direct coordinate-based DNO lookup."""
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

    async def get_vnb_details(self, vnb_id: str) -> DNODetails | None:
        """
        Fetch extended DNO details via VNBdigital GraphQL API.

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
            )

            return DNODetails(
                vnb_id=vnb_id,
                name=vnb_data.get("name", f"VNB {vnb_id}"),
                homepage_url=vnb_data.get("website"),
                phone=vnb_data.get("phone"),
                email=vnb_data.get("contact"),
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

    async def search_vnb(self, name: str) -> list[VNBSearchResult]:
        """Search for VNBs by name for autocomplete/validation."""
        await self._wait_for_rate_limit()

        log = self.log.bind(search_term=name[:50])
        log.info("Searching VNBs by name")

        payload = {
            "query": SEARCH_QUERY,
            "variables": {"searchTerm": name}
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

            results = data.get("data", {}).get("vnb_search", [])

            # Filter to only VNB type results
            vnb_results = []
            for item in results:
                if item.get("type") == "VNB":
                    logo = item.get("logo", {})
                    vnb_results.append(VNBSearchResult(
                        vnb_id=item.get("_id", ""),
                        name=item.get("title", ""),
                        subtitle=item.get("subtitle"),
                        logo_url=logo.get("url") if logo else None,
                    ))

            log.info("VNB search completed", total=len(results), vnbs=len(vnb_results))
            return vnb_results

        except httpx.TimeoutException:
            log.error("Request timeout")
            return []
        except Exception as e:
            log.error("Request failed", error=str(e))
            return []


# Default client instance
vnb_client = VNBDigitalClient(request_delay=1.0)
