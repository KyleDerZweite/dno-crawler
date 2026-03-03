# MVP Triage: Prod Readiness Assessment

> Generated: 2026-03-02
> Scope: Full codebase scan for TODOs, FIXMEs, stubs, incomplete features, and security gaps.

---

## 1. Critical for MVP (Must-Do Before Production)

### C1. `.env.example` missing `AI_ENCRYPTION_KEY` / `SESSION_SECRET` documentation

- **File**: `/home/kyle/CodingProjects/dno-crawler/.env.example`
- **Issue**: The `.env.example` template does not mention `AI_ENCRYPTION_KEY` or `SESSION_SECRET`. The encryption module (`backend/app/services/ai/encryption.py`, line 40-48) refuses to start in production/staging without one of these. A deployer following `.env.example` will hit a runtime crash on first AI provider save.
- **Why Critical**: Production startup failure. Secrets stored unencrypted if misconfigured.
- **Fix**: Add `AI_ENCRYPTION_KEY=<generate-random-hex-here>` to `.env.example` with a comment.
- **Priority**: 1

### C2. `.env.example` missing `TRUSTED_PROXY_COUNT`

- **File**: `/home/kyle/CodingProjects/dno-crawler/.env.example`
- **Issue**: `TRUSTED_PROXY_COUNT` defaults to `1` in config (`backend/app/core/config.py`, line 57). The DEPLOYMENT.md doc says production requires `2` (Pangolin + Newt). If left at default, rate limiting and IP extraction from `X-Forwarded-For` will use the wrong hop, making rate limits target proxy IPs instead of clients.
- **Why Critical**: Rate limiting bypass; incorrect IP logging and abuse detection.
- **Fix**: Add `TRUSTED_PROXY_COUNT=2` to `.env.example` with a comment explaining the Pangolin + Newt setup.
- **Priority**: 2

### C3. Mock auth guard in production is reactive, not preventive

- **File**: `/home/kyle/CodingProjects/dno-crawler/backend/app/core/auth.py`, lines 270-280
- **Issue**: If `ZITADEL_DOMAIN` is left at `auth.example.com` in production, the system logs a critical error and returns 503 on every authenticated request. This is correct defensive behavior. However, there is no startup-time check that fails fast. The backend will start, serve public endpoints (search, health), and only fail when a user hits a protected route. This creates a confusing partial-availability state.
- **Why Critical**: Partial service availability in production with misconfigured auth creates a false "healthy" signal for monitoring.
- **Fix**: Add a startup validation in `app/api/main.py` lifespan that refuses to start if `ENVIRONMENT=production` and `is_auth_enabled=False`. Log a critical message and raise `SystemExit`.
- **Priority**: 3

### C4. Legacy `search_job.py` still in worker registration (dead code risk)

- **File**: `/home/kyle/CodingProjects/dno-crawler/backend/app/jobs/search_job.py` (entire file)
- **File**: `/home/kyle/CodingProjects/dno-crawler/backend/app/jobs/__init__.py`, lines 89, 163
- **Issue**: `search_job.py` is documented as "TEMPORARY WORKER for queue and status update testing" (line 2). It contains a `process_dno_crawl` function that is registered in the legacy `WorkerSettings` class. The legacy `WorkerSettings` is not used in the split-worker production compose, but the import still exists and the `_update_step` function (line 73-81) is a dead no-op. If someone accidentally starts the legacy worker, it would run this simplified job instead of the real pipeline.
- **Why Critical**: Accidental use of legacy worker would silently produce no data. Dead code increases confusion.
- **Fix**: Remove `search_job.py` entirely. Remove the `WorkerSettings` class or, if it must stay for backwards compatibility, wire it to `process_crawl` + `process_extract` instead.
- **Priority**: 4

### C5. `type: ignore` suppressions in sitemap service

- **File**: `/home/kyle/CodingProjects/dno-crawler/backend/app/services/discovery/sitemap.py`, lines 97, 100, 101
- **Issue**: Three `# type: ignore` comments suppress type checking on HTTP response handling. These indicate the code may not be handling the `None` case from failed HTTP calls correctly.
- **Why Critical**: Could mask a runtime `AttributeError` on `None.status_code` or `None.text` if the HTTP client returns an unexpected type. This is a data-path code used during every crawl.
- **Fix**: Add proper type narrowing (`if response is not None:`) or refactor the HTTP call to always return a typed result.
- **Priority**: 5

### C6. [Deferred] No XLSX extraction in the extraction pipeline

- **Files**: `/home/kyle/CodingProjects/dno-crawler/backend/app/services/extraction/` (directory)
- **Issue**: The architecture document (`docs/ARCHITECTURE.md`, line 439) shows XLSX as a supported extraction path. The discovery and download steps correctly detect and download XLSX files. The `content_verifier.py` can read XLSX for verification. However, there is no `xlsx_extractor.py` in the extraction pipeline. If a DNO only publishes data in XLSX format, the deterministic extraction step will fail silently and fall through to AI extraction (if configured) or fail entirely.
- **Status**: Deferred per `MVP_PLAN.md` ("What was NOT done", around line 76).
- **Why Deferred**: During MVP validation, no active DNO in scope used XLSX as the sole source for Netzentgelte/HLZF. Existing PDF/HTML paths cover current production targets.
- **Implementation Target**: Add `/app/services/extraction/xlsx_extractor.py` and wire it into the extraction pipeline entrypoint in `/app/services/extraction/` (classifier/dispatch stage).
- **Planned Timing**: First post-MVP extraction expansion milestone, when a DNO source set requires XLSX parsing.
- **Priority**: Deferred (not critical for MVP launch)

---

## 2. Quality of Life (Can Wait)

### Q1. SQL Explorer view is a stub

- **File**: `/home/kyle/CodingProjects/dno-crawler/frontend/src/features/dno-detail/views/SQLExplorer.tsx`, line 198
- **Issue**: The SQL Explorer tab shows a placeholder message. The detailed implementation plan is documented in the file comments (lines 1-172) including security model and API endpoint spec, but no code is implemented. No corresponding backend endpoint exists.
- **Why QoL**: Power-user feature. All data is accessible through the existing Data Explorer and API endpoints. Not required for core data extraction workflow.
- **Priority**: 1

### Q2. Technical view is a stub

- **File**: `/home/kyle/CodingProjects/dno-crawler/frontend/src/features/dno-detail/views/Technical.tsx`, line 128
- **Issue**: The Technical tab shows a placeholder. Intended to display sitemap URLs, robots.txt data, and crawl metadata. Full spec is in file comments (lines 1-110).
- **Why QoL**: Debugging/transparency feature for operators. Crawl metadata is accessible via the API and database directly. Useful but not blocking for production data flows.
- **Priority**: 2

### Q3. Tools view is a placeholder

- **File**: `/home/kyle/CodingProjects/dno-crawler/frontend/src/features/dno-detail/views/Tools.tsx`
- **Issue**: Entire component is a placeholder for "Netzentgelte calculators, form automation, and compliance checkers."
- **Why QoL**: Future expansion feature explicitly marked as such. No backend support exists or is needed for MVP.
- **Priority**: 3

### Q4. LiteLLM provider is a stub

- **File**: `/home/kyle/CodingProjects/dno-crawler/backend/app/services/ai/providers/litellm.py`
- **Issue**: All methods raise `NotImplementedError` or return empty/False. Marked "Coming Soon" in provider info. The frontend shows it as disabled.
- **Why QoL**: OpenRouter, Google, and Custom providers are fully functional. LiteLLM is an enterprise convenience feature for proxy deployments.
- **Priority**: 4

### Q5. Impressum extractor enhancement ideas

- **File**: `/home/kyle/CodingProjects/dno-crawler/backend/app/services/impressum_extractor.py`, lines 18-24
- **Issue**: TODO comment lists future enhancements: extract Geschaeftsfuehrung, Handelsregister, USt-IdNr, and responsible person from Impressum pages.
- **Why QoL**: The core address extraction works. Additional metadata extraction is a data enrichment feature, not required for pricing data extraction.
- **Priority**: 5

### Q6. PriceTrendChart forecast logic is a placeholder

- **File**: `/home/kyle/CodingProjects/dno-crawler/frontend/src/features/dno-detail/components/PriceTrendChart.tsx`, line 55
- **Issue**: Comment says "For now, forecast is any year > current year (placeholder)". The chart shows future years with dashed lines, but the forecast is just rendering null data points.
- **Why QoL**: Visual polish. No actual forecasting model exists or is needed for MVP. The chart correctly shows historical data.
- **Priority**: 6

### Q7. `recheck_robots.py` temporary script

- **File**: `/home/kyle/CodingProjects/dno-crawler/backend/scripts/recheck_robots.py`
- **Issue**: Documented as "Temporary script to re-check robots.txt and fetch sitemaps." This is a one-off migration/maintenance script.
- **Why QoL**: Operational tooling. Not part of the production runtime. Can be kept or removed at leisure.
- **Priority**: 7

### Q8. Frontend test coverage is minimal

- **Files**: `/home/kyle/CodingProjects/dno-crawler/frontend/src/App.test.tsx` (only test file)
- **Issue**: Only one test file exists with two trivial "renders without crashing" tests. No component, hook, or integration tests.
- **Why QoL**: Testing is important but the backend has meaningful test coverage (6 test files covering health, auth, search, DNOs, crawling, completeness). Frontend tests can be added incrementally.
- **Priority**: 8

### Q9. Stale TODO comment in DNOsPage

- **File**: `/home/kyle/CodingProjects/dno-crawler/frontend/src/pages/DNOsPage.tsx`, line 289
- **Issue**: Comment says `{/* TODO was: Future enhancement - validate DNO against VNB Digital API - NOW IMPLEMENTED */}`. This is a resolved TODO that was left in place instead of being removed.
- **Why QoL**: Code hygiene. No functional impact.
- **Priority**: 9

---

## Summary: Minimum Path to Prod

| Step | Item | Effort Estimate | Risk if Skipped |
|------|------|-----------------|-----------------|
| 1 | C1: Add `AI_ENCRYPTION_KEY` to `.env.example` | 5 min | Startup crash / unencrypted secrets |
| 2 | C2: Add `TRUSTED_PROXY_COUNT` to `.env.example` | 5 min | Rate limiting bypass |
| 3 | C3: Fail-fast startup check for auth in production | 30 min | Confusing partial availability |
| 4 | C4: Remove legacy `search_job.py` and `WorkerSettings` | 15 min | Silent data pipeline failure |
| 5 | C5: Fix `type: ignore` in sitemap service | 20 min | Potential runtime crash during crawl |
| 6 | C6: XLSX extractor | Deferred post-MVP | Track as extraction expansion item |

**Total estimated effort for Critical MVP launch items: approximately 1-2 hours (C1-C5).**

All QoL items (Q1-Q9) can be addressed post-launch with no impact on core data extraction, security, or operational stability.
