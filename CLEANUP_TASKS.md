# Codebase Refactor & Cleanup Tasks

> **Started:** 2026-01-08
> **Last Updated:** 2026-01-08 22:30

## Overview

This document tracks the progress of a deep codebase refactor to improve maintainability, reduce duplication, and organize code into logical modules.

---

## Progress Summary

| Phase | Description | Status | Progress |
|-------|-------------|--------|----------|
| Phase 1 | Frontend Component Decomposition | ✅ Complete | 18/18 |
| Phase 2 | Backend Route Decomposition | ✅ Complete | 8/8 |
| Phase 3 | Shared Types & Constants | ✅ Complete | 4/4 |
| Phase 4 | Backend Service Layer Cleanup | ✅ Complete | 4/4 |
| Phase 5 | File Naming Conventions | ✅ Complete | 3/3 |

---

## Phase 1: Frontend Component Decomposition

**Goal:** Split `DNODetailPage.tsx` (2,489 lines, 140KB) into modular, reusable components.

### Tasks

#### 1.1 Create Shared Utilities & Hooks
- [x] **Task 1.1.1:** Create `useErrorToast` hook to handle error formatting (eliminates 10+ duplications)
- [x] **Task 1.1.2:** Create `features/dno-detail/utils/data-utils.ts` for shared helpers (`isValidValue`, formatters)
- [x] **Task 1.1.3:** Create `features/dno-detail/hooks/useDNOMutations.ts` - consolidate all mutation logic

#### 1.2 Extract Components
- [x] **Task 1.2.1:** Extract `DNOHeader` component (DNO info card, status, actions)
- [x] **Task 1.2.2:** Extract `CrawlDialog` component (crawl trigger form)
- [x] **Task 1.2.3:** Extract `DataFilters` component (year/voltage level filters)
- [x] **Task 1.2.4:** Extract `NetzentgelteTable` component
- [x] **Task 1.2.5:** Extract `HLZFTable` component
- [x] **Task 1.2.6:** Extract `FilesJobsPanel` component (files + jobs tabs)
- [x] **Task 1.2.7:** Extract `EditRecordDialog` component
- [x] **Task 1.2.8:** Extract `SourceDataAccordion` component (MaStR/VNB/BDEW)
- [x] **Task 1.2.9:** Extract `EditDNODialog` component (admin DNO metadata editing)
- [x] **Task 1.2.10:** Extract `DeleteDNODialog` component (admin DNO deletion)

#### 1.3 Create Custom Hooks
- [x] **Task 1.3.1:** Create `useDNOData` hook (data fetching, polling logic)
- [x] **Task 1.3.2:** Create `useDataFilters` hook (filter state management)
- [x] **Task 1.3.3:** Create `useDataCompleteness` hook (completeness calculation)

#### 1.4 Final Cleanup
- [x] **Task 1.4.1:** Refactor main `DNODetailPage.tsx` to use extracted components
- [x] **Task 1.4.2:** Verify all functionality works correctly (build passes)
- [x] **Task 1.4.3:** Remove any remaining dead code (backup created)

### Completed Tasks (Phase 1)

| Task | Description | File Created |
|------|-------------|--------------|
| 1.1.1 | Error toast hook | `hooks/use-error-toast.ts` |
| 1.1.2 | Data utilities | `features/dno-detail/utils/data-utils.ts` |
| 1.1.3 | Mutations hook | `features/dno-detail/hooks/useDNOMutations.ts` |
| 1.2.2 | Crawl dialog | `features/dno-detail/components/CrawlDialog.tsx` |
| 1.2.3 | Data filters | `features/dno-detail/components/DataFilters.tsx` |
| 1.2.4 | Netzentgelte table | `features/dno-detail/components/NetzentgelteTable.tsx` |
| 1.2.5 | HLZF table | `features/dno-detail/components/HLZFTable.tsx` |
| 1.2.7 | Edit record dialog | `features/dno-detail/components/EditRecordDialog.tsx` |
| 1.2.9 | Edit DNO dialog | `features/dno-detail/components/EditDNODialog.tsx` |
| 1.2.10 | Delete DNO dialog | `features/dno-detail/components/DeleteDNODialog.tsx` |
| 1.3.1 | DNO data hook | `features/dno-detail/hooks/useDNOData.ts` |
| 1.3.2 | Data filters hook | `features/dno-detail/hooks/useDataFilters.ts` |
| 1.3.3 | Completeness hook | `features/dno-detail/hooks/useDataCompleteness.ts` |
| 1.2.6 | Files + Jobs panel | `features/dno-detail/components/FilesJobsPanel.tsx` |
| 1.2.1 | DNO header | `features/dno-detail/components/DNOHeader.tsx` |
| 1.2.8 | Source data accordion | `features/dno-detail/components/SourceDataAccordion.tsx` |
| 1.4.1 | **Final Integration** | `pages/DNODetailPage.tsx` (**2,488 → 981 lines, 60% reduction**) |

---

## Phase 2: Backend Route Decomposition ✅

**Goal:** Split `dnos.py` (1,819 lines, 64KB) into domain-focused modules.

### Strategy
The decomposition fully migrated all endpoints to the new modular structure:
1. Created `dnos/` package with individual modules
2. Original monolithic `dnos.py` deleted (no legacy code)
3. All endpoints migrated to domain-specific modules

### Tasks

- [x] **Task 2.1:** Create `backend/app/api/routes/dnos/` directory structure
- [x] **Task 2.2:** Extract Pydantic schemas to `schemas.py`
- [x] **Task 2.3:** Create `utils.py` with shared helper functions
- [x] **Task 2.4:** Extract CRUD endpoints to `crud.py`
- [x] **Task 2.5:** Extract crawl/job endpoints to `crawl.py`
- [x] **Task 2.6:** Extract data endpoints (Netzentgelte/HLZF) to `data.py`
- [x] **Task 2.7:** Extract file operations to `files.py`
- [x] **Task 2.8:** Extract import/export to `import_export.py`

### Completed Files

| File | Description | Lines |
|------|-------------|-------|
| `dnos/__init__.py` | Main router combining all sub-routers | ~35 |
| `dnos/schemas.py` | Pydantic request/response models | ~140 |
| `dnos/utils.py` | Shared utilities (slugify, etc.) | ~20 |
| `dnos/crud.py` | DNO CRUD operations, VNB search | ~580 |
| `dnos/crawl.py` | Crawl/job trigger and history | ~200 |
| `dnos/data.py` | Netzentgelte/HLZF CRUD | ~290 |
| `dnos/files.py` | File list and upload | ~140 |
| `dnos/import_export.py` | JSON import/export | ~290 |

**Total: ~1,695 lines across 8 files** (vs 1,819 in original monolith)

---

## Phase 3: Shared Types & Constants ✅

**Goal:** Create single sources of truth for types and constants.

### Tasks

- [x] **Task 3.1:** Create `frontend/src/types/` directory with domain-specific type files
- [x] **Task 3.2:** Create `frontend/src/constants/` for shared constants
- [x] **Task 3.3:** Added note to `frontend/src/lib/api.ts` pointing to new types (backward compatible)
- [x] **Task 3.4:** Create `backend/app/core/constants.py` for shared backend constants

### Created Files

**Frontend Types (`frontend/src/types/`):**
- `api.types.ts` - API response types, pagination
- `dno.types.ts` - DNO, VNB, address types
- `data.types.ts` - Netzentgelte, HLZF types
- `job.types.ts` - Job, step, extraction log types
- `search.types.ts` - Public search API types
- `index.ts` - Re-exports all types

**Frontend Constants (`frontend/src/constants/`):**
- `api.ts` - API URL, pagination defaults, years
- `status.ts` - DNO/job/verification status config
- `voltage-levels.ts` - Voltage level constants
- `index.ts` - Re-exports all constants

**Backend:**
- `backend/app/core/constants.py` - Shared backend constants

---

## Phase 4: Backend Service Layer Cleanup ✅

**Goal:** Reduce duplication and improve organization in service layer.

### Tasks

- [x] **Task 4.1:** Voltage level normalization in `core/constants.py` (normalize_voltage_level function)
- [x] **Task 4.2:** Extract AI prompt templates to `services/extraction/prompts/`
- [x] **Task 4.3:** Create shared value parsing utilities in `core/parsers.py`
- [x] **Task 4.4:** HLZF time parsing already consolidated in `html_extractor.py` (no duplication found)

### Created Files

- `backend/app/core/constants.py` - Voltage levels, data types, job config, pagination
- `backend/app/core/parsers.py` - German number parsing, time window normalization
- `backend/app/services/extraction/prompts/__init__.py` - AI extraction prompts

---

## Phase 5: File Naming Conventions

**Goal:** Standardize file naming across the codebase for consistency and clarity.

> 📖 **Full Documentation:** [`docs/FILE_NAMING_CONVENTIONS.md`](./docs/FILE_NAMING_CONVENTIONS.md)

### Recommended Conventions (Summary)

| File Type | Convention | Example |
|-----------|------------|---------|
| React Components | **PascalCase** | `CrawlDialog.tsx`, `DNOHeader.tsx` |
| Custom Hooks | **kebab-case** with `use-` prefix | `use-auth.ts`, `use-toast.ts` |
| Utilities/Helpers | **kebab-case** | `data-utils.ts`, `format-helpers.ts` |
| Types | **kebab-case** with `.types` suffix | `dno.types.ts`, `api.types.ts` |
| Python modules | **snake_case** | `crawl_job.py`, `rate_limiter.py` |
| Config files | **kebab-case** | `auth-config.ts`, `tsconfig.json` |

### Files Renamed ✅

| Old Name | New Name | Status |
|----------|----------|--------|
| `verification-badge.tsx` | `VerificationBadge.tsx` | ✅ Done |
| `extraction-source-badge.tsx` | `ExtractionSourceBadge.tsx` | ✅ Done |
| `auth-callback.tsx` | `AuthCallback.tsx` | ✅ Done |
| `auth-provider.tsx` | `AuthProvider.tsx` | ✅ Done |
| `protected-route.tsx` | `ProtectedRoute.tsx` | ✅ Done |

### Tasks

- [x] **Task 5.1:** Create `docs/FILE_NAMING_CONVENTIONS.md` documentation
- [x] **Task 5.2:** Rename component files to PascalCase
- [x] **Task 5.3:** Update all imports after renaming

---

## Bug Fixes (Discovered During Refactoring)

These issues were discovered during the refactoring process and should be tracked for resolution.

### TypeScript Errors

| File | Issue | Status |
|------|-------|--------|
| `components/ui/tooltip.tsx` | Missing `delayDuration` prop on TooltipProvider, missing `side` prop on TooltipContent | ✅ Fixed |
---

## Changelog

### 2026-01-08

- **22:30** - ✅ **Phase 4 Complete!** Backend service layer cleanup (constants, parsers, prompts)
- **22:25** - ✅ **Phase 3 Complete!** Created frontend types/ and constants/ directories
- **21:59** - ✅ **Phase 2 Complete!** Decomposed dnos.py (1,819 lines) into 8 modular files
- **21:50** - Started Phase 2: Created `dnos/` package with schemas.py, utils.py
- **17:30** - ✅ **Phase 5 Complete!** Renamed 5 component files to PascalCase, updated all imports
- **17:18** - Created `docs/FILE_NAMING_CONVENTIONS.md` with AI-optimized conventions
- **17:10** - ✅ **Phase 1 Complete!** DNODetailPage.tsx refactored from 2,488 to 981 lines (60% reduction)
- **16:57** - Completed 16/18 Phase 1 tasks (all components extracted, ready for integration)
- **16:52** - Fixed TypeScript errors in tooltip component, started extracting Phase 1 components
- **16:50** - Completed 13/18 Phase 1 tasks (hooks + components created)
- **16:46** - Added Phase 5 for file naming conventions
- **16:38** - Created CLEANUP_TASKS.md, started Phase 1 planning
