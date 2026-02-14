# DNO Crawler -- Code Review

**Date:** 2026-02-11
**Scope:** Full-stack review (backend + frontend)

> **Note:** Members in this project's private Zitadel instance are trusted/invited users.
> Member-level access for uploads, imports, and verification is intentional.

---

## Completed Fixes

| # | Severity | Issue | Fix |
|---|----------|-------|-----|
| 1 | CRITICAL | Auth disabled when `ZITADEL_DOMAIN` unset -- mock admin on all endpoints | Added `is_production` check; returns 503 in prod instead of mock admin |
| 2 | CRITICAL | XSS in OAuth callback -- unescaped user data in HTML, wildcard `postMessage` | HTML-escaped all values; `postMessage` uses specific origin |
| 3 | CRITICAL | XXE in sitemap parser via `ElementTree.fromstring()` | Replaced with `defusedxml.ElementTree.fromstring()` |
| 4 | CRITICAL | Unbounded file upload -- `await file.read()` with no size limit | Streaming 250MB limit with extension allowlist |
| 5 | CRITICAL | Hardcoded fallback encryption key for AI API keys | Production raises `RuntimeError` if no key; key derivation uses HKDF |
| 6 | HIGH | No React Error Boundaries -- white screen on any render error | Added `ErrorBoundary` component at app and route level |
| 7 | HIGH | No SSRF protection in content verifier -- fetches arbitrary URLs | Added `validate_url_ssrf_safe()` with private IP/port checks |
| 8 | HIGH | DOCX always misidentified as XLSX due to early return in magic bytes loop | Removed `PK\x03\x04` from `MAGIC_BYTES`; falls through to ZIP refinement |
| 9 | HIGH | API key leak in AI test error messages via `str(e)` | Added `_sanitize_error()` that strips key patterns from messages |
| 10 | MEDIUM | ILIKE wildcard injection -- `%` returns all records | Escape `%`, `_`, `\` before ILIKE patterns |
| 11 | MEDIUM | X-Forwarded-For trusted unconditionally in rate limiter | Rightmost-N approach with `TRUSTED_PROXY_COUNT` setting |
| 12 | MEDIUM | JWT audience verification disabled (`verify_aud: False`) | Added `ZITADEL_CLIENT_ID` setting; enables audience check when configured |
| 13 | MEDIUM | Token in localStorage (XSS-accessible) | **Accepted** -- known SPA + PKCE trade-off for trusted-user model |
| 14 | MEDIUM | `dangerouslySetInnerHTML` with SVG content in admin panel | Added DOMPurify sanitization with SVG profile |
| 15 | MEDIUM | Rate limiter silently disabled on Redis failure | Changed to `log.error` with structured event for observability |
| 16 | MEDIUM | Crawl lock bypass -- concurrent crawl could start within 1hr window | Added `else` branch raising 409 Conflict |
| 17 | MEDIUM | BaseStep rollback-then-commit pattern -- detached ORM objects | `db.merge()` after rollback; try/except around failure persistence |
| 18 | MEDIUM | Redis pool not closed on enqueue failure | `try/finally` with `redis_pool.close()` |
| 19 | MEDIUM | Validate step context mutations not persisted by SQLAlchemy | Added `flag_modified(job, "context")` before commits |
| 20 | MEDIUM | Non-atomic upsert in finalize step -- SELECT then INSERT race | `INSERT ... ON CONFLICT DO UPDATE` with unique indexes |
| 21 | MEDIUM | Enrichment job enqueued to wrong Redis queue name | Changed `_queue_name` from `"arq:queue"` to `"crawl"` |
| 22 | MEDIUM | OAuth state stored in process memory -- no TTL, no expiration | Added 10-min TTL, expired entry cleanup, 50-flow cap |
| 23 | MEDIUM | JWKS cache thundering herd -- multiple concurrent refreshes | `asyncio.Lock` with double-check pattern |
| 24 | MEDIUM | `datetime.utcnow()` mixed with `datetime.now(UTC)` across 11 files | Replaced all with `datetime.now(UTC)` |
| 25 | MEDIUM | Float used for financial data (Netzentgelte prices) | Changed to `Numeric(10, 4)` with `Decimal` type |
| 26 | MEDIUM | `parse_german_number` ambiguity (`"1.234"` = 1234 or 1.234?) | **Documented** -- no reliable heuristic; accepted as known limitation |
| 27 | MEDIUM | N+1 queries in admin file listing (thousands of queries) | Batch-load all statuses upfront into dicts/sets |
| 28 | MEDIUM | N+1 queries in finalize step (per-record SELECT) | Eliminated via bulk `INSERT ... ON CONFLICT` (see #20) |
| 29 | MEDIUM | Blocking file I/O in async context (`write_bytes`/`read_text`) | Wrapped in `asyncio.to_thread()` |
| 30 | MEDIUM | httpx client created per request in VNB/BDEW clients | Shared `AsyncClient` with lazy init and `close()` |
| 31 | MEDIUM | Hardcoded `application/pdf` for all file downloads | `mimetypes.guess_type()` with `application/octet-stream` fallback |
| 32 | MEDIUM | `success=False` returned with HTTP 200 for not-found | Changed to `HTTPException(404)` |
| 33 | MEDIUM | Unused `year`/`data_type` query params in `get_dno_data` | Removed unused parameters |
| 34 | MEDIUM | Post-fetch status filtering breaks pagination counts | SQL-level EXISTS/NOT EXISTS subqueries |
| 35 | MEDIUM | Inconsistent response formats (`list_jobs` raw dict vs `APIResponse`) | Changed to `APIResponse` wrapper |
| 36 | LOW | Path traversal risk via `dno_slug` in filesystem paths | Slug regex validation + `Path.resolve().is_relative_to()` checks |
| 37 | LOW | Error messages leak internal paths/details | Removed `str(e)` from HTTP error details |
| 38 | LOW | Filesystem paths exposed in admin API | Returns relative path instead of absolute |
| 39 | LOW | `window.open` with user-controlled URL (possible `javascript:`) | Added `^https?:\/\/` check + `noopener,noreferrer` |
| 40 | LOW | Readiness endpoint hardcodes "connected" | Actual DB `SELECT 1` and `redis.ping()` checks |
| 41 | LOW | Missing `completed_at` on job failure | Set in BaseStep error handler + all three job orchestrators |
| 42 | LOW | Extract job DNO lock never releases on DB failure | Fresh DB session for lock release instead of reusing broken one |
| 43 | LOW | `enrichment_job.py` uses `get_db()` instead of `get_db_session()` | Replaced with `async with get_db_session() as db` |
| 44 | LOW | PyMuPDF document handle not in try/finally | Wrapped in try/finally |
| 45 | LOW | `retry-after` header parsed as float without validation | try/except with 5-second fallback |
| 47 | LOW | Redis INCR + EXPIRE not atomic in rate limiter | `pipeline(transaction=True)` for atomic execution |
| 50 | LOW | Duplicate `TimestampMixin` in two DB model files | Removed duplicate; imports from `models.py` |
| 53 | LOW | f-string logging defeats structured logging in pdf_extractor | Converted to structlog keyword arguments |
| 54 | LOW | Duplicate enum/Literal type definitions | **Documented** -- cross-reference comments added |
| 55 | LOW | `normalize_voltage_level` unreachable code | Removed unreachable block |
| 56 | LOW | Regex re-compiled on every call in `normalize_voltage_level` | Pre-compiled at module scope |
| 58 | LOW | Loading spinners have no screen reader text | Added `role="status"`, `aria-busy`, sr-only text; reusable `Spinner` component |
| 59 | LOW | Mutations without `onError` handlers -- no user feedback | Added `onError` with destructive toast notifications |
| 60 | LOW | Blob URL never revoked after export download -- memory leak | Added `URL.revokeObjectURL()` after download |
| 61 | LOW | 401 interceptor redirect loop risk | `_isRedirecting` guard flag prevents multiple redirects |
| 62 | LOW | DNOsPage polls every 5s unconditionally | Conditional on `hasActiveJobs` state |
| 63 | LOW | `login()` called as side effect during render | Moved to `useEffect` |
| 64 | LOW | `DNOCard` not memoized with 5s polling | Wrapped in `React.memo()` |
| 65 | HIGH | `User.sub` AttributeError -- JWT `sub` mapped to `id` but code uses `.sub` | Changed to `current_user.id` |
| 66 | HIGH | PyMuPDF handle not closed on exception in content_verifier | try/finally for `doc.close()` |
| 67 | HIGH | Unbounded RobotsChecker cache -- no TTL or size limit | 1hr TTL, 500-domain max, auto-cleanup |
| 68 | HIGH | Sitemap retry inner function recreated per loop iteration | Function receives URL as argument via `with_retries` *args |
| 69 | MEDIUM | Blocking I/O in pdf_extractor.py (missed by #29) | Async wrappers with `asyncio.to_thread()` |
| 70 | MEDIUM | File downloaded fully before size check in content_verifier | Streaming download with incremental size check |
| 71 | MEDIUM | MD5 used for file hashing | **Documented** -- used only for dedup cache keys, not security |
| 72 | LOW | Verification endpoints accessible by all authenticated users | **Accepted** -- intentional for trusted-user model |
| 73 | LOW | HLZF missing `verification_notes` handling | Added column and updated endpoints |
| 74 | LOW | Weak coordinate parsing in frontend | Regex validation + range checking with clear error messages |
| 75 | HIGH | Missing security response headers | Added `SecurityHeadersMiddleware` with `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `HSTS` (prod) |
| 76 | HIGH | CORS allows wildcard methods and headers | Replaced with explicit `["GET","POST","PUT","PATCH","DELETE","OPTIONS"]` and `["Content-Type","Authorization"]` |
| 77 | HIGH | Wide events middleware uses insecure leftmost IP | Reuses secure `get_client_ip()` from `core/rate_limiter.py`; removed old method |
| 78 | HIGH | VNBDigitalClient httpx connections never closed | `try/finally` with `await vnb_client.close()` in all crud.py endpoints |
| 79 | HIGH | No schema validation on AI extraction responses | `_parse_json_response` validates response is dict with `data` as list of dicts |
| 81 | MEDIUM | `STORAGE_PATH` read via `os.environ.get()` bypassing Settings | Replaced all 7 occurrences with `settings.storage_path`; removed unused `os` imports |
| 83 | MEDIUM | Bare `except Exception: pass` silently swallowing errors | Added `structlog` debug/error logging to 7 bare `pass` handlers in app/ |
| 84 | MEDIUM | File upload double-close and sync unlink | Removed explicit `close()`; async unlink via `asyncio.to_thread()` in except handler |
| 86 | MEDIUM | `useToast` re-subscribes on every state change | Changed `useEffect` dependency from `[state]` to `[]` |
| 87 | MEDIUM | Regex patterns recompiled per call in web crawler | Pre-compiled `_TOKEN_URL_PATTERNS` and `_YEAR_PATTERNS` at module level |
| 90 | LOW | Duplicate coordinate regex in LandingPage | Extracted shared `COORD_PATTERN` constant |

---

## Open Issues

### MEDIUM

- [ ] **82. Missing rate limiting on expensive admin endpoints**
  `api/routes/admin.py` -- Filesystem scans and bulk operations have no rate limiting.
  **Fix:** Per-user rate limiting on expensive admin operations.

- [ ] **85. Import rolls back all progress on partial failure**
  `api/routes/dnos/import_export.py:225-365` -- Single transaction for Netzentgelte + HLZF; HLZF failure discards all Netzentgelte progress.
  **Fix:** Commit per record type, use savepoints, or pre-validate all records.

### LOW

- [ ] **46. No idempotency guarantees for jobs**
  Pipeline re-executes fully on ARQ retry after worker crash.
  **Status:** TODO for v1.1.

- [ ] **48. Duplicate type definitions drift (frontend)**
  `api.ts` vs `types/` directory.
  **Status:** POSTPONED for v1.1.

- [ ] **49. LandingPage and SearchPage ~80% identical**
  Should extract shared `SearchForm` component.
  **Status:** POSTPONED for v1.1.

- [ ] **51. Duplicate validation logic between extract and validate steps**
  `step_03_extract.py` + `step_04_validate.py` -- slightly different rules.
  **Status:** POSTPONED for v1.1.

- [ ] **52. Three different job orchestration patterns**
  Nearly identical logic across `crawl_job.py`, `extract_job.py`, `search_job.py`.
  **Status:** POSTPONED for v1.1.

- [ ] **57. No ARIA attributes on custom interactive elements**
  **Status:** POSTPONED for v1.1.

- [ ] **80. AI prompt injection via DNO names**
  `services/extraction/prompts/__init__.py:14, 77` -- VNB API names interpolated into AI prompts. **Downgraded:** AI is OpenRouter-only with max tokens, no tools. Worst case is malformed output, mitigated by #79 validation.

- [ ] **88. German number regex silently skips thousands-separator values**
  `services/extraction/pdf_extractor.py:97` -- `float("1.234.56")` raises ValueError, caught but not logged.

- [ ] **89. HTML stripper year pattern is overly specific**
  `services/extraction/html_stripper.py:42` -- Only matches `"gültig ab 01.01.XXXX"`.

- [ ] **91. Enrichment job doesn't check for concurrent crawl**
  `jobs/enrichment_job.py:66-67` -- Could update shared fields simultaneously.

- [ ] **92. OAuth state fallback to `"null"` string when `cors_origins` empty**
  `api/routes/oauth.py` -- Invalid `postMessage` origin on misconfigured deployment.

---

## Notes

- **Crawl-delay directive** from robots.txt is not respected (`services/robots_parser.py`).
- **Content verifier** makes HTTP requests without rate limiting or robots.txt checking.
- **`ai_seeder.py`** unconditionally overwrites admin's manual config changes on every restart.
- **`BaseHTTPMiddleware`** has known performance issues and ContextVar propagation bugs in Starlette.
