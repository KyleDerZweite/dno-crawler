# Codebase Refactor & Cleanup Tasks

> **Started:** 2026-01-08
> **Last Updated:** 2026-01-08 17:30

## Overview

This document tracks the progress of a deep codebase refactor to improve maintainability, reduce duplication, and organize code into logical modules.

---

## Progress Summary

| Phase | Description | Status | Progress |
|-------|-------------|--------|----------|
| Phase 1 | Frontend Component Decomposition | ✅ Complete | 18/18 |
| Phase 2 | Backend Route Decomposition | ⏳ Pending | 0/5 |
| Phase 3 | Shared Types & Constants | ⏳ Pending | 0/4 |
| Phase 4 | Backend Service Layer Cleanup | ⏳ Pending | 0/4 |
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

## Phase 2: Backend Route Decomposition

**Goal:** Split `dnos.py` (1,819 lines, 64KB) into domain-focused modules.

### Tasks

- [ ] **Task 2.1:** Create `backend/app/api/routes/dnos/` directory structure
- [ ] **Task 2.2:** Extract Pydantic schemas to `schemas.py`
- [ ] **Task 2.3:** Extract CRUD endpoints to `crud.py`
- [ ] **Task 2.4:** Extract crawl/job endpoints to `crawl.py`
- [ ] **Task 2.5:** Extract data endpoints (Netzentgelte/HLZF) to `data.py`

---

## Phase 3: Shared Types & Constants

**Goal:** Create single sources of truth for types and constants.

### Tasks

- [ ] **Task 3.1:** Create `frontend/src/types/` directory with domain-specific type files
- [ ] **Task 3.2:** Create `frontend/src/constants/` for shared constants
- [ ] **Task 3.3:** Split `frontend/src/lib/api.ts` into domain modules
- [ ] **Task 3.4:** Create `backend/app/core/constants.py` for shared backend constants

---

## Phase 4: Backend Service Layer Cleanup

**Goal:** Reduce duplication and improve organization in service layer.

### Tasks

- [ ] **Task 4.1:** Extract voltage level normalization to `core/normalization.py`
- [ ] **Task 4.2:** Extract AI prompt templates to `services/extraction/prompts/`
- [ ] **Task 4.3:** Create shared value parsing utilities in `core/parsers.py`
- [ ] **Task 4.4:** Deduplicate HLZF time parsing logic

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

- **17:18** - Created `docs/FILE_NAMING_CONVENTIONS.md` with AI-optimized conventions
- **17:10** - ✅ **Phase 1 Complete!** DNODetailPage.tsx refactored from 2,488 to 981 lines (60% reduction)
- **16:57** - Completed 16/18 Phase 1 tasks (all components extracted, ready for integration)
- **16:52** - Fixed TypeScript errors in tooltip component, started extracting Phase 1 components
- **16:50** - Completed 13/18 Phase 1 tasks (hooks + components created)
- **16:46** - Added Phase 5 for file naming conventions
- **16:38** - Created CLEANUP_TASKS.md, started Phase 1 planning
