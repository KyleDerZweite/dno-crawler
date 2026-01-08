# File Naming Conventions

> **Project:** dno-crawler  
> **Version:** 1.1  
> **Last Updated:** 2026-01-08  
> **Stack:** React + react-router-dom + Tanstack Query

---

## Quick Reference (AI-Optimized)

```yaml
# NAMING RULES - Use this for file creation/renaming
frontend:
  components: "PascalCase.tsx"      # UserProfile.tsx, DataFilters.tsx
  hooks: "use-{name}.ts"            # use-auth.ts, use-toast.ts  
  utilities: "kebab-case.ts"        # data-utils.ts, format-helpers.ts
  pages: "PascalCase.tsx"           # DashboardPage.tsx, SettingsPage.tsx
  types: "{name}.types.ts"          # dno.types.ts, job.types.ts
  constants: "kebab-case.ts"        # voltage-levels.ts, api-endpoints.ts
  styles: "kebab-case.css"          # index.css, theme.css
  query-keys: "query-keys.ts"       # centralized query key factory
  api: "api.ts"                     # centralized API client

backend:
  modules: "snake_case.py"          # crawl_job.py, data_utils.py
  tests: "test_{module}.py"         # test_dnos.py, test_auth.py
  
shared:
  config: "kebab-case.{ext}"        # docker-compose.yml, tsconfig.json
  docs: "UPPER_CASE.md"             # README.md, CHANGELOG.md
```

---

## Detailed Conventions

### Frontend (TypeScript/React)

| Category | Convention | Pattern | Examples |
|----------|------------|---------|----------|
| **React Components** | PascalCase | `{Name}.tsx` | `CrawlDialog.tsx`, `DNOHeader.tsx`, `VerificationBadge.tsx` |
| **Custom Hooks** | kebab-case with `use-` prefix | `use-{name}.ts` | `use-auth.ts`, `use-toast.ts`, `use-error-toast.ts` |
| **Utility Functions** | kebab-case | `{name}.ts` or `{name}-utils.ts` | `data-utils.ts`, `format-helpers.ts` |
| **Pages** | PascalCase with `Page` suffix | `{Name}Page.tsx` | `DashboardPage.tsx`, `DNODetailPage.tsx` |
| **Type Definitions** | kebab-case with `.types` suffix | `{name}.types.ts` | `dno.types.ts`, `api.types.ts` |
| **Constants** | kebab-case | `{name}.ts` | `voltage-levels.ts`, `error-codes.ts` |
| **Index/Barrel Files** | lowercase | `index.ts` | `index.ts` |
| **Config Files** | kebab-case | `{name}-config.ts` | `auth-config.ts`, `api-config.ts` |
| **CSS/Styles** | kebab-case | `{name}.css` | `index.css`, `globals.css` |

### Tanstack Query Conventions

This project uses **Tanstack Query v5** for data fetching.

| Category | Convention | Pattern | Examples |
|----------|------------|---------|----------|
| **Query Hooks** | kebab-case with `use-` prefix | `use-{resource}.ts` | `use-dnos.ts`, `use-jobs.ts` |
| **Query Keys** | Centralized factory | `query-keys.ts` | `queryKeys.dnos.detail(id)` |
| **API Functions** | Centralized client | `api.ts` | `api.dnos.get(id)` |

#### Query Key Factory Pattern (Recommended)

```typescript
// lib/query-keys.ts
export const queryKeys = {
  // DNO-related queries
  dnos: {
    all: ['dnos'] as const,
    lists: () => [...queryKeys.dnos.all, 'list'] as const,
    list: (filters: { page?: number; search?: string }) => 
      [...queryKeys.dnos.lists(), filters] as const,
    details: () => [...queryKeys.dnos.all, 'detail'] as const,
    detail: (id: string) => [...queryKeys.dnos.details(), id] as const,
    data: (id: string) => ['dno-data', id] as const,
    jobs: (id: string) => ['dno-jobs', id] as const,
    files: (id: string) => ['dno-files', id] as const,
  },
  
  // Job-related queries
  jobs: {
    all: ['jobs'] as const,
    lists: () => [...queryKeys.jobs.all, 'list'] as const,
    list: (status?: string) => [...queryKeys.jobs.lists(), { status }] as const,
    detail: (id: string) => [...queryKeys.jobs.all, 'detail', id] as const,
  },
  
  // Admin-related queries
  admin: {
    all: ['admin'] as const,
    dashboard: () => [...queryKeys.admin.all, 'dashboard'] as const,
    flagged: () => [...queryKeys.admin.all, 'flagged'] as const,
    cachedFiles: () => [...queryKeys.admin.all, 'cached-files'] as const,
    bulkExtractStatus: () => [...queryKeys.admin.all, 'bulk-extract-status'] as const,
  },
} as const;
```

#### Usage in Hooks

```typescript
// hooks/use-dno.ts
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';

export function useDNO(id: string) {
  return useQuery({
    queryKey: queryKeys.dnos.detail(id),
    queryFn: () => api.dnos.get(id),
  });
}

// Invalidation example
queryClient.invalidateQueries({ queryKey: queryKeys.dnos.all });
```

### react-router-dom Conventions

This project uses **react-router-dom v7** (code-based routing, NOT file-based).

| Category | Convention | Pattern | Examples |
|----------|------------|---------|----------|
| **Page Components** | PascalCase with `Page` suffix | `{Name}Page.tsx` | `DashboardPage.tsx`, `DNODetailPage.tsx` |
| **Route Config** | Defined in router file | `router.tsx` or inline in `App.tsx` | N/A |
| **Layout Components** | PascalCase with `Layout` suffix | `{Name}Layout.tsx` | `Layout.tsx`, `AdminLayout.tsx` |
| **Route Guards** | PascalCase component | `ProtectedRoute.tsx` | `ProtectedRoute.tsx` |

#### Route Structure Example

```typescript
// App.tsx or routes.tsx
import { createBrowserRouter, RouterProvider } from 'react-router-dom';

const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'dnos', element: <DNOsPage /> },
      { path: 'dnos/:id', element: <DNODetailPage /> },
      { path: 'jobs', element: <JobsPage /> },
      { path: 'jobs/:id', element: <JobDetailsPage /> },
    ],
  },
]);
```

#### URL Parameter Naming

```typescript
// Use kebab-case for URL paths
'/dno-details/:id'     // ✓ Good
'/dnoDetails/:id'      // ✗ Avoid

// Use camelCase for route params in code
const { id } = useParams<{ id: string }>();
const { dnoId } = useParams<{ dnoId: string }>();
```

### Backend (Python)

| Category | Convention | Pattern | Examples |
|----------|------------|---------|----------|
| **Modules** | snake_case | `{name}.py` | `crawl_job.py`, `rate_limiter.py` |
| **Route Files** | snake_case (noun, plural) | `{resource}.py` | `dnos.py`, `jobs.py`, `users.py` |
| **Service Files** | snake_case with `_service` suffix | `{name}_service.py` | `extraction_service.py` |
| **Model Files** | snake_case | `models.py` or `{name}_models.py` | `models.py`, `source_models.py` |
| **Test Files** | snake_case with `test_` prefix | `test_{module}.py` | `test_dnos.py`, `test_auth.py` |
| **Config Files** | snake_case | `config.py` | `config.py`, `database.py` |
| **Init Files** | fixed | `__init__.py` | `__init__.py` |

### Shared/Root Files

| Category | Convention | Pattern | Examples |
|----------|------------|---------|----------|
| **Documentation** | UPPER_CASE | `{NAME}.md` | `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md` |
| **Config (JSON/YAML)** | kebab-case or lowercase | `{name}.json` | `package.json`, `tsconfig.json` |
| **Docker** | kebab-case | `docker-compose.yml` | `docker-compose.yml`, `Dockerfile` |
| **Environment** | lowercase with dot prefix | `.{name}` or `.{name}.example` | `.env`, `.env.example` |
| **Git Files** | lowercase with dot prefix | `.{name}` | `.gitignore`, `.gitattributes` |


---

## Code Naming Inside Files

### TypeScript/JavaScript

```typescript
// Components: PascalCase
export function CrawlDialog() { ... }
export const UserProfile: React.FC = () => { ... }

// Hooks: camelCase with 'use' prefix  
export function useAuth() { ... }
export function useDataFilters() { ... }

// Functions: camelCase
function handleClick() { ... }
function formatCurrency(value: number) { ... }

// Variables: camelCase
const userName = "John";
const isLoading = true;

// Constants: UPPER_SNAKE_CASE
const MAX_RETRIES = 3;
const API_BASE_URL = "/api/v1";

// Types/Interfaces: PascalCase
interface UserProfile { ... }
type DNOStatus = "active" | "inactive";

// Enums: PascalCase for name, UPPER_SNAKE_CASE for values
enum JobStatus {
  PENDING = "pending",
  RUNNING = "running",
  COMPLETED = "completed",
}
```

### Python

```python
# Classes: PascalCase
class DNOModel:
    pass

class CrawlService:
    pass

# Functions: snake_case
def get_user_by_id(user_id: int):
    pass

def calculate_completeness():
    pass

# Variables: snake_case
user_name = "John"
is_loading = True

# Constants: UPPER_SNAKE_CASE
MAX_RETRIES = 3
API_BASE_URL = "/api/v1"

# Private members: single underscore prefix
def _internal_helper():
    pass

_private_cache = {}
```

---

## Directory Structure Rules

### Frontend Feature Modules

```
features/{feature-name}/           # kebab-case for directory
├── components/                    # lowercase
│   ├── FeatureComponent.tsx       # PascalCase for component files
│   └── index.ts                   # lowercase barrel file
├── hooks/                         # lowercase
│   ├── use-feature-hook.ts        # kebab-case with use- prefix
│   └── index.ts
├── utils/                         # lowercase
│   └── feature-utils.ts           # kebab-case
├── types/                         # lowercase
│   └── feature.types.ts           # kebab-case with .types suffix
└── index.ts                       # main barrel export
```

### Backend Domain Modules

```
app/{domain}/                      # snake_case for directory
├── __init__.py
├── routes.py                      # or {domain}.py for routes
├── models.py                      # domain models
├── schemas.py                     # Pydantic schemas
├── service.py                     # business logic
└── utils.py                       # domain-specific utilities
```

---

## Migration Guidelines

### Files to Rename (Current Project)

```yaml
# Priority: HIGH - Inconsistent hook naming
frontend/src/lib/use-auth.ts:
  current: "use-auth.ts"
  status: CORRECT ✓

frontend/src/hooks/use-toast.ts:
  current: "use-toast.ts"  
  status: CORRECT ✓

frontend/src/hooks/use-error-toast.ts:
  current: "use-error-toast.ts"
  status: CORRECT ✓

# Priority: MEDIUM - Component naming
frontend/src/components/verification-badge.tsx:
  current: "verification-badge.tsx"
  recommended: "VerificationBadge.tsx"
  reason: "Components should use PascalCase"

frontend/src/components/extraction-source-badge.tsx:
  current: "extraction-source-badge.tsx"
  recommended: "ExtractionSourceBadge.tsx"
  reason: "Components should use PascalCase"

frontend/src/lib/auth-callback.tsx:
  current: "auth-callback.tsx"
  recommended: "AuthCallback.tsx"
  reason: "This is a component, should use PascalCase"

frontend/src/lib/auth-provider.tsx:
  current: "auth-provider.tsx"
  recommended: "AuthProvider.tsx"
  reason: "This is a component, should use PascalCase"

frontend/src/lib/protected-route.tsx:
  current: "protected-route.tsx"
  recommended: "ProtectedRoute.tsx"
  reason: "This is a component, should use PascalCase"
```

---

## AI Agent Instructions

When creating or modifying files in this project:

### 1. File Creation Checklist

```
□ Determine file category (component, hook, utility, etc.)
□ Apply correct naming convention from Quick Reference
□ Verify directory location matches project structure
□ Update barrel exports (index.ts) if needed
```

### 2. Decision Tree

```
Is it a React component? (.tsx with JSX)
  └─ YES → PascalCase.tsx (e.g., MyComponent.tsx)
  └─ NO ↓

Is it a React page component? (renders a full page)
  └─ YES → {Name}Page.tsx (e.g., DashboardPage.tsx)
  └─ NO ↓

Is it a Tanstack Query hook wrapper?
  └─ YES → use-{resource}.ts (e.g., use-dnos.ts)
        → Uses queryKeys from lib/query-keys.ts
  └─ NO ↓

Is it a custom hook? (starts with use)
  └─ YES → use-{name}.ts (e.g., use-auth.ts)
  └─ NO ↓

Is it a query key definition?
  └─ YES → Add to lib/query-keys.ts (centralized)
  └─ NO ↓

Is it an API function?
  └─ YES → Add to lib/api.ts (centralized)
  └─ NO ↓

Is it a utility/helper function?
  └─ YES → kebab-case.ts (e.g., data-utils.ts)
  └─ NO ↓

Is it a type definition file?
  └─ YES → {name}.types.ts (e.g., dno.types.ts)
  └─ NO ↓

Is it a Python file?
  └─ YES → snake_case.py (e.g., crawl_job.py)
  └─ NO ↓

Is it a config or root file?
  └─ YES → Follow Shared/Root conventions
```

### 3. Import Statement Patterns

```typescript
// Components - PascalCase import
import { CrawlDialog } from "@/features/dno-detail/components/CrawlDialog";

// Hooks - camelCase function from kebab-case file
import { useAuth } from "@/lib/use-auth";

// Utilities - camelCase function from kebab-case file
import { formatCurrency, isValidValue } from "@/utils/data-utils";

// Types - PascalCase types from .types file
import type { DNO, Job } from "@/types/api.types";
```

---

## Exceptions and Special Cases

### Allowed Exceptions

1. **shadcn/ui Components**: Keep original lowercase naming (e.g., `button.tsx`, `dialog.tsx`) to match the library's conventions and simplify updates.

2. **Generated Files**: Files auto-generated by tools (e.g., `vite-env.d.ts`) should not be renamed.

3. **Package Conventions**: When a library has strong conventions (e.g., Next.js `page.tsx`), follow the library's conventions.

### Abbreviations

| Abbreviation | Full Form | Usage |
|--------------|-----------|-------|
| `DNO` | Distribution Network Operator | Keep uppercase in names: `DNODetailPage.tsx` |
| `HLZF` | Hochlastzeitfenster | Keep uppercase: `HLZFTable.tsx` |
| `API` | Application Programming Interface | Uppercase in constants, lowercase in files: `api.ts` |
| `UI` | User Interface | Lowercase in directory names: `ui/` |

---

## Validation Script

To check naming conventions, run:

```bash
# Check for kebab-case components (should be PascalCase)
find frontend/src -name "*.tsx" | grep -E '/[a-z]+-[a-z]+\.tsx$'

# Check for PascalCase hooks (should be kebab-case)  
find frontend/src -name "use*.ts" | grep -E 'use[A-Z]'

# Check Python files for camelCase (should be snake_case)
find backend -name "*.py" | grep -E '[a-z][A-Z]'
```

---

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-08 | 1.1 | Added Tanstack Query v5 patterns (query key factory), react-router-dom v7 conventions |
| 2026-01-08 | 1.0 | Initial conventions document |
