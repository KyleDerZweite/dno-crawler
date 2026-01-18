# File Naming Conventions

Project: dno-crawler  
Version: 1.2  
Last Updated: 2026-01-17  
Stack: React 19 + react-router-dom 7 + TanStack Query 5

## Quick Reference (AI Optimized)

```yaml
# NAMING RULES for file creation and renaming
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

## Detailed Conventions

### Frontend (TypeScript and React)

| Category | Convention | Pattern | Examples |
|----------|------------|---------|----------|
| React Components | PascalCase | `{Name}.tsx` | `CrawlDialog.tsx`, `DNOHeader.tsx`, `VerificationBadge.tsx` |
| Custom Hooks | kebab case with `use-` prefix | `use-{name}.ts` | `use-auth.ts`, `use-toast.ts`, `use-error-toast.ts` |
| Utility Functions | kebab case | `{name}.ts` or `{name}-utils.ts` | `data-utils.ts`, `format-helpers.ts` |
| Pages | PascalCase with `Page` suffix | `{Name}Page.tsx` | `DashboardPage.tsx`, `DNODetailPage.tsx` |
| Type Definitions | kebab case with `.types` suffix | `{name}.types.ts` | `dno.types.ts`, `api.types.ts` |
| Constants | kebab case | `{name}.ts` | `voltage-levels.ts`, `error-codes.ts` |
| Index and Barrel Files | lowercase | `index.ts` | `index.ts` |
| Config Files | kebab case | `{name}-config.ts` | `auth-config.ts`, `api-config.ts` |
| CSS and Styles | kebab case | `{name}.css` | `index.css`, `globals.css` |

### TanStack Query Conventions

This project uses TanStack Query v5 for data fetching.

| Category | Convention | Pattern | Examples |
|----------|------------|---------|----------|
| Query Hooks | kebab case with `use-` prefix | `use-{resource}.ts` | `use-dnos.ts`, `use-jobs.ts` |
| Query Keys | Centralized factory | `query-keys.ts` | `queryKeys.dnos.detail(id)` |
| API Functions | Centralized client | `api.ts` | `api.dnos.get(id)` |

#### Query Key Factory Pattern (Recommended)

```typescript
// lib/query-keys.ts
export const queryKeys = {
  // DNO related queries
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
  
  // Job related queries
  jobs: {
    all: ['jobs'] as const,
    lists: () => [...queryKeys.jobs.all, 'list'] as const,
    list: (status?: string) => [...queryKeys.jobs.lists(), { status }] as const,
    detail: (id: string) => [...queryKeys.jobs.all, 'detail', id] as const,
  },
  
  // Admin related queries
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

This project uses react-router-dom v7 (code based routing, NOT file based).

| Category | Convention | Pattern | Examples |
|----------|------------|---------|----------|
| Page Components | PascalCase with `Page` suffix | `{Name}Page.tsx` | `DashboardPage.tsx`, `DNODetailPage.tsx` |
| Route Config | Defined in router file | `router.tsx` or inline in `App.tsx` | N/A |
| Layout Components | PascalCase with `Layout` suffix | `{Name}Layout.tsx` | `Layout.tsx`, `AdminLayout.tsx` |
| Route Guards | PascalCase component | `ProtectedRoute.tsx` | `ProtectedRoute.tsx` |

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
// Use kebab case for URL paths
'/dno-details/:id'     // Good
'/dnoDetails/:id'      // Avoid

// Use camelCase for route params in code
const { id } = useParams<{ id: string }>();
const { dnoId } = useParams<{ dnoId: string }>();
```

### Backend (Python)

| Category | Convention | Pattern | Examples |
|----------|------------|---------|----------|
| Modules | snake_case | `{name}.py` | `crawl_job.py`, `rate_limiter.py` |
| Route Files | snake_case | `{resource}.py` or `{domain}.py` | `dnos.py`, `auth.py`, `health.py` |
| Service Files | snake_case | `{name}.py` | `web_crawler.py`, `extraction.py` |
| Model Files | snake_case | `models.py` or `{name}_models.py` | `models.py`, `source_models.py` |
| Test Files | snake_case with `test_` prefix | `test_{module}.py` | `test_dnos.py`, `test_auth.py` |
| Config Files | snake_case | `config.py` | `config.py`, `database.py` |
| Init Files | fixed | `__init__.py` | `__init__.py` |

## Directory Structure Rules

### Frontend Feature Modules

```
features/{feature-name}/           # kebab case for directory
├── components/                    # lowercase
│   ├── FeatureComponent.tsx       # PascalCase for component files
│   └── index.ts                   # lowercase barrel file
├── hooks/                         # lowercase
│   ├── use-feature-hook.ts        # kebab case with use- prefix
│   └── index.ts
├── views/                         # lowercase (for tabbed interfaces)
│   ├── Overview.tsx               # PascalCase for view components
│   ├── DataExplorer.tsx
│   └── index.ts
├── utils/                         # lowercase
│   └── feature-utils.ts           # kebab case
├── types/                         # lowercase
│   └── feature.types.ts           # kebab case with .types suffix
└── index.ts                       # main barrel export
```

### Backend Structure (Layered)

```
app/
├── api/
│   ├── middleware/                # Request processing
│   │   └── wide_events.py
│   └── routes/                    
│       ├── dnos/                  # Resource subdirectory for complex routes
│       │   └── __init__.py
│       ├── admin.py               # Domain route (singular or plural)
│       ├── auth.py
│       └── __init__.py
├── services/                      # Business logic
│   ├── ai/                        # Sub modules for complex domains
│   │   └── extractor.py
│   ├── discovery/
│   │   └── sitemap_parser.py
│   ├── extraction/
│   │   └── pdf_extractor.py
│   └── web_crawler.py             # snake_case (no _service suffix needed)
├── db/
│   ├── models.py                  # Database models
│   ├── source_models.py           # Additional model files
│   └── database.py
├── jobs/
│   ├── steps/                     # Pipeline step modules
│   │   └── step_01_discover.py
│   └── crawl_job.py
└── core/                          # Cross cutting concerns
    ├── config.py
    └── security.py
```

## AI Agent Instructions

When creating or modifying files in this project, follow these guidelines.

### 1. File Creation Checklist

1. Determine file category (component, hook, utility, etc.)
2. Apply correct naming convention from Quick Reference
3. Verify directory location matches project structure
4. Update barrel exports (index.ts) if needed

### 2. Decision Tree

```
Is it a React component? (.tsx with JSX)
  └─ YES → PascalCase.tsx (e.g., MyComponent.tsx)
  └─ NO ↓

Is it a React page component? (renders a full page)
  └─ YES → {Name}Page.tsx (e.g., DashboardPage.tsx)
  └─ NO ↓

Is it a TanStack Query hook wrapper?
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

Is it a utility or helper function?
  └─ YES → kebab-case.ts (e.g., data-utils.ts)
  └─ NO ↓

Is it a type definition file?
  └─ YES → {name}.types.ts (e.g., dno.types.ts)
  └─ NO ↓

Is it a Python file?
  └─ YES → snake_case.py (e.g., crawl_job.py)
  └─ NO ↓

Is it a config or root file?
  └─ YES → Follow Shared and Root conventions
```

### 3. Import Statement Patterns

```typescript
// Components use PascalCase import
import { CrawlDialog } from "@/features/dno-detail/components/CrawlDialog";

// Hooks use camelCase function from kebab case file
import { useAuth } from "@/lib/use-auth";

// Utilities use camelCase function from kebab case file
import { formatCurrency, isValidValue } from "@/utils/data-utils";

// Types use PascalCase types from .types file
import type { DNO, Job } from "@/types/api.types";
```

## Exceptions and Special Cases

### Allowed Exceptions

1. **shadcn/ui Components** Keep original lowercase naming (e.g., `button.tsx`, `dialog.tsx`) to match the library conventions and simplify updates.

2. **Generated Files** Files auto generated by tools (e.g., `vite-env.d.ts`) should not be renamed.

3. **Package Conventions** When a library has strong conventions (e.g., Next.js `page.tsx`), follow the library conventions.

### Abbreviations

| Abbreviation | Full Form | Usage |
|--------------|-----------|-------|
| `DNO` | Distribution Network Operator | Keep uppercase in names such as `DNODetailPage.tsx` |
| `HLZF` | Hochlastzeitfenster | Keep uppercase such as `HLZFTable.tsx` |
| `API` | Application Programming Interface | Uppercase in constants, lowercase in files such as `api.ts` |
| `UI` | User Interface | Lowercase in directory names such as `ui/` |

## Validation Script

To check naming conventions, run the following commands.

```bash
# Check for kebab case components (should be PascalCase)
find frontend/src -name "*.tsx" | grep -E '/[a-z]+-[a-z]+\.tsx$'

# Check for PascalCase hooks (should be kebab case)  
find frontend/src -name "use*.ts" | grep -E 'use[A-Z]'

# Check Python files for camelCase (should be snake_case)
find backend -name "*.py" | grep -E '[a-z][A-Z]'
```

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-17 | 1.2 | Updated to reflect current project structure, added views directory convention, removed problematic symbols |
| 2026-01-08 | 1.1 | Added TanStack Query v5 patterns (query key factory), react-router-dom v7 conventions |
| 2026-01-08 | 1.0 | Initial conventions document |
