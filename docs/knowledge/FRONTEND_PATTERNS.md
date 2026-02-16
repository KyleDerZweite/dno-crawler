# Frontend Patterns

Project-specific frontend conventions for the DNO Crawler React application.

## TanStack Query v5 Key Factory

```typescript
// lib/query-keys.ts
export const queryKeys = {
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
  jobs: {
    all: ['jobs'] as const,
    lists: () => [...queryKeys.jobs.all, 'list'] as const,
    list: (status?: string) => [...queryKeys.jobs.lists(), { status }] as const,
    detail: (id: string) => [...queryKeys.jobs.all, 'detail', id] as const,
  },
  admin: {
    all: ['admin'] as const,
    dashboard: () => [...queryKeys.admin.all, 'dashboard'] as const,
    flagged: () => [...queryKeys.admin.all, 'flagged'] as const,
    cachedFiles: () => [...queryKeys.admin.all, 'cached-files'] as const,
    bulkExtractStatus: () => [...queryKeys.admin.all, 'bulk-extract-status'] as const,
  },
} as const;
```

## Usage in Hooks

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

## react-router-dom v7 Routes

Code-based routing (NOT file-based). Routes defined in `App.tsx`.

```typescript
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

## URL Parameter Naming

```typescript
// kebab-case for URL paths
'/dno-details/:id'     // Good
'/dnoDetails/:id'      // Avoid

// camelCase for route params in code
const { id } = useParams<{ id: string }>();
```

## Import Patterns

```typescript
// Components: PascalCase import
import { CrawlDialog } from "@/features/dno-detail/components/CrawlDialog";

// Hooks: camelCase function from kebab-case file
import { useAuth } from "@/lib/use-auth";

// Utilities: camelCase function from kebab-case file
import { formatCurrency, isValidValue } from "@/utils/data-utils";

// Types: PascalCase types from .types file
import type { DNO, Job } from "@/types/api.types";
```

## Abbreviations

| Abbreviation | Full Form | Usage |
|--------------|-----------|-------|
| `DNO` | Distribution Network Operator | Uppercase in names: `DNODetailPage.tsx` |
| `HLZF` | Hochlastzeitfenster | Uppercase: `HLZFTable.tsx` |
| `API` | Application Programming Interface | Uppercase in constants, lowercase in files: `api.ts` |
| `UI` | User Interface | Lowercase in directory names: `ui/` |
