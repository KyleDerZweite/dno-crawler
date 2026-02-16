"""
Aggregators for computing DNO statistics from parsed data.
"""

from decimal import Decimal
from typing import Any

from .models import (
    CapacityStats,
    DNORecord,
    DNOStats,
    DNOStats as DNOStatsModel,
    ENERGY_SOURCE_CATALOG,
    EnergyUnitRecord,
    ExportMetadata,
    NetworkRecord,
    UnitCounts,
    VoltageDistribution,
    VOLTAGE_LEVEL_CATALOG,
)
from .parsers import (
    ConnectionPointRecord,
    build_dno_network_map,
)


def aggregate_connection_points(
    dno_to_cps: dict[str, list[str]],
    connection_points: dict[str, ConnectionPointRecord],
    dnos: dict[str, DNORecord],
) -> dict[str, VoltageDistribution]:
    """
    Aggregate connection points by DNO and voltage level.
    
    Returns dict mapping DNO MaStR number to VoltageDistribution.
    """
    result: dict[str, VoltageDistribution] = {}
    
    for dno_nr, cp_nrs in dno_to_cps.items():
        if dno_nr not in dnos:
            continue
        
        dist = VoltageDistribution()
        
        for cp_nr in cp_nrs:
            cp = connection_points.get(cp_nr)
            if not cp:
                continue
            
            # Map voltage level ID to category
            voltage_cat = VOLTAGE_LEVEL_CATALOG.get(cp.voltage_level_id or "", "other")
            
            if voltage_cat == "ns":
                dist.ns += 1
            elif voltage_cat == "umspannung_ns_ms":
                dist.umspannung_ns_ms += 1
            elif voltage_cat == "ms":
                dist.ms += 1
            elif voltage_cat == "umspannung_ms_hs":
                dist.umspannung_ms_hs += 1
            elif voltage_cat == "hs":
                dist.hs += 1
            elif voltage_cat == "umspannung_hs_hoe":
                dist.umspannung_hs_hoe += 1
            elif voltage_cat == "hoe":
                dist.hoe += 1
            else:
                dist.other += 1
            
            dist.total += 1
        
        result[dno_nr] = dist
    
    return result


def aggregate_networks(
    networks: dict[str, NetworkRecord],
    dnos: dict[str, DNORecord],
) -> dict[str, dict[str, Any]]:
    """
    Aggregate network information by DNO.
    
    Returns dict mapping DNO MaStR number to network stats dict.
    """
    dno_networks = build_dno_network_map(networks, dnos)
    result: dict[str, dict[str, Any]] = {}
    
    for dno_nr, net_list in dno_networks.items():
        # Filter to electricity networks (Sparte = 20)
        electricity_networks = [n for n in net_list if n.sparte == "20"]
        
        result[dno_nr] = {
            "count": len(electricity_networks),
            "has_customers": any(n.has_customers for n in electricity_networks),
            "closed_distribution_network": any(n.closed_network for n in electricity_networks),
        }
    
    return result


def aggregate_capacity(
    dno_units: dict[str, list[EnergyUnitRecord]],
) -> dict[str, CapacityStats]:
    """
    Aggregate installed capacity by DNO and energy source.
    
    Returns dict mapping DNO MaStR number to CapacityStats.
    """
    result: dict[str, CapacityStats] = {}
    
    for dno_nr, units in dno_units.items():
        stats = CapacityStats()
        
        for unit in units:
            # Get capacity in MW (convert from kW)
            capacity_kw = unit.gross_capacity_kw or Decimal("0")
            capacity_mw = capacity_kw / Decimal("1000")
            
            # Map energy source to category
            source_cat = ENERGY_SOURCE_CATALOG.get(unit.energy_source or "", "other")
            
            if source_cat == "solar":
                stats.solar_mw += capacity_mw
            elif source_cat == "wind":
                stats.wind_mw += capacity_mw
            elif source_cat == "storage":
                stats.storage_mw += capacity_mw
            elif source_cat == "biomass":
                stats.biomass_mw += capacity_mw
            elif source_cat == "hydro":
                stats.hydro_mw += capacity_mw
            else:
                stats.other_mw += capacity_mw
        
        result[dno_nr] = stats
    
    return result


def aggregate_unit_counts(
    dno_units: dict[str, list[EnergyUnitRecord]],
) -> dict[str, UnitCounts]:
    """
    Count units by DNO and type.
    
    Returns dict mapping DNO MaStR number to UnitCounts.
    """
    result: dict[str, UnitCounts] = {}
    
    for dno_nr, units in dno_units.items():
        counts = UnitCounts()
        
        for unit in units:
            if unit.unit_type == "solar":
                counts.solar += 1
            elif unit.unit_type == "wind":
                counts.wind += 1
            elif unit.unit_type == "storage":
                counts.storage += 1
            elif unit.unit_type == "biomass":
                counts.biomass += 1
            elif unit.unit_type == "hydro":
                counts.hydro += 1
        
        result[dno_nr] = counts
    
    return result


def aggregate_dno_stats(
    dnos: dict[str, DNORecord],
    connection_points: dict[str, ConnectionPointRecord],
    dno_to_cps: dict[str, list[str]],
    networks: dict[str, NetworkRecord],
    dno_units: dict[str, list[EnergyUnitRecord]],
) -> tuple[dict[str, DNOStats], ExportMetadata]:
    """
    Perform all aggregations and create final DNOStats objects.
    
    Returns:
        - Dict mapping DNO MaStR number to DNOStats
        - ExportMetadata with processing statistics
    """
    # Run aggregations
    cp_stats = aggregate_connection_points(dno_to_cps, connection_points, dnos)
    network_stats = aggregate_networks(networks, dnos)
    capacity_stats = aggregate_capacity(dno_units)
    unit_counts = aggregate_unit_counts(dno_units)
    
    # Build final stats objects
    result: dict[str, DNOStats] = {}
    
    for dno_nr, dno in dnos.items():
        stats = DNOStats(
            mastr_nr=dno_nr,
            name=dno.name,
        )
        
        # Connection points
        if dno_nr in cp_stats:
            stats.connection_points = cp_stats[dno_nr]
        
        # Networks
        if dno_nr in network_stats:
            net_data = network_stats[dno_nr]
            stats.networks_count = net_data["count"]
            stats.has_customers = net_data["has_customers"]
            stats.closed_distribution_network = net_data["closed_distribution_network"]
        
        # Capacity
        if dno_nr in capacity_stats:
            stats.capacity = capacity_stats[dno_nr]
        
        # Unit counts
        if dno_nr in unit_counts:
            stats.units = unit_counts[dno_nr]
        
        # Mark as having full data if we have both CP and capacity data
        stats.has_full_data = (
            stats.connection_points.total > 0 and
            stats.capacity.total_mw > 0
        )
        
        result[dno_nr] = stats
    
    # Create metadata
    metadata = ExportMetadata(
        total_dnos=len(result),
        dnos_with_connection_points=sum(1 for s in result.values() if s.connection_points.total > 0),
        dnos_with_capacity_data=sum(1 for s in result.values() if s.capacity.total_mw > 0),
    )
    
    return result, metadata
