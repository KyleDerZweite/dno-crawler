"""
VNB Digital Module - Data Models.

Data classes for VNB Digital API responses.
"""

from dataclasses import dataclass


@dataclass
class VNBResult:
    """Result from VNB Digital API lookup."""
    name: str
    vnb_id: str
    types: list[str]  # e.g., ["STROM", "GAS"]
    voltage_types: list[str]  # e.g., ["Niederspannung", "Mittelspannung"]
    logo_url: str | None = None
    official_name: str | None = None  # Full legal name (e.g., "Westnetz GmbH")

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
    homepage_url: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None


@dataclass
class VNBSearchResult:
    """Result from VNB name search for autocomplete."""
    vnb_id: str
    name: str
    subtitle: str | None = None  # Often contains official legal name (e.g., "GmbH")
    logo_url: str | None = None
