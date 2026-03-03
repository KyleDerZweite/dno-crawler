# MVP Production Plan

> Generated: 2026-03-02
> Focus: Only what's required to ship safely. No QoL, no refactors, no nice-to-haves.

---

## Phase 1: Production Blockers — COMPLETED

| # | Task | Status |
|---|------|--------|
| 1.1 | Added `AI_ENCRYPTION_KEY` and `TRUSTED_PROXY_COUNT` to `.env.example` | Done |
| 1.2 | Fail-fast `SystemExit(1)` if auth disabled in production (`main.py`) | Done |
| 1.3 | Deleted `search_job.py`, removed `WorkerSettings` class | Done |
| 1.4 | Replaced 3x `type: ignore` with explicit `httpx.Response` annotation in `sitemap.py` | Done |
| bonus | Test fixtures skip gracefully when DB is unavailable (`conftest.py`) | Done |

---

## Phase 2: Code Health — COMPLETED

| # | Task | Status |
|---|------|--------|
| 2.1 | Removed ~535 lines of duplicated types from `lib/api.ts`, created canonical `ai.types.ts` and `api-key.types.ts` | Done |
| 2.2 | Replaced 4x inline admin checks with `Depends(require_admin)` in `data.py` | Done |
| 2.3 | Extracted `enrich_dno_from_web()` helper, replaced 3 duplicated blocks in `search.py` | Done |
| 2.4 | Removed dangling coroutine, stale comment, `locals()` hack in `crud.py` | Done |

---

## Phase 3: Dev/Prod Workflow Setup — PARTIALLY DONE

| # | Task | Status |
|---|------|--------|
| 3.1 | Create `dev` branch and push to origin | **You** |
| 3.2 | Updated CI triggers in `.github/workflows/ci.yml` (added `dev` branch) | Done |
| 3.3 | Set up GitHub branch protection for `main` | **You** |
| bonus | Fixed 11 lint errors (alembic imports, unused imports, f-strings, module-level `pytest.skip`) | Done |

### What you still need to do manually:

**3.1 — Create the `dev` branch:**
```bash
git checkout main
git checkout -b dev
git push -u origin dev
```

**3.3 — GitHub branch protection (repo Settings > Branches > Add rule for `main`):**
- Require pull request before merging
- Require status checks to pass (select: `backend-lint`, `backend-test`, `frontend-build`, `frontend-test`)
- Require branch to be up to date before merging

---

## Summary

### What was done (all code changes)

| Area | Change |
|------|--------|
| **Security** | Fail-fast startup if auth disabled in production |
| **Security** | Consistent `require_admin` dependency across all admin endpoints |
| **Config** | Added missing `AI_ENCRYPTION_KEY` and `TRUSTED_PROXY_COUNT` to `.env.example` |
| **Dead code** | Deleted legacy `search_job.py` and `WorkerSettings` class |
| **Dead code** | Removed dangling coroutine and `locals()` hack in `crud.py` |
| **Type safety** | Replaced `type: ignore` in `sitemap.py` with explicit typing |
| **DRY** | Extracted `enrich_dno_from_web()` helper, deduplicated 3 call sites in `search.py` |
| **DRY** | Removed ~535 lines of duplicated frontend types, single source of truth in `@/types` |
| **CI** | Updated CI triggers to also run on `dev` branch |
| **CI** | Fixed 11 lint/test errors blocking CI (imports, f-strings, module-level pytest.skip) |
| **Testing** | Tests skip gracefully when DB is unavailable instead of failing |

### What was NOT done (deferred post-MVP)

- XLSX extraction (no DNOs use XLSX for Netzentgelte/HLZF)
- PDF/HTML extraction improvements (works, iterate later)
- SQL Explorer, Technical view, Tools view (frontend stubs)
- LiteLLM provider (other providers work)
- Impressum enrichment enhancements (core works)
- Frontend test coverage (backend has tests, frontend can wait)
- Large refactors: service layer extraction for `admin.py` (F-007) and `crud.py` (F-008)
- Model mixins for shared columns (F-020)
- Generic verification endpoints (F-013)
- Consolidate `StrEnum` vs `Literal` duplication (F-015)
- PriceTrendChart forecast (visual polish)
