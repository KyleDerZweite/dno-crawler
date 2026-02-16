# MaStR Data Transformation Pipeline

This directory contains scripts for transforming Marktstammdatenregister (MaStR) XML exports into pre-computed DNO statistics for the DNO Crawler application.

## Overview

The Bundesnetzagentur publishes the MaStR (Marktstammdatenregister) as XML exports containing data about:
- Distribution Network Operators (DNOs)
- Network connection points
- Energy generation units (solar, wind, storage, etc.)
- Networks and locations

This pipeline transforms raw XML data into structured JSON statistics that can be imported into the DNO Crawler database.

## Directory Structure

```
marktstammdatenregister/
├── transform_mastr.py       # Main transformation script
├── import_mastr_stats.py    # Compatibility wrapper to backend/scripts/import_mastr_stats.py
├── mastr/                   # Python module
│   ├── __init__.py
│   ├── models.py            # Data classes for intermediate structures
│   ├── parsers.py           # XML parsers for each file type
│   └── aggregators.py       # Statistics aggregation logic
├── data/                    # MaStR XML files (downloaded separately)
│   ├── MarktakteureUndRollen.xml
│   ├── Marktakteure_*.xml
│   ├── Netze.xml
│   ├── Netzanschlusspunkte_*.xml
│   ├── Lokationen_*.xml
│   ├── EinheitenSolar_*.xml
│   └── ...
└── README.md               # This file
```

## Current Pipeline (Recommended)

Use this sequence for the current, supported MaStR integration.

### 1. Prepare raw export locally

1. Download MaStR Gesamtdatenexport.
2. Extract files into `marktstammdatenregister/data/`.

Raw/generated data files are intentionally ignored from git in this folder.

### 2. Transform XML to JSON stats

From repository root:

```bash
# Full run (recommended)
python marktstammdatenregister/transform_mastr.py \
  --data-dir ./marktstammdatenregister/data \
  --output ./marktstammdatenregister/dno_stats.json

# Quick run (no energy unit/capacity parsing)
python marktstammdatenregister/transform_mastr.py \
  --data-dir ./marktstammdatenregister/data \
  --output ./marktstammdatenregister/dno_stats.json \
  --quick
```

### 3. Apply backend migrations

```bash
cd backend
alembic upgrade head
```

### 4. Import MaStR stats into database

```bash
cd backend

# Dry run first
python scripts/import_mastr_stats.py \
  --file ../marktstammdatenregister/dno_stats.json \
  --dry-run

# Actual import
python scripts/import_mastr_stats.py \
  --file ../marktstammdatenregister/dno_stats.json
```

### 5. Verify API output

Verify one DNO in `GET /api/v1/dnos/{id}` has:
- `stats.connection_points.by_canonical_level` (7 levels)
- `stats.connection_points.by_voltage` (legacy compatibility buckets)

## Usage

### Step 1: Download MaStR Data

1. Visit https://www.marktstammdatenregister.de/MaStR/Datendownload
2. Request a "Gesamtdatenexport" (full data export)
3. Download and extract the ZIP file
4. Place XML files in the `data/` directory

### Step 2: Transform Data

Run the transformation script:

```bash
# Full transformation (includes energy unit capacity)
# Takes 1-2 hours depending on hardware
python transform_mastr.py --data-dir ./data --output dno_stats.json

# Quick mode (skip energy units, connection points only)
# Takes 10-30 minutes
python transform_mastr.py --data-dir ./data --output dno_stats.json --quick
```

**Output format** (`dno_stats.json`):

```json
{
  "metadata": {
    "mastr_export_date": "2025-01-01",
    "processed_at": "2025-02-15T10:30:00Z",
    "data_quality": "full",
    "total_dnos": 1697,
    "dnos_with_connection_points": 890,
    "dnos_with_capacity_data": 890
  },
  "dnos": {
    "SNB947592865054": {
      "mastr_nr": "SNB947592865054",
      "name": "Stuttgart Netze GmbH",
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
          "ms": 43,
          "hs": 3,
          "hoe": 1,
          "other": 0
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
        "storage": 80,
        "biomass": 0,
        "hydro": 0
      },
      "has_full_data": true
    }
  }
}
```

### Step 3: Import into Database

**Option A: Merge into Seed Data (recommended for deployment)**

Copy `dno_stats.json` to the DNO Crawler seed data directory and rebuild the parquet file:

```bash
cp dno_stats.json /path/to/dno-crawler/data/seed-data/
cd /path/to/dno-crawler
# Rebuild parquet (or use your existing build script)
```

**Option B: Direct Database Import**

Run from the backend directory:

```bash
cd /path/to/dno-crawler/backend

# Dry run first
python scripts/import_mastr_stats.py \
    --file ../marktstammdatenregister/dno_stats.json \
    --dry-run

# Actual import
python scripts/import_mastr_stats.py \
    --file ../marktstammdatenregister/dno_stats.json
```

## Data Fields

### Connection Points

Canonical MaStR levels used by this pipeline:

1. `NS`
2. `Umspannung NS/MS`
3. `MS`
4. `Umspannung MS/HS`
5. `HS`
6. `Umspannung HS/HöS`
7. `HöS`

| Field | Description | Source |
|-------|-------------|--------|
| `connection_points_total` | Total connection points | Netzanschlusspunkte count |
| `connection_points_by_level` | Full 7-level canonical distribution | MaStR Spannungsebene catalog |
| `connection_points_ns` | Aggregate `NS + Umspannung NS/MS` | Derived compatibility field |
| `connection_points_ms` | Aggregate `MS + Umspannung MS/HS` | Derived compatibility field |
| `connection_points_hs` | Aggregate `HS + Umspannung HS/HöS` | Derived compatibility field |
| `connection_points_hoe` | Aggregate `HöS` | Derived compatibility field |

### Networks

| Field | Description | Source |
|-------|-------------|--------|
| `networks_count` | Number of electricity networks | Netze count (Sparte=20) |
| `has_customers` | Whether network has connected customers | KundenAngeschlossen=1 |
| `closed_distribution_network` | Closed distribution network flag | GeschlossenesVerteilnetz=1 |

### Installed Capacity

| Field | Description | Source |
|-------|-------------|--------|
| `solar_capacity_mw` | Solar PV capacity in MW | EinheitenSolar Bruttoleistung |
| `wind_capacity_mw` | Wind turbine capacity in MW | EinheitenWind Bruttoleistung |
| `storage_capacity_mw` | Battery storage capacity in MW | EinheitenStromSpeicher |
| `biomass_capacity_mw` | Biomass capacity in MW | EinheitenBiomasse |
| `hydro_capacity_mw` | Hydro capacity in MW | EinheitenWasser |
| `total_capacity_mw` | Sum of all capacities | Calculated |

### Unit Counts

| Field | Description |
|-------|-------------|
| `solar_units` | Number of solar installations |
| `wind_units` | Number of wind turbines |
| `storage_units` | Number of battery storage systems |

## Data Linkage

The pipeline uses a multi-hop join to link energy units to DNOs:

```
Einheiten (Solar/Wind/etc.)
    └── LokationMaStRNummer → Lokationen
                               └── NetzanschlusspunkteMaStRNummern → Netzanschlusspunkte
                                                                      └── NetzbetreiberMaStRNummer → DNO
```

## Processing Time

| Phase | Files | Time |
|-------|-------|------|
| Market Roles | 1 small | < 10 sec |
| Market Actors | 52 files | 2-5 min |
| Networks | 1 small | < 10 sec |
| Connection Points | 54 large | 10-20 min |
| Locations | 62 large | 15-25 min |
| Energy Units | 60+ very large | 30-60 min |
| **Total (full)** | | **1-2 hours** |
| **Total (quick)** | | **10-30 min** |

## Use Cases for DNO Statistics

1. **Prioritization**: Sort DNOs by size (connection points, capacity) to crawl large operators first
2. **Voltage Level Estimation**: Predict applicable tariff levels based on connection point distribution
3. **Energy Transition Tracking**: Monitor solar/storage adoption per DNO region
4. **Crawl Strategy**: Large DNOs may have more complex website structures
5. **Customer Importance**: DNOs with many customers are higher priority for accurate tariff data

## Backend Integration

The canonical integration reference is:

- `marktstammdatenregister/BACKEND_INTEGRATION.md`

Current required operational steps:

```bash
cd backend
alembic upgrade head
python scripts/import_mastr_stats.py --file ../marktstammdatenregister/dno_stats.json --dry-run
python scripts/import_mastr_stats.py --file ../marktstammdatenregister/dno_stats.json
```

## Troubleshooting

### Memory Issues

The parsers use iterative XML parsing (iterparse) which is memory-efficient. However, if you encounter memory issues with very large files:

1. Process files in smaller batches
2. Use `--quick` mode for connection points only
3. Increase system swap space

### Missing DNOs

Some DNOs may have zero connection points because:
- They are transmission system operators (TSOs) with few connection points
- The data linkage via locations failed
- The DNO operates in a closed distribution network

### Data Quality

- `full`: Both connection points and capacity data available
- `partial`: Only connection points (quick mode or missing energy data)
- `sampled`: Not currently used, reserved for future sampling mode

## License

This transformation pipeline is part of the DNO Crawler project.
MaStR data is published by Bundesnetzagentur under their data usage terms.
