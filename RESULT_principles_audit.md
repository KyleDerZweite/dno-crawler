# Engineering Principles Audit

## Executive Summary

The codebase is generally well-structured with clear separation of concerns and good use of domain modeling. However, several principle violations exist, primarily around DRY (duplicated types, repeated code patterns), Single Responsibility (oversized route handlers), and YAGNI (unused abstractions). The most impactful findings are the massive type duplication between `lib/api.ts` and `types/` on the frontend, and the repeated "skeleton creation + robots.txt + impressum" pattern in `search.py`.

---

## 1. Simplicity and Scope

### 1.1 KISS Violations

**[HIGH] F-001: SecurityHeadersMiddleware defined inline inside `create_app()`**
- File: `/home/kyle/CodingProjects/dno-crawler/backend/app/api/main.py`, lines 143-153
- A class is defined inside a function body. While functional, it violates readability norms and is harder to test.
- Fix: Move `SecurityHeadersMiddleware` to `app/api/middleware/` alongside `WideEventMiddleware`.

**[LOW] F-002: Dynamic `locals()` check in `create_dno`**
- File: `/home/kyle/CodingProjects/dno-crawler/backend/app/api/routes/dnos/crud.py`, lines 362-363
- `tech_info if website and "tech_info" in locals()` uses `locals()` introspection, which is fragile and hard to follow. The variable `robots_task` is also created but never awaited (line 323).
- Fix: Initialize `tech_info = None` before the `if website:` block and assign conditionally. Remove the unused `robots_task` variable.

**[LOW] F-003: Hardcoded known PDF URLs in extraction module**
- File: `/home/kyle/CodingProjects/dno-crawler/backend/app/services/extraction/pdf_extractor.py`, lines 279-311
- `find_pdf_url_for_dno()` contains hardcoded URLs for "netze bw". This is a maintenance liability and mixes configuration with logic.
- Fix: Move to a configuration file or database lookup. If this is test data, mark it clearly or restrict to test scope.

### 1.2 YAGNI Violations

**[MEDIUM] F-004: `AuthSettings` backwards compatibility wrapper is unnecessary indirection**
- File: `/home/kyle/CodingProjects/dno-crawler/backend/app/core/config.py`, lines 169-181
- `AuthSettings` wraps `settings` properties with identical signatures. No code path requires a separate `AuthSettings` instance; all consumers could use `settings` directly.
- Fix: Remove `AuthSettings` class. Update `auth.py` to import `settings` and use `settings.zitadel_issuer` / `settings.zitadel_jwks_url` directly.

**[LOW] F-005: `AIProvider` enum in `core/models.py` is unused by actual provider system**
- File: `/home/kyle/CodingProjects/dno-crawler/backend/app/core/models.py`, lines 122-128
- The `AIProvider` enum lists hardcoded providers (Gemini, OpenAI, Anthropic, Ollama), but the actual provider system uses dynamic registration via `PROVIDER_REGISTRY` and database-stored `provider_type` strings. This enum is dead code.
- Fix: Remove `AIProvider` enum from `core/models.py`.

**[LOW] F-006: `get_available_years()` in constants is unused**
- File: `/home/kyle/CodingProjects/dno-crawler/backend/app/core/constants.py`, lines 223-230
- No call site found. The `MAX_YEAR = 2030` constant on line 220 is also speculative.
- Fix: Remove if unused, or verify call sites.

---

## 2. Architecture and Design

### 2.1 Single Responsibility Violations

**[HIGH] F-007: `admin.py` route handler `trigger_bulk_extract` is 210+ lines and does file scanning, status lookup, job creation, and Redis enqueueing**
- File: `/home/kyle/CodingProjects/dno-crawler/backend/app/api/routes/admin.py`, lines 584-795
- This function performs at least 5 distinct responsibilities: file system scanning, batch status loading, extraction mode filtering, job creation, and Redis queue management.
- Fix: Extract into a service layer (`services/bulk_extraction.py`) with methods like `scan_files()`, `filter_by_mode()`, `create_jobs()`, and `enqueue_jobs()`.

**[HIGH] F-008: `list_dnos_detailed` in `crud.py` is 300+ lines**
- File: `/home/kyle/CodingProjects/dno-crawler/backend/app/api/routes/dnos/crud.py`, lines 428-722
- Combines search logic, fuzzy matching configuration, batch data fetching, status computation, and response building.
- Fix: Extract search query building, status computation, and response serialization into separate functions or a service class.

**[MEDIUM] F-009: `get_dno_details` in `crud.py` manually serializes 3 source data objects inline**
- File: `/home/kyle/CodingProjects/dno-crawler/backend/app/api/routes/dnos/crud.py`, lines 725-914
- Building mastr_data, vnb_data, and bdew_data dicts inline clutters the endpoint. Each serialization block is 20-30 lines.
- Fix: Create serializer functions (`_serialize_mastr_data(m)`, `_serialize_vnb_data(v)`, `_serialize_bdew_data(b)`) or use Pydantic response models.

**[MEDIUM] F-010: `search.py` contains both API route handlers and utility functions (`_parse_hlzf_times`)**
- File: `/home/kyle/CodingProjects/dno-crawler/backend/app/api/routes/search.py`, lines 132-188
- The `_parse_hlzf_times` function is imported by `data.py` (line 92), making `search.py` a dependency for `data.py`. Utility parsing logic should not live in a route module.
- Fix: Move `_parse_hlzf_times` to `app/core/parsers.py` or `app/services/extraction/validation.py`.

### 2.2 Separation of Concerns Violations

**[HIGH] F-011: `create_dno` endpoint performs HTTP calls, robots.txt parsing, and impressum extraction inline**
- File: `/home/kyle/CodingProjects/dno-crawler/backend/app/api/routes/dnos/crud.py`, lines 238-388
- Route handlers should delegate I/O to services. This endpoint creates httpx clients, calls `fetch_robots_txt`, `fetch_site_tech_info`, and `impressum_extractor` directly.
- Fix: Extract a `DNOCreationService` that handles VNB lookup, robots analysis, and impressum enrichment.

**[MEDIUM] F-012: `list_cached_files` and `preview_bulk_extract` both duplicate file scanning logic**
- File: `/home/kyle/CodingProjects/dno-crawler/backend/app/api/routes/admin.py`, lines 253-374 and 402-581
- Both endpoints independently iterate the downloads directory, parse file names, and look up verification statuses. The scanning loop is near-identical.
- Fix: Extract a shared `scan_cached_files(downloads_path, dnos, status_lookup, filters)` function.

### 2.3 Open/Closed Principle Violations

**[MEDIUM] F-013: Verification endpoints are duplicated for each data type instead of being generic**
- File: `/home/kyle/CodingProjects/dno-crawler/backend/app/api/routes/verification.py`
- The file contains 6 endpoints that are identical in structure, differing only in the model class (`NetzentgelteModel` vs `HLZFModel`). Adding a new data type would require copying all 6 handlers.
- Fix: Create a generic verification function parameterized by model class, then register thin wrappers per data type.

---

## 3. Logic and Maintenance

### 3.1 DRY Violations

**[HIGH] F-014: Frontend types duplicated between `lib/api.ts` and `types/` directory**
- Files: `/home/kyle/CodingProjects/dno-crawler/frontend/src/lib/api.ts` and `/home/kyle/CodingProjects/dno-crawler/frontend/src/types/dno.types.ts`, `/home/kyle/CodingProjects/dno-crawler/frontend/src/types/data.types.ts`
- The `DNO`, `Netzentgelte`, `HLZF`, `HLZFTimeRange`, `MastrData`, `VnbData`, `BdewData`, `AddressComponents`, `VNBSuggestion`, `VNBDetails`, `VerificationResponse`, `PublicSearchRequest`, `PublicSearchResponse`, `PublicSearchDNO`, `PublicSearchLocation`, `PublicSearchNetzentgelte`, `PublicSearchHLZF`, `Job`, `JobDetails`, `JobStep` interfaces are all fully duplicated.
- The `api.ts` file even has a comment (line 5): "New code should prefer importing from '@/types'", yet still contains ~300 lines of duplicated type definitions.
- Fix: Remove all type definitions from `lib/api.ts`. Import from `@/types` exclusively. Update all consumers.

**[HIGH] F-015: Backend constants duplicate enums from `core/models.py`**
- File: `/home/kyle/CodingProjects/dno-crawler/backend/app/core/constants.py`, lines 173-206, 247-248
- `DataType`, `JobStatus`, `DNOStatus`, `VerificationStatus` are defined as both `StrEnum` classes in `core/models.py` and `Literal` types + tuples in `core/constants.py`. The comment on line 174 acknowledges this: "NOTE: Literal types below must stay in sync with Enum classes in core/models.py."
- Fix: Use the `StrEnum` classes as the single source of truth. Derive `Literal` types programmatically or eliminate the parallel definitions.

**[HIGH] F-016: Robots.txt fetch + impressum enrichment duplicated 4 times in `search.py`**
- File: `/home/kyle/CodingProjects/dno-crawler/backend/app/api/routes/search.py`
- The pattern of creating an httpx client, calling `fetch_robots_txt`, and calling `impressum_extractor.extract_full_address` is repeated nearly identically in `_search_by_address` (lines 417-428), `_search_by_coordinates` (lines 520-532), `_search_by_dno` (lines 662-674), and also in `crud.py:create_dno` (lines 312-341).
- Fix: Extract a helper function like `async def enrich_dno_info(website: str, address: str | None) -> EnrichmentResult` that handles robots.txt + impressum in one call.

**[MEDIUM] F-017: `_build_completeness_payload` in `crud.py` duplicates logic from `search.py:_build_response`**
- File: `/home/kyle/CodingProjects/dno-crawler/backend/app/api/routes/dnos/crud.py`, lines 91-138 and `/home/kyle/CodingProjects/dno-crawler/backend/app/api/routes/search.py`, lines 785-806
- Both independently query voltage levels, build connection_points dict, and call `compute_completeness`. The crud.py version also builds a detailed levels list that search.py does not.
- Fix: Centralize into a service function that takes a db session and DNO, returns structured completeness data.

**[MEDIUM] F-018: Admin check pattern repeated inline across data endpoints**
- File: `/home/kyle/CodingProjects/dno-crawler/backend/app/api/routes/dnos/data.py`, lines 162-166, 215-219, 253-258, 306-310
- `if not current_user.is_admin: raise HTTPException(403, ...)` is repeated in 4 endpoints. The `require_admin` dependency exists in `auth.py` but is not used here.
- Fix: Replace `get_current_user` with `require_admin` dependency for admin-only endpoints, consistent with `admin.py`.

**[MEDIUM] F-019: Verification status lookup pattern duplicated across admin endpoints**
- File: `/home/kyle/CodingProjects/dno-crawler/backend/app/api/routes/admin.py`
- The pattern of querying `NetzentgelteModel.dno_id, year, verification_status` and `HLZFModel` equivalents, then building a `status_lookup` dict, appears 3 times (lines 287-309, 444-457, 623-636).
- Fix: Extract a `build_verification_status_lookup(db)` helper.

### 3.2 Refactoring Opportunities

**[MEDIUM] F-020: `NetzentgelteModel` and `HLZFModel` share 12 identical columns**
- File: `/home/kyle/CodingProjects/dno-crawler/backend/app/db/models.py`, lines 381-478
- Both models have identical `extraction_source`, `extraction_model`, `extraction_source_format`, `last_edited_by`, `last_edited_at`, `verification_status`, `verified_by`, `verified_at`, `verification_notes`, `flagged_by`, `flagged_at`, `flag_reason` columns.
- Fix: Create a `VerificationMixin` and `ExtractionSourceMixin` to reduce duplication. The existing `TimestampMixin` pattern demonstrates this approach is already used.

**[MEDIUM] F-021: `ocr_pdf` method in `AIGateway` bypasses the provider abstraction**
- File: `/home/kyle/CodingProjects/dno-crawler/backend/app/services/ai/gateway.py`, lines 262-352
- While `extract` and `extract_text` use the provider abstraction (`provider.extract_text/extract_vision`), `ocr_pdf` creates a raw OpenRouter client directly (line 290-311), breaking the gateway pattern.
- Fix: Add an `extract_plain_text` or `ocr` method to `BaseProvider` and use the provider abstraction consistently.

**[LOW] F-022: `get_dno_details` uses `getattr(dno, "crawlable", True)` defensively 5 times**
- File: `/home/kyle/CodingProjects/dno-crawler/backend/app/api/routes/dnos/crud.py`, lines 893-899
- The `crawlable` column exists on `DNOModel` and always has a value (`default=True`). The `getattr` fallback is unnecessary defensive coding.
- Fix: Access `dno.crawlable` directly.

---

## 4. Documentation

### 4.1 Intent-Based Documentation

**[LOW] F-023: Comment on line 326 in `crud.py` describes dead code path**
- File: `/home/kyle/CodingProjects/dno-crawler/backend/app/api/routes/dnos/crud.py`, line 326-327
- Comment says "Note: fetch_robots_txt in crud.py is using the old import..." then immediately imports the correct function. The old import on line 323 (`robots_task = fetch_robots_txt(...)`) is created but never awaited, creating a dangling coroutine.
- Fix: Remove the dead code and the stale comment.

**[LOW] F-024: `pdf_extractor.py` has docstrings that describe what, not why**
- File: `/home/kyle/CodingProjects/dno-crawler/backend/app/services/extraction/pdf_extractor.py`
- Most docstrings describe the obvious ("Parse Netzentgelte data from raw text"). The complex regex patterns and fallback logic lack explanatory comments about why specific patterns are needed.
- Fix: Add comments explaining which DNO PDF formats require each pattern (e.g., "Pattern 2 handles Stadtwerke Ulm format where units are embedded inline").

### 4.2 Strategic Comments

**[MEDIUM] F-025: Magic numbers in search similarity thresholds lack rationale**
- File: `/home/kyle/CodingProjects/dno-crawler/backend/app/api/routes/dnos/crud.py`, lines 478-483
- Thresholds (0.08, 0.12, 0.2) are tuned values without explanation of how they were derived or what edge cases they address.
- Fix: Add a comment explaining the tuning rationale (e.g., "0.08 for short queries because trigram similarity drops below 0.1 for 3-char terms like 'Ulm'").

---

## Summary Table

| ID | Principle | Severity | File | Description |
|----|-----------|----------|------|-------------|
| F-001 | KISS | HIGH | `api/main.py` | Inline middleware class definition |
| F-002 | KISS | LOW | `dnos/crud.py` | `locals()` introspection + dangling coroutine |
| F-003 | KISS | LOW | `pdf_extractor.py` | Hardcoded PDF URLs |
| F-004 | YAGNI | MEDIUM | `core/config.py` | Unnecessary `AuthSettings` wrapper |
| F-005 | YAGNI | LOW | `core/models.py` | Dead `AIProvider` enum |
| F-006 | YAGNI | LOW | `core/constants.py` | Unused `get_available_years()` |
| F-007 | SRP | HIGH | `admin.py` | 210-line bulk extract handler |
| F-008 | SRP | HIGH | `dnos/crud.py` | 300-line list endpoint |
| F-009 | SRP | MEDIUM | `dnos/crud.py` | Inline serialization of 3 source models |
| F-010 | SRP | MEDIUM | `search.py` | Utility function in route module |
| F-011 | SoC | HIGH | `dnos/crud.py` | HTTP calls in route handler |
| F-012 | SoC | MEDIUM | `admin.py` | Duplicated file scanning logic |
| F-013 | OCP | MEDIUM | `verification.py` | Copy-paste verification endpoints |
| F-014 | DRY | HIGH | `lib/api.ts` vs `types/` | Resolved in MVP: duplicated frontend types removed; consumers import from `@/types` |
| F-015 | DRY | HIGH | `constants.py` vs `models.py` | Parallel enum and Literal definitions |
| F-016 | DRY | HIGH | `search.py` + `crud.py` | Resolved in MVP: enrichment extracted into `enrich_dno_from_web()` and reused |
| F-017 | DRY | MEDIUM | `crud.py` vs `search.py` | Duplicated completeness computation |
| F-018 | DRY | MEDIUM | `data.py` | Resolved in MVP: endpoints use `Depends(require_admin)` |
| F-019 | DRY | MEDIUM | `admin.py` | Status lookup built 3 times |
| F-020 | Refactor | MEDIUM | `db/models.py` | 12 identical columns across 2 models |
| F-021 | Refactor | MEDIUM | `ai/gateway.py` | `ocr_pdf` bypasses provider abstraction |
| F-022 | Refactor | LOW | `dnos/crud.py` | Unnecessary defensive `getattr` |
| F-023 | Docs | LOW | `dnos/crud.py` | Dead code with stale comment |
| F-024 | Docs | LOW | `pdf_extractor.py` | Docstrings describe what, not why |
| F-025 | Docs | MEDIUM | `dnos/crud.py` | Magic numbers without rationale |

### Severity Distribution
- **HIGH**: 7 findings (F-001, F-007, F-008, F-011, F-014, F-015, F-016)
- **MEDIUM**: 12 findings (F-004, F-009, F-010, F-012, F-013, F-017, F-018, F-019, F-020, F-021, F-025)
- **LOW**: 6 findings (F-002, F-003, F-005, F-006, F-022, F-023, F-024)

### Priority Recommendations

This audit is a point-in-time snapshot. Findings F-014, F-016, and F-018 were addressed during MVP implementation.

1. **Immediate** (HIGH impact, relatively contained fix): F-015 (consolidate enum/Literal duplication)
2. **Next sprint**: F-007 and F-008 (extract service layers from oversized handlers), F-013 (generic verification)
3. **Ongoing**: F-020 (model mixins), F-009/F-017 (shared serialization and completeness), documentation improvements
