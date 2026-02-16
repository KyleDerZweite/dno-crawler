# Coding Conventions

## Python

- **snake_case** for all files, functions, variables, and modules.
- **Type hints** on all function signatures (arguments and return types).
- **async/await** for all I/O-bound operations (database, HTTP, file I/O).
- **Pydantic** for all input validation and serialization.
- **structlog** with the Wide Events pattern for logging (see `LOGGING.md`).

## TypeScript

- **PascalCase** for React components and type/interface names.
- **kebab-case** for hooks (`use-{name}.ts`) and utility files.
- **Path alias**: `@/*` maps to `src/*`.
- **Zod** for all frontend input validation and API response parsing.

## General

- Apply the **KISS principle**. Prefer modular, single-responsibility functions.
- **Validate at boundaries**: Zod on the frontend, Pydantic on the backend.
- **Handle errors gracefully**: structured error responses, no silent swallowing.
- Do not hard-code secrets or environment-specific values.
