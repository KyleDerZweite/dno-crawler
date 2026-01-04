# Data Directory

Persistent storage for seed data, downloaded files, and database volumes.

## Structure

```
data/
├── seed-data/              # Static seed files (tracked in git)
│   ├── dnos.json           # Base DNO records from MaStR
│   ├── OeffentlicheMarktakteure.csv  # MaStR market participants export
│   └── marktstammdatenregister/      # Raw MaStR exports (gitignored)
├── downloads/              # Crawled files (gitignored)
│   └── {dno-slug}/
│       ├── {slug}-netzentgelte-{year}.pdf
│       └── {slug}-hlzf-{year}.html
├── samples/                # Extraction samples for learning (gitignored)
│   ├── training/           # Regex failed → AI succeeded
│   │   └── {dno-slug}/
│   └── debug/              # Regex failed → AI also failed
│       └── {dno-slug}/
├── uploads/                # User-uploaded files (gitignored)
│   └── {dno-slug}/
│       └── {filename}
├── postgres/               # PostgreSQL data volume (gitignored)
└── redis/                  # Redis persistence (gitignored)
```

## Seed Data

### Tracked Files

| File | Size | Description |
|------|------|-------------|
| `seed-data/dnos.json` | ~1 MB | Enriched DNO dataset with MaStR data |
| `seed-data/OeffentlicheMarktakteure.csv` | ~220 KB | Public market participants from MaStR |

### Gitignored

- `seed-data/marktstammdatenregister/` - Raw XML/CSV exports (too large for git)
- `downloads/` - Crawled PDFs and HTML files
- `samples/` - Extraction samples for learning/debugging
- `uploads/` - User-uploaded files
- `postgres/` - Database volume
- `redis/` - Redis AOF persistence

## Extraction Samples

When regex extraction fails, samples are captured to `samples/`:

| Category | Description |
|----------|-------------|
| `training/` | Regex failed → AI succeeded (useful for pattern learning) |
| `debug/` | Regex failed → AI also failed (for debugging extraction) |

Sample files are JSON with source file path, regex output, AI output, and failure reasons.

## File Naming Convention

Downloaded and uploaded files follow a canonical naming scheme:

```
{dno-slug}-{data-type}-{year}.{extension}
```

Examples:
- `netze-bw-netzentgelte-2025.pdf`
- `westnetz-hlzf-2024.html`
- `stadtwerke-muenchen-netzentgelte-2025.xlsx`

## Data Sources

### Marktstammdatenregister (MaStR)

The MaStR data requires periodic manual export from the Bundesnetzagentur portal:

1. Navigate to [Marktstammdatenregister](https://www.marktstammdatenregister.de/)
2. Export "Öffentliche Marktakteure" data
3. Place CSV/XML files in `seed-data/marktstammdatenregister/`
4. Run the seeding script: `python backend/scripts/seed_mastr.py`

### VNB Digital

VNB Digital data is fetched in real-time via GraphQL API during DNO resolution.

### BDEW Codes

BDEW codes are fetched on-demand via JTables POST requests to the BDEW registry.

## Verification

Seed files include SHA256 checksums in `seed-data/SHA256SUMS`:

```bash
# Verify all seed files
cd data/seed-data
sha256sum -c SHA256SUMS

# Verify single file
sha256sum dnos.json
```

## Volume Management

For Docker/Podman deployments, volumes are mounted from this directory:

```yaml
# docker-compose.yml
volumes:
  - ./data/postgres:/var/lib/postgresql/data
  - ./data/redis:/data
  - ./data:/data  # Downloads, uploads
```

To reset the database:

```bash
podman-compose down -v
rm -rf data/postgres data/redis
podman-compose up -d
```