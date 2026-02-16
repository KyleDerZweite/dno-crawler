# Seed Data Pipeline

The database is seeded on worker startup from a parquet file. The pipeline transforms raw source files through several stages to produce that parquet. Only the final two steps (merge + convert) need to run regularly; the earlier stages are one-time or infrequent data preparation.

## Data files (`data/seed-data/`)

| File | Content |
|------|---------|
| `OeffentlicheMarktakteure.csv` | Raw MaStR public CSV export (semicolon-delimited, UTF-8 with BOM). Contains all electricity network operators with registration data, addresses, market roles. |
| `dnos_seed.json` | Cleaned JSON produced from the CSV. Intermediate file, not used directly by later stages. |
| `dnos_enriched.json` | Seed records enriched with VNB Digital (website, phone, email) and BDEW codes, plus robots.txt/sitemap crawl state. This is the primary input to the merge step. |
| `dno_stats.json` | MaStR offline pipeline output (`marktstammdatenregister/transform_mastr.py`). Connection points, capacity, unit counts for ~1693 operators (SNB electricity + GNB gas). |
| `dnos_enriched_with_stats.json` | Merged output combining enriched records with MaStR stats. SNB-only, deduplicated slugs. |
| `dnos_enriched_with_stats.parquet` | Final zstd-compressed parquet consumed by the seeder at runtime. |

## Scripts

| Script | Location | Purpose |
|--------|----------|---------|
| `transform_csv_to_json.py` | `backend/scripts/` | Stage 1: CSV to JSON |
| `enrich_seed_data.py` | `backend/scripts/` | Stage 2: VNB Digital + BDEW enrichment |
| `recheck_robots.py` | `backend/scripts/` | Stage 3: robots.txt + sitemap crawling |
| `transform_mastr.py` | `marktstammdatenregister/` | Stage 4: MaStR XML to stats JSON |
| `merge_enriched_with_stats.py` | `data/seed-data/` | Stage 5: merge enriched + stats |
| `convert.py` | `data/seed-data/` | Stage 6: JSON to parquet |

## Full pipeline (stages in order)

Each stage feeds the next. Stages 1 through 4 are infrequent data preparation steps. Stages 5 and 6 are the regular "regenerate seed data" steps.

### Stage 1: CSV to JSON (run from `backend/`)

```bash
uv run python scripts/transform_csv_to_json.py
```

- Input: `data/seed-data/OeffentlicheMarktakteure.csv`
- Output: `data/seed-data/dnos_seed.json`

Parses semicolon-delimited fields (dates in M/D/YYYY, Ja/Nein booleans, German umlauts in company names), generates URL-safe slugs (umlauts replaced: ae/oe/ue/ss), and writes sorted JSON. Each record contains `mastr_nr`, `name`, `slug`, `region`, `acer_code`, `address_components`, `contact_address`, `marktrollen`, dates, and status flags.

### Stage 2: Enrich with VNB Digital + BDEW (run from `backend/`)

```bash
uv run python scripts/enrich_seed_data.py [--limit N] [--skip-vnb] [--skip-bdew]
```

- Input: `data/seed-data/dnos_seed.json`
- Output: `data/seed-data/dnos_enriched.json`

For each record, queries:
- **VNB Digital API**: website, phone, email, address (1.0s base delay with jitter)
- **BDEW API**: BDEW code, internal IDs, market function (0.3s base delay with jitter)

Tags each record with `enrichment_source`: `both`, `vnb_digital`, `bdew`, or `null`. Progress logged every 25 records.

Also supports `--db` mode to write directly to database source tables instead of JSON output.

Full options: `--vnb-delay`, `--bdew-delay` to adjust politeness timings.

### Stage 3: Recheck robots.txt and sitemaps (run from `backend/`)

```bash
uv run python scripts/recheck_robots.py [--limit N] [--delay 0.5]
```

- Input/Output: `data/seed-data/dnos_enriched.json` (in-place by default, or `--output`)

For each record with a `website` field:
1. Fetches `robots.txt` via `fetch_and_verify_robots()`.
2. Extracts `Sitemap:` directives and `Disallow:` paths.
3. Recursively fetches and parses sitemaps (max depth 2), filtering by language preference: German (`/de/`) preferred, English (`/en/`) fallback, other languages excluded.

Updates fields: `crawlable`, `blocked_reason`, `robots_txt`, `robots_fetched_at`, `sitemap_urls`, `sitemap_parsed_urls`, `sitemap_fetched_at`, `disallow_paths`. Sets `status` to `"protected"` if blocked.

### Stage 4: Generate MaStR stats (run from repo root)

```bash
python marktstammdatenregister/transform_mastr.py \
    --data-dir ./marktstammdatenregister/data \
    --output ./data/seed-data/dno_stats.json
```

Transforms MaStR XML exports into per-DNO statistics JSON. Output contains ~1693 operators keyed by `mastr_nr` (both SNB electricity and GNB gas), with connection points, installed capacity, unit counts, and network metadata.

### Stage 5: Merge enriched data with MaStR stats (run from repo root)

```bash
python data/seed-data/merge_enriched_with_stats.py
```

- Input: `data/seed-data/dnos_enriched.json` + `data/seed-data/dno_stats.json`
- Output: `data/seed-data/dnos_enriched_with_stats.json`

Two-pass merge:
1. **First pass** over enriched records: attaches MaStR stats to each record via `mastr_nr` key lookup. Tracks seen `mastr_nr` values and slugs.
2. **Second pass** over stats records: appends stats-only DNOs as minimal seed records. Filters applied:
   - `mastr_nr` must start with `SNB` (electricity only; excludes ~752 GNB gas records)
   - Generated slug must not already exist (deduplicates ~2 collisions)

Prints a summary with counts: `input_enriched`, `input_stats`, `output_total`, `updated_with_stats`, `stats_only_added`, `skipped_non_snb`, `skipped_duplicate_slug`.

### Stage 6: Convert to parquet (run from repo root)

```bash
python data/seed-data/convert.py \
    --input data/seed-data/dnos_enriched_with_stats.json \
    --output data/seed-data/dnos_enriched_with_stats.parquet
```

Converts the merged JSON to a zstd-compressed parquet file (compression level 22). The parquet format is required by the seeder.

## Regenerating seed data (common task)

When only the merge logic or stats data has changed, run stages 5 and 6 only:

```bash
python data/seed-data/merge_enriched_with_stats.py
python data/seed-data/convert.py \
    --input data/seed-data/dnos_enriched_with_stats.json \
    --output data/seed-data/dnos_enriched_with_stats.parquet
```

Expected output: ~939 SNB-only records, 0 duplicate slugs.

## Runtime seeding (`backend/app/db/seeder.py`)

On worker startup, `seed_dnos()` loads the parquet file and upserts each record into the database:

- **File preference**: `dnos_enriched_with_stats.parquet` first, falls back to `dnos_enriched.parquet`.
- **Upsert logic**: looks up existing `DNOModel` by `mastr_nr`. If found, updates; if not, inserts.
- **Hub and spoke**: creates/updates `DNOModel` (hub) and spoke tables (`DNOMastrData`, `DNOVnbData`, `DNOBdewData`) depending on which fields are present in the record.
- **MaStR stats normalization**: connection points are normalized from either `by_canonical_level` or `by_voltage` format into a consistent structure with NS/MS/HS/HoeS levels.
- **Error isolation**: each record is wrapped in a savepoint (`begin_nested()`) so one `IntegrityError` does not poison the session for subsequent records.
- **Single commit**: commits once after all records are processed.
- **Return value**: tuple of `(inserted, updated, skipped)`.

## Verification

After regenerating seed data, verify:

1. **Merge summary**: expected totals, `skipped_non_snb` count (~752), `skipped_duplicate_slug` count (~2).
2. **Zero duplicate slugs**:
   ```bash
   python -c "
   import json; from collections import Counter
   r = json.load(open('data/seed-data/dnos_enriched_with_stats.json'))
   slugs = [x['slug'] for x in r]
   dupes = {s: c for s, c in Counter(slugs).items() if c > 1}
   print(f'records={len(r)} dupes={len(dupes)}')
   "
   ```
3. **Runtime**: `podman-compose logs worker-crawl` shows "Seeding complete" with expected inserted/updated counts.
