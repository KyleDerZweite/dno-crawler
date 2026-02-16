# File Naming Conventions

## Quick Reference

```yaml
frontend:
  components: "PascalCase.tsx"        # UserProfile.tsx, DataFilters.tsx
  hooks: "use-{name}.ts"              # use-auth.ts, use-toast.ts
  utilities: "kebab-case.ts"          # data-utils.ts, format-helpers.ts
  pages: "{Name}Page.tsx"             # DashboardPage.tsx, SettingsPage.tsx
  types: "{name}.types.ts"            # dno.types.ts, job.types.ts
  constants: "kebab-case.ts"          # voltage-levels.ts, api-endpoints.ts
  styles: "kebab-case.css"            # index.css, theme.css
  query-keys: "query-keys.ts"         # centralized query key factory
  api: "api.ts"                       # centralized API client

backend:
  modules: "snake_case.py"            # crawl_job.py, data_utils.py
  tests: "test_{module}.py"           # test_dnos.py, test_auth.py

shared:
  config: "kebab-case.{ext}"          # docker-compose.yml, tsconfig.json
  docs: "UPPER_CASE.md"              # README.md, CHANGELOG.md
```

## Frontend Naming Table

| Category | Convention | Example |
|----------|------------|---------|
| React Components | `PascalCase.tsx` | `CrawlDialog.tsx`, `DNOHeader.tsx` |
| Custom Hooks | `use-{name}.ts` | `use-auth.ts`, `use-error-toast.ts` |
| Utilities | `kebab-case.ts` | `data-utils.ts`, `format-helpers.ts` |
| Pages | `{Name}Page.tsx` | `DashboardPage.tsx`, `DNODetailPage.tsx` |
| Types | `{name}.types.ts` | `dno.types.ts`, `api.types.ts` |
| Index/Barrel | `index.ts` | `index.ts` |
| Config | `{name}-config.ts` | `auth-config.ts` |

## Backend Naming Table

| Category | Convention | Example |
|----------|------------|---------|
| Modules | `snake_case.py` | `crawl_job.py`, `rate_limiter.py` |
| Routes | `snake_case.py` | `dnos.py`, `auth.py` |
| Models | `models.py` or `{name}_models.py` | `source_models.py` |
| Tests | `test_{module}.py` | `test_dnos.py`, `test_auth.py` |

## Feature Module Structure

```
features/{feature-name}/           # kebab-case directory
  components/                      # PascalCase.tsx files
  hooks/                           # use-{name}.ts files
  views/                           # PascalCase.tsx (tabbed interfaces)
  utils/                           # kebab-case.ts files
  types/                           # {name}.types.ts files
  index.ts                         # barrel export
```

## Decision Tree

```
React component (.tsx with JSX)?       -> PascalCase.tsx
Page component (full page)?            -> {Name}Page.tsx
TanStack Query hook?                   -> use-{resource}.ts (uses query-keys.ts)
Custom hook (starts with use)?         -> use-{name}.ts
Query key definition?                  -> add to lib/query-keys.ts
API function?                          -> add to lib/api.ts
Utility/helper?                        -> kebab-case.ts
Type definition?                       -> {name}.types.ts
Python file?                           -> snake_case.py
Config/root file?                      -> follow shared conventions
```

## Exceptions

1. **shadcn/ui**: Keep original lowercase naming (`button.tsx`, `dialog.tsx`).
2. **Generated files**: Do not rename (`vite-env.d.ts`).
3. **Library conventions**: Follow the library when it has strong naming opinions.
