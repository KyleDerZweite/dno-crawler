# DNO Crawler -- Code Review

**Date:** 2026-02-11
**Scope:** Full-stack review (backend + frontend)
**Codebase:** ~10K lines Python backend, 93 TypeScript/TSX frontend files

> **Note:** Members in this project's private Zitadel instance are trusted/invited users.
> Member-level access for uploads, imports, and verification is intentional.

---

## CRITICAL / HIGH Severity

- [x] **1. Auth completely disabled on misconfiguration** -- FIXED
  `backend/app/core/auth.py:119-125` + `core/config.py:98-100`
  When `ZITADEL_DOMAIN` is unset or equals `"auth.example.com"`, every request gets a mock ADMIN user. All endpoints become publicly accessible. Frontend has the same issue in `lib/use-auth.ts:26-47`.
  **Fix applied:** Added `is_production` property to Settings. In production/staging, `get_current_user` returns 503 instead of mock admin. Startup logs CRITICAL warning. Dev mode still works with mock admin but logs a visible warning. Role extraction logging reduced from INFO to DEBUG. Error messages no longer leak internal JWT/auth details.

- [x] **2. XSS in OAuth callback HTML** -- FIXED
  `api/routes/oauth.py:214,268`
  User-controlled data (email, name from Google OAuth) interpolated into HTML without escaping. `postMessage` uses wildcard origin `'*'` (lines 219, 273), sending credentials to any opener window.
  **Fix applied:** All interpolated values HTML-escaped via `html.escape()`. JavaScript strings use `json.dumps()` for safe embedding. `postMessage` now uses specific origin from `settings.cors_origins` instead of wildcard `'*'`.

- [x] **3. XXE vulnerability in sitemap parser** -- FIXED
  `services/discovery/sitemap.py:140`
  `ElementTree.fromstring()` parses external XML without XXE protection. Attacker-controlled sitemaps could read local files.
  **Fix applied:** Replaced `ElementTree.fromstring()` with `defusedxml.ElementTree.fromstring()`. Added `defusedxml>=0.7.1` to dependencies.

- [x] **4. Unbounded file upload with no size limit** -- FIXED
  `api/routes/dnos/files.py:126`
  `await file.read()` loads entire upload into memory with no size or extension validation.
  **Fix applied:** Added 250MB streaming size limit (reads in 1MB chunks, cleans up partial file on overflow). Added extension allowlist validation (.pdf, .xlsx, .xls, .csv, .html, .htm, .docx, .doc, .txt, .png, .jpg, .jpeg). Returns 413 on size exceeded, 400 on bad extension. To adjust the limit, change `MAX_UPLOAD_SIZE` in `api/routes/dnos/files.py`.

- [x] **5. Hardcoded fallback encryption key** -- FIXED
  `services/ai/encryption.py:36-39`
  When `AI_ENCRYPTION_KEY` and `SESSION_SECRET` are unset, API keys encrypted with a publicly visible string. Key derivation uses plain SHA-256 instead of proper KDF.
  **Fix applied:** In production/staging, raises `RuntimeError` if no key is configured. Key derivation replaced with HKDF (from `cryptography` library) instead of plain SHA-256. Dev fallback key still works for local development with warning.

- [x] **6. No React Error Boundaries** -- FIXED
  Frontend-wide -- zero `ErrorBoundary` components. Any rendering exception crashes the entire app with a white screen.
  **Fix applied:** Added `ErrorBoundary` component (`components/ErrorBoundary.tsx`) with full-page and inline variants. Wrapped at app level (`main.tsx`) and at every route level (`App.tsx`) with inline mode.

- [x] **7. No SSRF protection in content verifier** -- FIXED
  `services/content_verifier.py:137-316`
  `verify_url` and `verify_and_cache_document` fetch arbitrary URLs without private IP checks or port restrictions. The `UrlProber` has protections, but the content verifier bypasses them.
  **Fix applied:** Added `validate_url_ssrf_safe()` helper to `url_utils.py` (checks scheme, port, credentials, resolves hostname to verify all IPs are global/public). Both `verify_url` and `verify_and_cache_document` now call this check before any HTTP request.

- [x] **8. Dead code in format detection -- DOCX always misidentified as XLSX** -- FIXED
  `jobs/steps/step_02_download.py:278-294`
  `MAGIC_BYTES` maps `PK\x03\x04` to `'xlsx'`. The loop returns immediately, so the XLSX/DOCX/PPTX refinement logic never executes. All ZIP-based Office formats saved as `.xlsx`.
  **Fix applied:** Removed `PK\x03\x04` from `MAGIC_BYTES` dict. ZIP-based formats now fall through to the refinement logic that checks for `workbook.xml`, `word/`, or `ppt/` signatures.

- [x] **9. API key leak in AI test error messages** -- FIXED
  `api/routes/ai.py:372-378`
  `str(e)` from provider libraries may include API keys in error output. Returned to admin users.
  **Fix applied:** Added `_sanitize_error()` function that strips API key patterns (`sk-`, `key-`, `api-`, `bearer` + long tokens) and redacts full URLs from error messages before returning to clients.

---

## MEDIUM Severity

### Security

- [x] **10. ILIKE wildcard injection in search** -- FIXED
  `api/routes/search.py:562-567` + `dnos/crud.py:327-362`
  `%` and `_` not escaped in ILIKE patterns. Submitting `%` returns all records.
  **Fix applied:** Escape `%`, `_`, and `\` in user input before ILIKE patterns in both `search.py` and `crud.py`.

- [x] **11. X-Forwarded-For trusted unconditionally** -- FIXED
  `core/rate_limiter.py:126-131`
  Any client can spoof IP to bypass rate limiting.
  **Fix applied:** Replaced leftmost-IP approach with rightmost-N. New `TRUSTED_PROXY_COUNT` setting (default 1). Takes the IP at `-(N+1)` from the right of X-Forwarded-For, which only trusted proxies can append to.

- [x] **12. JWT audience verification disabled** -- FIXED
  `core/auth.py:147`
  `verify_aud: False` means any JWT from any Zitadel project on the same instance is accepted.
  **Fix applied:** Added `ZITADEL_CLIENT_ID` setting. When configured, JWT audience verification is enabled in both `get_current_user` and `get_optional_user`. Without it, behavior is unchanged (backwards compatible).

- [x] **13. Token stored in localStorage (XSS-accessible)** -- ACCEPTED
  `frontend/src/lib/auth-config.ts:20`
  OIDC tokens accessible to any JavaScript on the page.
  **Decision:** Accepted as a known SPA + PKCE trade-off. Using `oidc-client-ts` with Authorization Code Flow + PKCE. localStorage risk is minor given the trusted-user model.

- [x] **14. `dangerouslySetInnerHTML` with SVG content** -- FIXED
  `frontend/src/features/admin/AIConfigSection.tsx:96-105`
  `ProviderIcon` renders SVG strings as raw HTML. Currently safe (hardcoded client-side) but architecture permits server-sourced SVG.
  **Fix applied:** Added DOMPurify sanitization with SVG profile (`USE_PROFILES: { svg: true, svgFilters: true }`) before `dangerouslySetInnerHTML`.

### Reliability

- [x] **15. Rate limiter silently disabled on Redis failure** -- FIXED
  `api/routes/search.py:246-249` + `files.py:21-25`
  If Redis is down, rate limiting is silently bypassed on all endpoints including public search.
  **Fix applied:** Changed `log.warning` to `log.error` with structured event name `rate_limiter_unavailable`. Keeps fail-open behavior (appropriate for this app) but ensures observability.

- [x] **16. Crawl lock bypass logic bug** -- FIXED
  `api/routes/dnos/crawl.py:86-100`
  When `crawl_locked_at` is recent (within 1 hour), the code falls through without raising 409. A second concurrent crawl can start.
  **Fix applied:** Added `else` branch for `locked_at >= threshold` that raises 409 Conflict, preventing concurrent crawls.

- [x] **17. BaseStep rollback-then-commit pattern is fragile** -- FIXED
  `jobs/steps/base.py:77-100`
  After `db.rollback()`, ORM objects may be detached. The subsequent `db.commit()` can fail, leaving jobs stuck in "running" forever.
  **Fix applied:** After rollback, re-attach ORM objects via `db.merge()` before updating failure state. Added try/except around failure persistence so the original error is never masked. Also sets `job.completed_at` on failure.

- [x] **18. Redis pool not closed on enqueue failure** -- FIXED
  `jobs/crawl_job.py:165-174`
  If `enqueue_job` raises, `redis_pool.close()` is never called.
  **Fix applied:** Wrapped in `try/finally` with `redis_pool` initialized to `None` before the try block.

- [x] **19. Validate step context mutations may not persist** -- FIXED
  `jobs/steps/step_04_validate.py:46-71`
  `ctx` dict modified without `flag_modified(job, 'context')`. SQLAlchemy may not detect changes.
  **Fix applied:** Added `flag_modified(job, "context")` before both `await db.commit()` calls in the validate step's `run()` method.

- [x] **20. Non-atomic upsert in finalize step** -- FIXED
  `jobs/steps/step_05_finalize.py:321-379`
  `SELECT` then `INSERT/UPDATE` race condition with concurrent extract workers.
  **Fix applied:** Rewrote `_save_netzentgelte` and `_save_hlzf` to use PostgreSQL `INSERT ... ON CONFLICT DO UPDATE` (bulk upsert). Added unique indexes on `(dno_id, year, voltage_level)` for both tables. Verified records are skipped unless `force_override` is set.

- [x] **21. Enrichment job uses wrong Redis queue name** -- FIXED
  `jobs/enrichment_job.py:295-296`
  Jobs enqueued to `"arq:queue"` but `CrawlWorkerSettings` listens on `"crawl"` queue.
  **Fix applied:** Changed `_queue_name` from `"arq:queue"` to `"crawl"` in both `queue_enrichment_jobs()` and `enqueue_enrichment_job()`.

- [x] **22. OAuth state stored in process memory** -- FIXED
  `api/routes/oauth.py:111`
  States lost on restart, don't work across workers, no expiration (memory leak).
  **Fix applied:** Added 10-minute TTL for OAuth states, automatic cleanup of expired entries, and a cap of 50 concurrent pending flows. TTL checked both on creation and consumption.

- [x] **23. JWKS cache thundering herd** -- FIXED
  `core/auth.py:25-27`
  Multiple concurrent requests can all refresh JWKS cache simultaneously.
  **Fix applied:** Added `asyncio.Lock` with double-check pattern. After acquiring lock, re-checks cache validity to avoid redundant fetches.

### Data Integrity

- [x] **24. `datetime.utcnow()` mixed with `datetime.now(UTC)`** -- FIXED
  Multiple files across backend
  Naive vs aware datetimes can cause comparison failures.
  **Fix applied:** Replaced all `datetime.utcnow()` with `datetime.now(UTC)` across 11 files: base.py, crawl_job.py, extract_job.py, search_job.py, step_05_finalize.py, crawl_recovery.py, sample_capture.py, pattern_learner.py, admin.py, crawl.py, models.py. Added `UTC` import from `datetime` module in each file.

- [x] **25. Float used for financial data** -- FIXED
  `db/models.py:335-340`
  Netzentgelte prices stored as `Float` (IEEE 754) instead of `Numeric`. Subject to rounding errors.
  **Fix applied:** Changed all 4 price columns (`arbeit`, `leistung`, `arbeit_unter_2500h`, `leistung_unter_2500h`) from `Float` to `Numeric(10, 4)` with `Decimal` type annotation. DB is recreated from scratch in dev so no migration needed.

- [x] **26. `parse_german_number` ambiguity** -- DOCUMENTED
  `core/parsers.py:51-60`
  `"1.234"` could be German 1234 or US 1.234. No contextual disambiguation.
  **Fix applied:** Added detailed docstring documenting the ambiguity. Both dot and comma are used as decimal delimiters in the data, so no heuristic can reliably distinguish them. Accepted as known limitation.

### Performance

- [x] **27. N+1 queries in admin file listing** -- FIXED
  `api/routes/admin.py:292-308`
  Separate DB query per file in bulk operations. Thousands of queries per request.
  **Fix applied:** Batch-load all verification statuses, failed jobs, and active jobs upfront into dicts/sets. Rewrote `list_cached_files`, `preview_bulk_extract`, and `trigger_bulk_extract`.

- [x] **28. N+1 queries in finalize step** -- FIXED
  `jobs/steps/step_05_finalize.py:312-328`
  Separate SELECT per record during upsert.
  **Fix applied:** Eliminated per-record SELECT by switching to bulk `INSERT ... ON CONFLICT DO UPDATE` (see #20).

- [x] **29. Blocking file I/O in async context** -- FIXED
  `jobs/steps/step_02_download.py:146,154` + `step_03_extract.py:490`
  Synchronous `write_bytes`/`read_text` blocks the event loop for large files.
  **Fix applied:** Wrapped `write_text`, `write_bytes`, and `read_text` calls in `asyncio.to_thread()`.

- [x] **30. httpx client created per request in VNB/BDEW clients** -- FIXED
  `services/vnb/client.py`, `services/bdew_client.py`
  New TCP connection pool per API call. Wastes connections.
  **Fix applied:** Added shared `httpx.AsyncClient` with lazy initialization (`_get_client()`) and cleanup (`close()`) to both clients.

- [x] **31. Hardcoded `application/pdf` media type for all file downloads** -- FIXED
  `api/routes/files.py:54`
  HTML, XLSX, CSV files served with wrong Content-Type.
  **Fix applied:** Uses `mimetypes.guess_type()` to detect media type from file extension. Falls back to `application/octet-stream`.

### API Design

- [x] **32. `success=False` returned with HTTP 200** -- FIXED
  `api/routes/ai.py:239,262`
  Not-found responses return 200 with logical failure instead of 404.
  **Fix applied:** Changed to raise `HTTPException(404)` for not-found configs in both `update_config` and `delete_config`.

- [x] **33. Unused `year`/`data_type` query params in `get_dno_data`** -- FIXED
  `api/routes/dnos/data.py:27-28`
  Parameters declared but never used for filtering.
  **Fix applied:** Removed unused `year` and `data_type` query parameters and their imports.

- [x] **34. Post-fetch status filtering breaks pagination** -- FIXED
  `api/routes/dnos/crud.py:496-547`
  Dynamic status filtering happens after fetch, making total/page counts wrong.
  **Fix applied:** Replaced post-fetch filtering with SQL-level EXISTS/NOT EXISTS subqueries on `crawl_jobs`, `netzentgelte`, and `hlzf` tables. Count query now includes the same filter, giving accurate pagination.

- [x] **35. Inconsistent response formats** -- FIXED
  `api/routes/jobs.py:32 vs 127`
  `list_jobs` returns raw dict, `get_job` returns `APIResponse` wrapper.
  **Fix applied:** Changed `list_jobs` return type to `APIResponse` wrapper with `data` and `meta` fields.

---

## LOW Severity

### Security

- [x] **36. Path traversal risk via `dno_slug` in filesystem paths** -- FIXED
  `jobs/steps/step_00_gather_context.py:48`, `step_02_download.py:92-93`
  Slug used directly in `Path()` construction without sanitization.
  **Fix applied:** Added `@validates("slug")` on DNOModel that rejects slugs not matching `[a-z0-9][a-z0-9\-]*`. Added `Path.resolve().is_relative_to()` checks in download step, gather context step, and file upload endpoint.

- [x] **37. Error messages leak internal paths/details** -- FIXED
  `database.py:100`, `auth.py:188`, `ai.py:372`, `crawl_job.py:122`
  Raw exception strings returned to clients.
  **Fix applied:** Removed `str(e)` from HTTP error details in `database.py` (generic 500 handler) and `import_export.py` (import failure). Auth and AI error details were already sanitized in previous fixes (#1 and #9).

- [x] **38. Filesystem paths exposed in admin API** -- FIXED
  `api/routes/admin.py:222`
  Absolute server paths returned in API responses.
  **Fix applied:** `_parse_file_info` now returns relative path (`{dno_slug}/{filename}`) instead of absolute filesystem path.

- [x] **39. `window.open` with user-controlled URL** -- FIXED
  `frontend/src/pages/DNOsPage.tsx:753`
  `dno.website` from API could contain `javascript:` URL.
  **Fix applied:** Added regex check `^https?:\/\/` before `window.open()`. Also added `noopener,noreferrer` to the window features.

### Reliability

- [x] **40. Readiness endpoint hardcodes "connected"** -- FIXED
  `api/routes/health.py:16-24`
  Reports DB/Redis as connected without actually checking.
  **Fix applied:** Readiness endpoint now calls `check_database_health()` (SELECT 1) and `redis.ping()`. Returns `"degraded"` status if either check fails.

- [x] **41. Missing `completed_at` on job failure** -- FIXED
  `jobs/crawl_job.py`, `extract_job.py`, `search_job.py`
  Failed jobs never get `completed_at` set.
  **Fix applied:** BaseStep error handler now sets `job.completed_at` via merge. All three job orchestrators (crawl, extract, search) also set `completed_at` as a fallback for non-step errors. Recovery service (`crawl_recovery.py`) now sets `completed_at` when resetting stuck jobs.

- [x] **42. Extract job DNO lock may never release on DB failure** -- FIXED
  `jobs/extract_job.py:112-118`
  If DB session is broken, lock release fails silently. DNO stuck in "crawling" forever.
  **Fix applied:** `_release_dno_lock()` now opens a fresh DB session (`get_db_session()`) instead of reusing the potentially broken parent session. Error logging upgraded from `warning` to `error`.

- [x] **43. `enrichment_job.py` uses `get_db()` instead of `get_db_session()`** -- FIXED
  `jobs/enrichment_job.py:57`
  FastAPI dependency generator used outside FastAPI context.
  **Fix applied:** Replaced `async for db in get_db()` with `async with get_db_session() as db`.

- [x] **44. PyMuPDF document handle not in try/finally** -- FIXED
  `jobs/steps/step_03_extract.py:469-473`
  If `len(doc)` raises, `doc.close()` never called.
  **Fix applied:** Wrapped `len(doc)` in try/finally to ensure `doc.close()` is always called.

- [x] **45. `retry-after` header parsed as float without validation** -- FIXED
  `jobs/steps/step_02_download.py:191`
  Crashes on date-format `retry-after` headers (RFC 7231).
  **Fix applied:** Wrapped `float()` call in try/except, falling back to 5 seconds on parse failure.

- [ ] **46. No idempotency guarantees for jobs**
  Pipeline re-executes fully on ARQ retry after worker crash.
  **Status:** TODO for v1.1. Requires checkpoint/resume capability.

- [x] **47. Redis INCR + EXPIRE not atomic** -- FIXED
  `core/rate_limiter.py:64-66`
  Process crash between INCR and EXPIRE permanently blocks the IP.
  **Fix applied:** Both IP rate limit and VNB quota now use Redis `pipeline(transaction=True)` to execute INCR + EXPIRE atomically.

### Code Quality

- [ ] **48. Duplicate type definitions drift (frontend)**
  `api.ts` vs `types/` directory -- types are not identical, causing type narrowing issues.
  **Status:** POSTPONED for v1.1. Risk of breaking working code. Types in `types/` directory are more complete; `api.ts` types should eventually be replaced with imports from `types/`.

- [ ] **49. LandingPage and SearchPage ~80% identical**
  `frontend/src/pages/LandingPage.tsx` + `SearchPage.tsx`
  Should extract shared `SearchForm` component.
  **Status:** POSTPONED for v1.1. Significant refactoring risk; pages have subtle differences (LandingPage has auth/login, SearchPage has different navigation).

- [x] **50. Duplicate `TimestampMixin` defined in two DB model files** -- FIXED
  `db/models.py` + `db/source_models.py`
  **Fix applied:** Removed duplicate definition from `source_models.py`, now imports `TimestampMixin` from `models.py`.

- [ ] **51. Duplicate validation logic between extract and validate steps**
  `step_03_extract.py:383-429` + `step_04_validate.py:80-205`
  Slightly different rules, causing inconsistencies.
  **Status:** POSTPONED for v1.1. Requires careful extraction to shared module without breaking existing behavior.

- [ ] **52. Three different job orchestration patterns**
  `crawl_job.py`, `extract_job.py`, `search_job.py`
  Nearly identical orchestration logic should be a shared base function.
  **Status:** POSTPONED for v1.1. Refactoring risk; each job type has subtle differences in error handling.

- [x] **53. f-string logging defeats structured logging** -- FIXED
  `services/extraction/pdf_extractor.py` (multiple lines)
  Should use structlog keyword arguments instead.
  **Fix applied:** Converted all f-string log calls in `pdf_extractor.py` to structlog keyword arguments (e.g., `log.info("pdf_opened", page_count=N)`).

- [x] **54. Duplicate enum/Literal type definitions** -- DOCUMENTED
  `core/models.py` vs `core/constants.py`
  No single source of truth for status enums.
  **Fix applied:** Added cross-reference comments in `constants.py` noting sync requirement with `core/models.py`. Flagged `VerificationStatus` mismatch (`models.py` includes "rejected").

- [x] **55. `normalize_voltage_level` unreachable code** -- FIXED
  `jobs/steps/step_05_finalize.py:222-230`
  Exact-match checks already handled by earlier `in` check.
  **Fix applied:** Removed the unreachable exact-match block for HS, MS, NS, HS/MS, MS/NS.

- [x] **56. Regex re-compiled on every call in `normalize_voltage_level`** -- FIXED
  `core/constants.py:117-129`
  `re` imported inside function, patterns not pre-compiled.
  **Fix applied:** Moved `re` import to module level. Pre-compiled `_RE_WHITESPACE`, `_RE_SEPARATOR`, and `_RE_PARENS` patterns at module scope.

### Frontend

- [ ] **57. No ARIA attributes on custom interactive elements**
  Frontend-wide -- custom buttons, dropdowns, filters lack `role`, `aria-pressed`, `aria-expanded`.
  **Status:** POSTPONED for v1.1. Requires systematic audit of all interactive components.

- [x] **58. Loading spinners have no screen reader text** -- FIXED
  `ProtectedRoute.tsx`, `AuthCallback.tsx`, `DashboardPage.tsx`, etc.
  **Fix applied:** Added `role="status"`, `aria-busy="true"`, and `<span className="sr-only">` text to all loading spinners in ProtectedRoute.tsx, AuthCallback.tsx, and App.tsx. Created reusable `Spinner` component in `components/ui/spinner.tsx`.

- [x] **59. Mutations without `onError` handlers** -- FIXED
  `DNODetailPage.tsx:113-128`, `DataExplorer.tsx:59-87`
  Failed API calls give users no feedback.
  **Fix applied:** Added `onError` handlers with destructive toast notifications to all mutations in both files.

- [x] **60. Blob URL never revoked after export download** -- FIXED
  `features/dno-detail/views/DataExplorer.tsx:99-103`
  Memory leak from `URL.createObjectURL`.
  **Fix applied:** Added `window.URL.revokeObjectURL(url)` after the download click.

- [x] **61. 401 interceptor redirect loop risk** -- FIXED
  `frontend/src/lib/api.ts:47-61`
  No debounce on 401 redirect. Root page API call returning 401 causes infinite loop.
  **Fix applied:** Added `_isRedirecting` guard flag that prevents multiple 401 redirects. Once the first 401 triggers a redirect, subsequent 401 responses are ignored (the page is already navigating away).

- [x] **62. DNOsPage polls every 5s unconditionally** -- FIXED
  `frontend/src/pages/DNOsPage.tsx:117`
  Should only poll when active jobs exist.
  **Fix applied:** `refetchInterval` is now conditional on `hasActiveJobs` state. Only polls every 5s when DNOs with "running" or "pending" status exist in the current page. Otherwise polling is disabled.

- [x] **63. `login()` called as side effect during render** -- FIXED
  `frontend/src/App.tsx:25-47`
  Should be in `useEffect`.
  **Fix applied:** Moved `login()` call into `useEffect` with `[isLoading, isAuthenticated, login]` dependencies.

- [x] **64. `DNOCard` not memoized with 5s polling** -- FIXED
  `frontend/src/pages/DNOsPage.tsx:680`
  50-250 cards re-render on every poll even when data unchanged.
  **Fix applied:** Wrapped `DNOCard` in `React.memo()` to skip re-renders when props haven't changed.

---

## Notes

- **Crawl-delay directive** from robots.txt is not respected (`services/robots_parser.py`). Consider parsing and honoring it.
- **Content verifier** makes HTTP requests without rate limiting or robots.txt checking, separate from crawler politeness.
- **AI prompt injection** risk exists via DNO names from VNB API interpolated into extraction prompts (`services/extraction/prompts/__init__.py`).
- **No AI output schema validation** -- hallucinated prices could pass through undetected.
- **`ai_seeder.py`** unconditionally overwrites admin's manual config changes on every restart.
- **`BaseHTTPMiddleware`** has known performance issues and ContextVar propagation bugs in Starlette.

---

## Further Discoveries (2026-02-14)

### CRITICAL Severity

- [x] **65. `User.sub` AttributeError in data routes** -- FIXED
  `api/routes/dnos/data.py:182, 274` + `api/middleware/wide_events.py:129`
  The `User` dataclass (`core/auth.py:35-42`) has `id`, `email`, `name`, `roles` attributes. The JWT `sub` claim is mapped to `id`. Code accesses `current_user.sub` which will raise `AttributeError` at runtime.
  **Fix applied:** Changed `current_user.sub` to `current_user.id` in `data.py` (lines 182, 274) and `wide_events.py` docstring example.

### HIGH Severity

- [x] **66. PyMuPDF document handle not closed on exception** -- FIXED
  `services/content_verifier.py:698-720`
  In `_try_pymupdf`, if an exception occurs after `fitz.open()` but before `doc.close()`, the document handle leaks. Same pattern was fixed in `step_03_extract.py` (issue #44) but this location was missed.
  **Fix applied:** Wrapped `doc.close()` in try/finally to ensure it's always called.

- [x] **67. Memory leak in RobotsChecker cache** -- FIXED
  `services/url_utils.py:218`
  `RobotsChecker._cache` is an unbounded dict with no TTL. Long-running workers accumulate memory indefinitely.
  **Fix applied:** Added TTL-based eviction (1 hour), max size limit (500 domains), and automatic cleanup of expired entries.

- [x] **68. Sitemap retry inner function recreated per loop iteration** -- FIXED
  `services/discovery/sitemap.py:93-98`
  Inner function `_fetch_sitemap_url` recreated on every loop iteration. Works correctly but inefficient and confusing pattern.
  **Fix applied:** Function now properly receives URL as argument via `with_retries` *args. Renamed loop variable to `sitemap_url` for clarity.

### MEDIUM Severity

- [x] **69. Blocking I/O in pdf_extractor.py** -- FIXED
  `services/extraction/pdf_extractor.py:39-57`
  `pdfplumber.open()` and page extraction are synchronous operations that block the event loop. Issue #29 fixed this in `step_03_extract.py` but the service file was missed.
  **Fix applied:** Added async wrappers `extract_netzentgelte_from_pdf_async()` and `extract_hlzf_from_pdf_async()` that wrap the synchronous functions in `asyncio.to_thread()`.

- [x] **70. File downloaded before size check** -- FIXED
  `services/content_verifier.py:393-396`
  `response.content` loads entire file into memory before checking size limits. Servers without `content-length` header could cause memory exhaustion.
  **Fix applied:** Changed to streaming download with `client.stream("GET", ...)` and `aiter_bytes()` to check size incrementally. File is now rejected as soon as it exceeds max_size.

- [x] **71. MD5 used for file hashing** -- DOCUMENTED
  `services/content_verifier.py:290, 313-314`
  MD5 is cryptographically broken. Currently used only for deduplication cache keys (not security), but should document this or switch to SHA-256.
  **Fix applied:** Added comments documenting that MD5 is used only for deduplication cache keys, not for security/cryptography. The hash is used to identify duplicate files.

### LOW Severity

- [x] **72. Verification endpoints accessible by all authenticated users** -- ACCEPTED
  `api/routes/verification.py`
  Any authenticated user can verify/flag data without role check.
  **Decision:** Intentional design. This is a private instance where normal users are trusted/invited. Only unflag requires Maintainer/Admin role.

- [x] **73. Inconsistent HLZF verification_notes handling** -- FIXED
  `api/routes/verification.py:257-267, 281`
  Netzentgelte verify endpoint uses `verification_notes` field, HLZF endpoint ignores it and always returns `None`.
  **Fix applied:** Added `verification_notes` column to `HLZFModel` and updated all HLZF verification endpoints to properly handle the notes field.

- [x] **74. Weak coordinate parsing in frontend** -- FIXED
  `frontend/src/pages/LandingPage.tsx:85-96`
  `parseFloat` with simple comma-to-dot replacement may accept malformed coordinates without clear error.
  **Fix applied:** Added regex validation for coordinate format, proper range checking with clear error messages, and a `getCoordinateError()` function that displays specific validation errors to users.
