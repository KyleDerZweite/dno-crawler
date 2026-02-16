"""
Data models for MaStR transformation.

Intermediate structures used during parsing and aggregation.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


@dataclass
class DNORecord:
    """Raw DNO data from Marktakteure and Marktrollen files."""
    mastr_nr: str
    name: str = "Unknown"
    roles: list[str] = field(default_factory=list)
    street: Optional[str] = None
    house_nr: Optional[str] = None
    zip_code: Optional[str] = None
    city: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    acer_code: Optional[str] = None
    registration_date: Optional[date] = None
    activity_start: Optional[date] = None
    activity_end: Optional[date] = None


@dataclass
class NetworkRecord:
    """Network data from Netze.xml."""
    mastr_nr: str
    dno_mastr_nr: Optional[str] = None
    name: Optional[str] = None
    sparte: Optional[str] = None  # 20=Strom, 21=Gas
    has_customers: bool = False
    closed_network: bool = False
    bundesland: Optional[str] = None


@dataclass
class ConnectionPointRecord:
    """Connection point data from Netzanschlusspunkte files."""
    mastr_nr: str
    dno_mastr_nr: Optional[str] = None
    network_mastr_nr: Optional[str] = None
    voltage_level_id: Optional[str] = None  # Catalog ID
    net_capacity_kw: Optional[Decimal] = None
    location_mastr_nr: Optional[str] = None


@dataclass
class LocationRecord:
    """Location data from Lokationen files."""
    mastr_nr: str
    location_type: Optional[str] = None
    unit_mastr_nrs: list[str] = field(default_factory=list)
    connection_point_mastr_nrs: list[str] = field(default_factory=list)


@dataclass
class EnergyUnitRecord:
    """Energy unit data (Solar, Wind, Storage, etc.)."""
    mastr_nr: str
    location_mastr_nr: Optional[str] = None
    energy_source: Optional[str] = None  # Catalog ID
    gross_capacity_kw: Optional[Decimal] = None
    net_capacity_kw: Optional[Decimal] = None
    operational_status: Optional[str] = None
    bundesland: Optional[str] = None
    plz: Optional[str] = None
    city: Optional[str] = None
    inbetriebnahme_date: Optional[date] = None
    unit_type: str = "unknown"  # solar, wind, storage, biomass, hydro


@dataclass
class VoltageDistribution:
    """Voltage level distribution for a DNO."""
    ns: int = 0
    umspannung_ns_ms: int = 0
    ms: int = 0
    umspannung_ms_hs: int = 0
    hs: int = 0
    umspannung_hs_hoe: int = 0
    hoe: int = 0
    other: int = 0
    total: int = 0

    @property
    def by_canonical_level(self) -> dict[str, int]:
        return {
            "NS": self.ns,
            "Umspannung NS/MS": self.umspannung_ns_ms,
            "MS": self.ms,
            "Umspannung MS/HS": self.umspannung_ms_hs,
            "HS": self.hs,
            "Umspannung HS/HöS": self.umspannung_hs_hoe,
            "HöS": self.hoe,
        }

    @property
    def by_voltage_legacy(self) -> dict[str, int]:
        """Legacy 4-bucket view for existing integration points."""
        return {
            "ns": self.ns + self.umspannung_ns_ms,
            "ms": self.ms + self.umspannung_ms_hs,
            "hs": self.hs + self.umspannung_hs_hoe,
            "hoe": self.hoe,
            "other": self.other,
        }


@dataclass
class CapacityStats:
    """Installed capacity statistics for a DNO."""
    solar_mw: Decimal = Decimal("0")
    wind_mw: Decimal = Decimal("0")
    storage_mw: Decimal = Decimal("0")
    biomass_mw: Decimal = Decimal("0")
    hydro_mw: Decimal = Decimal("0")
    other_mw: Decimal = Decimal("0")

    @property
    def total_mw(self) -> Decimal:
        return self.solar_mw + self.wind_mw + self.storage_mw + self.biomass_mw + self.hydro_mw + self.other_mw


@dataclass
class UnitCounts:
    """Unit counts for a DNO."""
    solar: int = 0
    wind: int = 0
    storage: int = 0
    biomass: int = 0
    hydro: int = 0


@dataclass
class DNOStats:
    """Pre-computed statistics for a single DNO."""
    mastr_nr: str
    name: str
    
    # Connection points
    connection_points: VoltageDistribution = field(default_factory=VoltageDistribution)
    
    # Networks
    networks_count: int = 0
    has_customers: bool = False
    closed_distribution_network: bool = False
    
    # Capacity
    capacity: CapacityStats = field(default_factory=CapacityStats)
    
    # Unit counts
    units: UnitCounts = field(default_factory=UnitCounts)
    
    # Metadata
    has_full_data: bool = True

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "mastr_nr": self.mastr_nr,
            "name": self.name,
            "connection_points": {
                "total": self.connection_points.total,
                "by_canonical_level": self.connection_points.by_canonical_level,
                "by_voltage": self.connection_points.by_voltage_legacy,
            },
            "networks": {
                "count": self.networks_count,
                "has_customers": self.has_customers,
                "closed_distribution_network": self.closed_distribution_network,
            },
            "installed_capacity_mw": {
                "total": float(self.capacity.total_mw),
                "solar": float(self.capacity.solar_mw),
                "wind": float(self.capacity.wind_mw),
                "storage": float(self.capacity.storage_mw),
                "biomass": float(self.capacity.biomass_mw),
                "hydro": float(self.capacity.hydro_mw),
                "other": float(self.capacity.other_mw),
            },
            "unit_counts": {
                "solar": self.units.solar,
                "wind": self.units.wind,
                "storage": self.units.storage,
                "biomass": self.units.biomass,
                "hydro": self.units.hydro,
            },
            "has_full_data": self.has_full_data,
        }


@dataclass
class ExportMetadata:
    """Metadata for the exported statistics file."""
    mastr_export_date: Optional[date] = None
    processed_at: datetime = field(default_factory=lambda: datetime.utcnow())
    data_quality: str = "full"  # full, partial, sampled
    total_dnos: int = 0
    dnos_with_capacity_data: int = 0
    dnos_with_connection_points: int = 0

    def to_dict(self) -> dict:
        export_date = None
        if self.mastr_export_date:
            if isinstance(self.mastr_export_date, str):
                export_date = self.mastr_export_date
            else:
                export_date = self.mastr_export_date.isoformat()
        return {
            "mastr_export_date": export_date,
            "processed_at": self.processed_at.isoformat() + "Z",
            "data_quality": self.data_quality,
            "total_dnos": self.total_dnos,
            "dnos_with_capacity_data": self.dnos_with_capacity_data,
            "dnos_with_connection_points": self.dnos_with_connection_points,
        }


# Voltage level catalog mapping (MaStR catalog ID -> voltage class)
# Catalog category 15 (Spannungsebene)
# Reference: Katalogwerte.xml where KatalogKategorieId = 15
VOLTAGE_LEVEL_CATALOG: dict[str, str] = {
    "348": "hoe",  # HöS
    "349": "umspannung_hs_hoe",  # Umspannung HS/HöS
    "350": "hs",  # HS
    "351": "umspannung_ms_hs",  # Umspannung MS/HS
    "352": "ms",  # MS
    "353": "umspannung_ns_ms",  # Umspannung NS/MS
    "354": "ns",  # NS
}

# Energy source catalog mapping (MaStR catalog ID -> source type)
# Catalog category 1 (Energieträger)
ENERGY_SOURCE_CATALOG: dict[str, str] = {
    # Solar
    "2495": "solar",  # Solare Strahlungsenergie
    
    # Wind
    "2497": "wind",   # Wind
    
    # Storage
    "2496": "storage", # Speicher
    
    # Biomass
    "2": "biomass",   # Biomasse
    
    # Hydro
    "6": "hydro",     # Geothermie (small, but grouped here)
    "7": "hydro",     # Grubengas
    "2498": "hydro",  # Wasser (from EinheitenWasser)
    
    # Other
    "1": "other",     # andere Gase
    "3": "other",     # Braunkohle
    "5": "other",     # Erdgas
    "8": "other",     # Kernenergie
    "12": "other",    # Mineralölprodukte
    "17": "other",    # Steinkohle
    "18": "other",    # Wärme
}

# Operational status (only count active units)
ACTIVE_STATUS_IDS: set[str] = {
    "35",  # In Betrieb
}

# DNO roles we care about
DNO_ROLES: set[str] = {
    "Anschlussnetzbetreiber",
    "Übertragungsnetzbetreiber",
}
