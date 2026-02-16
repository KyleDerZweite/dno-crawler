"""
XML Parsers for MaStR data files.

Each parser uses iterative XML parsing (iterparse) for memory efficiency
with large files (100MB+).
"""

import glob
import os
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Iterator

from .models import (
    ACTIVE_STATUS_IDS,
    DNO_ROLES,
    DNORecord,
    ConnectionPointRecord,
    EnergyUnitRecord,
    LocationRecord,
    NetworkRecord,
)


def fast_iterparse(file_path: str, tag: str) -> Iterator[ET.Element]:
    """
    Memory-efficient XML parsing using iterparse.
    
    Yields elements matching the tag and clears memory after processing.
    """
    try:
        context = ET.iterparse(file_path, events=("start", "end"))
        _, root = next(context)
        for event, elem in context:
            if event == "end" and elem.tag == tag:
                yield elem
                root.clear()
    except Exception as e:
        raise RuntimeError(f"Error parsing {file_path}: {e}") from e


def safe_decimal(value: str | None) -> Decimal | None:
    """Safely convert string to Decimal."""
    if not value:
        return None
    try:
        return Decimal(value)
    except:
        return None


def safe_date(value: str | None) -> date | None:
    """Safely parse ISO date string."""
    if not value:
        return None
    try:
        if "T" in value:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        return date.fromisoformat(value)
    except:
        return None


# =============================================================================
# DNO Parsers
# =============================================================================

def parse_market_roles(data_dir: str) -> dict[str, DNORecord]:
    """
    Parse MarktakteureUndRollen.xml to identify DNOs.
    
    Returns dict mapping MaStR number to DNORecord.
    """
    roles_file = os.path.join(data_dir, "MarktakteureUndRollen.xml")
    dnos: dict[str, DNORecord] = {}
    
    if not os.path.exists(roles_file):
        raise FileNotFoundError(f"Market roles file not found: {roles_file}")
    
    for elem in fast_iterparse(roles_file, "MarktakteurUndRolle"):
        role = elem.findtext("Marktrolle")
        if role in DNO_ROLES:
            mastr_nr = elem.findtext("MarktakteurMastrNummer")
            if mastr_nr and mastr_nr not in dnos:
                dnos[mastr_nr] = DNORecord(mastr_nr=mastr_nr, roles=[role])
            elif mastr_nr and role not in dnos[mastr_nr].roles:
                dnos[mastr_nr].roles.append(role)
    
    return dnos


def parse_market_actors(data_dir: str, dnos: dict[str, DNORecord]) -> dict[str, DNORecord]:
    """
    Parse Marktakteure_*.xml files to enrich DNO details.
    
    Updates DNORecords in-place with contact information.
    """
    actor_files = sorted(glob.glob(os.path.join(data_dir, "Marktakteure_*.xml")))
    
    for file_path in actor_files:
        print(f"  Parsing {os.path.basename(file_path)}...")
        for elem in fast_iterparse(file_path, "Marktakteur"):
            mastr_nr = elem.findtext("MastrNummer")
            if mastr_nr in dnos:
                dno = dnos[mastr_nr]
                dno.name = elem.findtext("Firmenname") or dno.name
                dno.street = elem.findtext("Strasse") or dno.street
                dno.house_nr = elem.findtext("Hausnummer") or dno.house_nr
                dno.zip_code = elem.findtext("Postleitzahl") or dno.zip_code
                dno.city = elem.findtext("Ort") or dno.city
                dno.email = elem.findtext("Email") or dno.email
                dno.phone = elem.findtext("Telefon") or dno.phone
                dno.acer_code = elem.findtext("AcerCode") or dno.acer_code
                dno.registration_date = safe_date(elem.findtext("RegistrierungsdatumMarktakteur"))
                dno.activity_start = safe_date(elem.findtext("Taetigkeitsbeginn"))
                dno.activity_end = safe_date(elem.findtext("Taetigkeitsende"))
    
    return dnos


# =============================================================================
# Network Parsers
# =============================================================================

def parse_networks(data_dir: str) -> dict[str, NetworkRecord]:
    """
    Parse Netze.xml to get network information.
    
    Returns dict mapping Network.MaStRNummer to NetworkRecord.
    """
    networks_file = os.path.join(data_dir, "Netze.xml")
    networks: dict[str, NetworkRecord] = {}
    
    if not os.path.exists(networks_file):
        print("  Warning: Netze.xml not found, skipping network data")
        return networks
    
    for elem in fast_iterparse(networks_file, "Netz"):
        mastr_nr = elem.findtext("MastrNummer")
        if mastr_nr:
            sparte = elem.findtext("Sparte")
            networks[mastr_nr] = NetworkRecord(
                mastr_nr=mastr_nr,
                dno_mastr_nr=elem.findtext("NetzbetreiberMastrNummer"),
                name=elem.findtext("Bezeichnung"),
                sparte=sparte,
                has_customers=elem.findtext("KundenAngeschlossen") == "1",
                closed_network=elem.findtext("GeschlossenesVerteilnetz") == "1",
                bundesland=elem.findtext("Bundesland"),
            )
    
    return networks


def build_dno_network_map(
    networks: dict[str, NetworkRecord],
    dnos: dict[str, DNORecord],
) -> dict[str, list[NetworkRecord]]:
    """
    Build mapping from DNO MaStR number to their networks.
    
    Returns dict mapping DNO MaStR number to list of NetworkRecords.
    """
    dno_networks: dict[str, list[NetworkRecord]] = defaultdict(list)
    
    for network in networks.values():
        if network.dno_mastr_nr and network.dno_mastr_nr in dnos:
            dno_networks[network.dno_mastr_nr].append(network)
    
    return dno_networks


# =============================================================================
# Connection Point Parsers
# =============================================================================

def parse_connection_points(data_dir: str) -> tuple[dict[str, ConnectionPointRecord], dict[str, list[str]]]:
    """
    Parse Netzanschlusspunkte_*.xml files.
    
    Returns:
        - Dict mapping ConnectionPoint.MaStRNummer to ConnectionPointRecord
        - Dict mapping DNO MaStR number to list of connection point MaStR numbers
    """
    cp_files = sorted(glob.glob(os.path.join(data_dir, "Netzanschlusspunkte_*.xml")))
    
    connection_points: dict[str, ConnectionPointRecord] = {}
    dno_to_cps: dict[str, list[str]] = defaultdict(list)
    
    for file_path in cp_files:
        print(f"  Parsing {os.path.basename(file_path)}...")
        for elem in fast_iterparse(file_path, "Netzanschlusspunkt"):
            mastr_nr = elem.findtext("NetzanschlusspunktMastrNummer")
            dno_mastr_nr = elem.findtext("NetzbetreiberMaStRNummer")
            
            if mastr_nr:
                cp = ConnectionPointRecord(
                    mastr_nr=mastr_nr,
                    dno_mastr_nr=dno_mastr_nr,
                    network_mastr_nr=elem.findtext("NetzMaStRNummer"),
                    voltage_level_id=elem.findtext("Spannungsebene"),
                    net_capacity_kw=safe_decimal(elem.findtext("Nettoengpassleistung")),
                    location_mastr_nr=elem.findtext("LokationMaStRNummer"),
                )
                connection_points[mastr_nr] = cp
                
                if dno_mastr_nr:
                    dno_to_cps[dno_mastr_nr].append(mastr_nr)
    
    return connection_points, dno_to_cps


# =============================================================================
# Location Parsers
# =============================================================================

def parse_locations(data_dir: str) -> dict[str, LocationRecord]:
    """
    Parse Lokationen_*.xml files.
    
    Returns dict mapping Location.MaStRNummer to LocationRecord.
    """
    loc_files = sorted(glob.glob(os.path.join(data_dir, "Lokationen_*.xml")))
    
    locations: dict[str, LocationRecord] = {}
    
    for file_path in loc_files:
        print(f"  Parsing {os.path.basename(file_path)}...")
        for elem in fast_iterparse(file_path, "Lokation"):
            mastr_nr = elem.findtext("MastrNummer")
            if mastr_nr:
                # Parse verknuepfte Einheiten (can be multiple, semicolon-separated in newer exports)
                unit_nrs = elem.findtext("VerknuepfteEinheitenMaStRNummern") or ""
                cp_nrs = elem.findtext("NetzanschlusspunkteMaStRNummern") or ""
                
                locations[mastr_nr] = LocationRecord(
                    mastr_nr=mastr_nr,
                    location_type=elem.findtext("Lokationtyp"),
                    unit_mastr_nrs=[u.strip() for u in unit_nrs.split(";") if u.strip()],
                    connection_point_mastr_nrs=[c.strip() for c in cp_nrs.split(";") if c.strip()],
                )
    
    return locations


def build_location_to_dno_map(
    locations: dict[str, LocationRecord],
    connection_points: dict[str, ConnectionPointRecord],
) -> dict[str, str]:
    """
    Build mapping from Location MaStR number to DNO MaStR number.
    
    Uses the ConnectionPoint -> DNO link.
    """
    loc_to_dno: dict[str, str] = {}
    
    for loc in locations.values():
        for cp_nr in loc.connection_point_mastr_nrs:
            if cp_nr in connection_points:
                cp = connection_points[cp_nr]
                if cp.dno_mastr_nr:
                    loc_to_dno[loc.mastr_nr] = cp.dno_mastr_nr
                    break
    
    return loc_to_dno


# =============================================================================
# Energy Unit Parsers
# =============================================================================

def parse_energy_units(
    data_dir: str,
    loc_to_dno: dict[str, str],
    include_inactive: bool = False,
) -> dict[str, list[EnergyUnitRecord]]:
    """
    Parse all energy unit files and aggregate by DNO.
    
    Returns dict mapping DNO MaStR number to list of EnergyUnitRecords.
    
    Args:
        data_dir: Path to MaStR data directory
        loc_to_dno: Mapping from Location MaStR number to DNO MaStR number
        include_inactive: Whether to include inactive/in planning units
    """
    dno_units: dict[str, list[EnergyUnitRecord]] = defaultdict(list)
    stats = defaultdict(int)
    
    # Define unit file patterns and their types
    unit_configs = [
        ("EinheitenSolar_*.xml", "solar"),
        ("EinheitenWind.xml", "wind"),
        ("EinheitenStromSpeicher_*.xml", "storage"),
        ("EinheitenBiomasse.xml", "biomass"),
        ("EinheitenWasser.xml", "hydro"),
    ]
    
    for pattern, unit_type in unit_configs:
        files = sorted(glob.glob(os.path.join(data_dir, pattern)))
        
        for file_path in files:
            print(f"  Parsing {os.path.basename(file_path)}...")
            
            # Determine tag name based on unit type
            if unit_type == "solar":
                tag = "EinheitSolar"
            elif unit_type == "wind":
                tag = "EinheitWind"
            elif unit_type == "storage":
                tag = "EinheitStromSpeicher"
            elif unit_type == "biomass":
                tag = "EinheitBiomasse"
            elif unit_type == "hydro":
                tag = "EinheitWasser"
            else:
                tag = "Einheit"
            
            for elem in fast_iterparse(file_path, tag):
                # Check operational status
                status = elem.findtext("EinheitBetriebsstatus")
                if not include_inactive and status not in ACTIVE_STATUS_IDS:
                    stats["skipped_inactive"] += 1
                    continue
                
                # Get location and resolve to DNO
                loc_nr = elem.findtext("LokationMaStRNummer")
                dno_nr = loc_to_dno.get(loc_nr) if loc_nr else None
                
                if not dno_nr:
                    stats["no_dno"] += 1
                    continue
                
                # Extract unit data
                unit = EnergyUnitRecord(
                    mastr_nr=elem.findtext("EinheitMastrNummer") or "",
                    location_mastr_nr=loc_nr,
                    energy_source=elem.findtext("Energietraeger"),
                    gross_capacity_kw=safe_decimal(elem.findtext("Bruttoleistung")),
                    net_capacity_kw=safe_decimal(elem.findtext("Nettonennleistung")),
                    operational_status=status,
                    bundesland=elem.findtext("Bundesland"),
                    plz=elem.findtext("Postleitzahl"),
                    city=elem.findtext("Ort"),
                    inbetriebnahme_date=safe_date(elem.findtext("Inbetriebnahmedatum")),
                    unit_type=unit_type,
                )
                
                dno_units[dno_nr].append(unit)
                stats[unit_type] += 1
    
    print(f"  Unit stats: {dict(stats)}")
    return dno_units
