# Coding Conventions

> Documentation note: The codebase is authoritative. These conventions are default guidance and require documented rationale when intentionally deviated.

The codebase is the final source of truth. This document defines default engineering guidance and decision heuristics.

## Engineering Principles (Default)

Use these as default decision criteria across frontend, backend, and infrastructure work:

1. **KISS (Keep It Simple, Stupid)**
2. **DRY (Don't Repeat Yourself)**
3. **YAGNI (You Aren't Gonna Need It)**
4. **SOLID**
5. **Separation of Concerns (SoC)**
6. **Avoid Premature Optimization**
7. **Law of Demeter**

These principles are guidelines, not rigid constraints. If one is intentionally violated, record the rationale in the related PR/task context and capture durable operational implications in the appropriate `docs/knowledge/` topic.

## Python

- **snake_case** for all files, functions, variables, and modules.
- **Type hints** on all function signatures (arguments and return types).
- **async/await** for all I/O-bound operations (database, HTTP, file I/O).
- **Pydantic** for all input validation and serialization.
- **structlog** with the Wide Events pattern for logging.

## TypeScript

- **PascalCase** for React components and type/interface names.
- **kebab-case** for hooks (`use-{name}.ts`) and utility files.
- **Path alias**: `@/*` maps to `src/*`.
- **Zod** for all frontend input validation and API response parsing.

## General

- Prefer cohesive, single-responsibility modules and functions.
- Keep abstractions local until clear reuse is proven.
- Optimize for clarity and correctness before performance tuning.
- Minimize coupling across modules and avoid deep object graph traversal.
- **Validate at boundaries**: Zod on the frontend, Pydantic on the backend.
- **Handle errors gracefully**: structured error responses, no silent swallowing.
- Do not hard-code secrets or environment-specific values.
