# Frontend Patterns

> Documentation note: The frontend codebase is authoritative. This file captures durable patterns and decision rules.

Project-specific frontend conventions for the DNO Crawler React application.

The codebase is the source of truth for exact component and route definitions. This document focuses on stable patterns and decision rules.

## TanStack Query v5 Key Factory

Use a centralized query key factory with hierarchical key segments per domain.

Guidelines:
- Define one root namespace per domain (for example: DNOs, jobs, admin).
- Keep list/detail keys structurally distinct.
- Keep filter objects in keys serializable and stable.
- Invalidate at the highest safe namespace to avoid stale sibling caches.

## Usage in Hooks

Hooks should use shared query keys and keep query function logic thin.

Guidelines:
- Keep API adapters in runtime client modules.
- Keep hooks focused on state orchestration, not transformation-heavy logic.
- Co-locate invalidation logic with mutation hooks where practical.

## react-router-dom v7 Routes

Use code-based routing with a single authoritative router configuration.

Guidelines:
- Keep route definitions centralized.
- Keep URL path segments kebab-case.
- Keep route parameters camelCase in application code.
- Avoid scattering route constants across unrelated feature modules.

## URL Parameter Naming

- URL paths: kebab-case
- Params in code: camelCase

## Import Patterns

Import guidelines:
- Components and types use PascalCase symbols.
- Hook and utility files use kebab-case filenames.
- Prefer path aliases over deep relative imports.
- Keep domain types sourced from a single `types` boundary.

## Shared Public Search UI

Public-facing search flows should be composed from shared primitives rather than duplicated page-specific implementations.

When adding behavior (validation rules, filters, rendering states), apply it once in the shared primitive and keep page-level wrappers minimal.

## Type Source of Truth

For domain types (`DNO`, `Netzentgelte`, `HLZF`, `Job`, search response types), import from `@/types`.
Keep `@/lib/api` focused on runtime client functions (`api`, `apiClient`) and compatibility exports only.

## Abbreviations

| Abbreviation | Full Form | Usage |
|--------------|-----------|-------|
| `DNO` | Distribution Network Operator | Uppercase in names: `DNODetailPage.tsx` |
| `HLZF` | Hochlastzeitfenster | Uppercase: `HLZFTable.tsx` |
| `API` | Application Programming Interface | Uppercase in constants, lowercase in files: `api.ts` |
| `UI` | User Interface | Lowercase in directory names: `ui/` |
