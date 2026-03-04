# Importance Scoring

Canonical DNO importance scoring is implemented as a backend service and persisted on `dnos`.

## Purpose

Importance score is the canonical prioritization signal for automated enrichment and crawl workflows. It is distinct from legacy data completeness score.

## Inputs (v1)

- `connection_points` (dominant signal)
- `customer_count` (if available)
- `service_area_km2` (if available)

When customer/area data is missing, scoring remains deterministic via documented fallbacks. Explainability metadata records all fallback usage.

## Storage

The `dnos` table stores:

- `importance_score`
- `importance_confidence`
- `importance_version`
- `importance_factors` (JSON breakdown)
- `importance_updated_at`
- optional raw inputs: `customer_count`, `service_area_km2`

## Update Flow

Importance is updated in these paths:

1. seed upsert pipeline
2. recompute script
3. DNO metadata update route (when optional raw inputs change)

## Operations

Recompute all scores from backend:

```bash
python scripts/recompute_importance.py
```

Dry run:

```bash
python scripts/recompute_importance.py --dry-run
```

Admin endpoints:

- `GET /api/v1/admin/importance/distribution`

Async ORM caveat:

- Any route that computes transient importance from ORM DNO objects must eager-load `mastr_data` (for example `selectinload(DNOModel.mastr_data)`).
- Without eager loading, accessing `dno.mastr_data` during score computation can trigger `MissingGreenlet` in async contexts and make admin metrics appear as zeros in the UI because the request fails.

Notes:

- Recompute is intentionally script-only (`scripts/recompute_importance.py`) to keep admin API surface minimal (YAGNI).
- Admin UI exposes read-only distribution and diagnostics.

## Design Decision (YAGNI)

The previously added admin write endpoint for recomputation was removed.

Reasoning:

- recomputation is an operational batch action, not a frequent UI action
- script execution from backend shell is already available and explicit
- removing write endpoint reduces accidental heavy runs, auth attack surface, and rate-limit complexity

This keeps admin API focused on observability and avoids adding orchestration behavior before it is required.

## Principles Alignment

- KISS: one recompute path (script) + one diagnostics path (read-only endpoint)
- DRY: scoring logic lives in one service (`app/services/importance.py`) and is reused by seed/update/reporting flows
- YAGNI: no admin write endpoint for recompute until a concrete need appears
- SoC: compute logic, persistence triggers, and UI diagnostics are separated

## Frontend Visibility

Admin dashboard includes an Importance Scoring section showing:

- score distribution histogram
- p50 and p90
- fallback diagnostics
- top important DNO list
