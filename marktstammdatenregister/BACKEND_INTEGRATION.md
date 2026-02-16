# Backend Integration Guide

This document describes the changes needed in the DNO Crawler backend to support MaStR statistics.

## Files to Modify

Canonical voltage levels used for MaStR connection points are:

`NS`, `Umspannung NS/MS`, `MS`, `Umspannung MS/HS`, `HS`, `Umspannung HS/HöS`, `HöS`.

For backward compatibility, API and import paths still expose/accept aggregated legacy buckets (`ns`, `ms`, `hs`, `hoe`) in addition to canonical levels.

### 1. `backend/app/db/source_models.py`

Add the following fields to the `DNOMastrData` class:

```python
# ============================================================================
# MaStR Statistics Fields
# ============================================================================

# Connection points (from Netzanschlusspunkte)
connection_points_total: Mapped[int | None] = mapped_column(Integer)
connection_points_by_level: Mapped[dict | None] = mapped_column(JSON)
connection_points_ns: Mapped[int | None] = mapped_column(Integer)     # Niederspannung
connection_points_ms: Mapped[int | None] = mapped_column(Integer)     # Mittelspannung
connection_points_hs: Mapped[int | None] = mapped_column(Integer)     # Hochspannung
connection_points_hoe: Mapped[int | None] = mapped_column(Integer)    # Höchstspannung

# Network info (from Netze)
networks_count: Mapped[int | None] = mapped_column(Integer)
has_customers: Mapped[bool | None] = mapped_column(Boolean)
closed_distribution_network: Mapped[bool | None] = mapped_column(Boolean)

# Installed capacity in MW (from Einheiten)
total_capacity_mw: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
solar_capacity_mw: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
wind_capacity_mw: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
storage_capacity_mw: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
biomass_capacity_mw: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
hydro_capacity_mw: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))

# Unit counts
solar_units: Mapped[int | None] = mapped_column(Integer)
wind_units: Mapped[int | None] = mapped_column(Integer)
storage_units: Mapped[int | None] = mapped_column(Integer)

# Metadata
stats_computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
stats_data_quality: Mapped[str | None] = mapped_column(String(20))  # full, partial, sampled
```

### 2. `backend/app/db/models.py`

Add denormalized quick-access fields to `DNOModel`:

```python
# -------------------------------------------------------------------------
# MaStR Statistics (denormalized for sorting/filtering)
# -------------------------------------------------------------------------
connection_points_count: Mapped[int | None] = mapped_column(Integer)
total_capacity_mw: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
```

Add convenience properties:

```python
@property
def stats_available(self) -> bool:
    """Check if MaStR statistics are available."""
    return self.mastr_data is not None and self.mastr_data.connection_points_total is not None

@property
def display_capacity(self) -> dict | None:
    """Get capacity breakdown for display."""
    if not self.mastr_data or not self.mastr_data.total_capacity_mw:
        return None
    return {
        "total_mw": float(self.mastr_data.total_capacity_mw),
        "solar_mw": float(self.mastr_data.solar_capacity_mw or 0),
        "wind_mw": float(self.mastr_data.wind_capacity_mw or 0),
        "storage_mw": float(self.mastr_data.storage_capacity_mw or 0),
        "other_mw": float(
            (self.mastr_data.biomass_capacity_mw or 0) +
            (self.mastr_data.hydro_capacity_mw or 0)
        ),
    }

@property
def display_voltage_distribution(self) -> dict | None:
    """Get voltage level distribution for display."""
    if not self.mastr_data or not self.mastr_data.connection_points_total:
        return None
    return {
        "total": self.mastr_data.connection_points_total,
        "ns": self.mastr_data.connection_points_ns or 0,
        "ms": self.mastr_data.connection_points_ms or 0,
        "hs": self.mastr_data.connection_points_hs or 0,
        "hoe": self.mastr_data.connection_points_hoe or 0,
    }
```

### 3. `backend/app/db/seeder.py`

Update `upsert_mastr_data()` function:

```python
async def upsert_mastr_data(db: AsyncSession, dno: DNOModel, record: dict[str, Any]) -> None:
    """Create or update MaStR source data for a DNO."""
    # ... existing code ...

    # Update MaStR statistics (new section)
    stats = record.get("stats", {})
    
    # Connection points
    cp_data = stats.get("connection_points", {})
    mastr.connection_points_total = cp_data.get("total")
    levels = cp_data.get("by_canonical_level", {})
    # Keep full 7-level distribution
    mastr.connection_points_by_level = levels
    # Keep aggregated legacy buckets for existing UI/queries
    # NS bucket = NS + Umspannung NS/MS
    # MS bucket = MS + Umspannung MS/HS
    # HS bucket = HS + Umspannung HS/HöS
    # HöS bucket = HöS
    voltage = cp_data.get("by_voltage", {})  # fallback compatibility
    mastr.connection_points_ns = voltage.get("ns")
    mastr.connection_points_ms = voltage.get("ms")
    mastr.connection_points_hs = voltage.get("hs")
    mastr.connection_points_hoe = voltage.get("hoe")
    
    # Networks
    net_data = stats.get("networks", {})
    mastr.networks_count = net_data.get("count")
    mastr.has_customers = net_data.get("has_customers")
    mastr.closed_distribution_network = net_data.get("closed_distribution_network")
    
    # Capacity
    cap_data = stats.get("installed_capacity_mw", {})
    mastr.total_capacity_mw = cap_data.get("total")
    mastr.solar_capacity_mw = cap_data.get("solar")
    mastr.wind_capacity_mw = cap_data.get("wind")
    mastr.storage_capacity_mw = cap_data.get("storage")
    mastr.biomass_capacity_mw = cap_data.get("biomass")
    mastr.hydro_capacity_mw = cap_data.get("hydro")
    
    # Unit counts
    units_data = stats.get("unit_counts", {})
    mastr.solar_units = units_data.get("solar")
    mastr.wind_units = units_data.get("wind")
    mastr.storage_units = units_data.get("storage")
    
    # Metadata
    mastr.stats_computed_at = datetime.now(UTC)
    mastr.stats_data_quality = stats.get("has_full_data") and "full" or "partial"


async def upsert_dno_from_seed(db: AsyncSession, record: dict[str, Any]) -> str:
    # ... existing code ...
    
    # After updating MaStR data, update denormalized fields
    if dno.mastr_data:
        dno.connection_points_count = dno.mastr_data.connection_points_total
        dno.total_capacity_mw = dno.mastr_data.total_capacity_mw
```

### 4. `backend/app/api/routes/dnos/schemas.py`

Add statistics to DNO response schema:

```python
class DNOStatsSchema(BaseModel):
    """MaStR statistics for a DNO."""
    connection_points: dict | None
    networks: dict | None
    installed_capacity_mw: dict | None
    unit_counts: dict | None
    data_quality: str | None
    computed_at: datetime | None


class DNODetailSchema(BaseModel):
    # ... existing fields ...
    
    # Add statistics
    stats: DNOStatsSchema | None
```

### 5. Database Migration

Generate and apply migration:

```bash
cd backend
alembic revision --autogenerate -m "add mastr statistics fields to dno_mastr_data"
alembic upgrade head
```

## API Response Example

After integration, the DNO detail API (`GET /api/v1/dnos/{id}`) includes canonical and compatibility fields:

```json
{
  "id": 123,
  "name": "Stuttgart Netze GmbH",
  "slug": "stuttgart-netze-gmbh",
  "stats": {
    "connection_points": {
      "total": 847,
      "by_canonical_level": {
        "NS": 780,
        "Umspannung NS/MS": 20,
        "MS": 40,
        "Umspannung MS/HS": 3,
        "HS": 2,
        "Umspannung HS/HöS": 1,
        "HöS": 1
      },
      "by_voltage": {
        "ns": 800,
        "ms": 45,
        "hs": 2,
        "hoe": 0
      }
    },
    "networks": {
      "count": 1,
      "has_customers": true,
      "closed_distribution_network": false
    },
    "installed_capacity_mw": {
      "total": 125.5,
      "solar": 95.2,
      "wind": 15.3,
      "storage": 10.0,
      "biomass": 3.0,
      "hydro": 2.0
    },
    "unit_counts": {
      "solar": 1250,
      "wind": 5,
      "storage": 80
    },
    "data_quality": "full",
    "computed_at": "2025-02-15T10:30:00Z"
  }
}
```

## Frontend Integration

The frontend can display statistics on the DNO detail page:

```tsx
// Example component
function DNOStatsCard({ dno }: { dno: DNODetail }) {
  if (!dno.stats) return null;
  
  return (
    <Card>
      <CardHeader>
        <CardTitle>Network Statistics (MaStR)</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-sm text-muted-foreground">Connection Points</p>
            <p className="text-2xl font-bold">
              {dno.stats.connection_points?.total?.toLocaleString() || 'N/A'}
            </p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Installed Capacity</p>
            <p className="text-2xl font-bold">
              {dno.stats.installed_capacity_mw?.total?.toFixed(1) || 'N/A'} MW
            </p>
          </div>
        </div>
        
        {/* Capacity breakdown chart */}
        {/* Voltage distribution chart */}
      </CardContent>
    </Card>
  );
}
```

## Update Schedule

To update MaStR statistics:

1. Download latest MaStR export from Bundesnetzagentur
2. Run transformation: `python transform_mastr.py --data-dir ./data --output dno_stats.json`
3. Import (canonical backend script): `cd backend && python scripts/import_mastr_stats.py --file ../marktstammdatenregister/dno_stats.json`

Recommended frequency: Quarterly or when Bundesnetzagentur publishes major updates.
