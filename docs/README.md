# Documentation

> Documentation note: The executable codebase is authoritative. Documentation provides intent, constraints, and operational guidance.

This directory contains all project documentation for the DNO Crawler.

## Documentation Contract

- The codebase is the source of truth. Docs explain intent and constraints, but cannot supersede current code behavior.
- Keep docs stable, dense, and conceptual. Avoid volatile file-level implementation references unless operationally required.
- When a design decision intentionally violates a core engineering principle, document why.

Core engineering principles used in this repository:

1. KISS (Keep It Simple, Stupid)
2. DRY (Don't Repeat Yourself)
3. YAGNI (You Aren't Gonna Need It)
4. SOLID
5. Separation of Concerns (SoC)
6. Avoid Premature Optimization
7. Law of Demeter

## Structure

### Root docs (human-facing project documentation)

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture, data flow diagrams, database schema, API categories, frontend interaction model |

### `conventions/` (project-agnostic rules, always loaded by AI agents)

| Document | Description |
|----------|-------------|
| [FILE_NAMING.md](conventions/FILE_NAMING.md) | File, directory, and variable naming rules for frontend and backend |
| [LOGGING.md](conventions/LOGGING.md) | Wide Events pattern, log levels, field naming, best practices |
| [CODING.md](conventions/CODING.md) | Python and TypeScript style rules, validation, error handling |

### `knowledge/` (topic-specific operational knowledge, loaded on-demand by AI agents)

| Document | Description |
|----------|-------------|
| [SEEDING.md](knowledge/SEEDING.md) | Seed data pipeline: scripts, data files, stages, regeneration, runtime seeding |
| [FRONTEND_PATTERNS.md](knowledge/FRONTEND_PATTERNS.md) | TanStack Query v5 key factory, react-router-dom v7 routes, import patterns |
| [LOGGING_DOMAIN.md](knowledge/LOGGING_DOMAIN.md) | DNO Crawler domain fields, wide event examples, tail sampling |

Knowledge docs should prioritize reusable patterns and operational behavior over direct file listings.

## Quick Links

| Resource | Location |
|----------|----------|
| Main README | [../README.md](../README.md) |
| AI Agent Protocol | [../AGENTS.md](../AGENTS.md) |
| License | [../LICENSE](../LICENSE) |
