# Documentation

This directory contains all project documentation for the DNO Crawler.

## Structure

### Root docs (human-facing project documentation)

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture, data flow diagrams, database schema, API reference, frontend routes |
| [OBSERVABILITY_STACK.md](OBSERVABILITY_STACK.md) | OTel Collector, Loki, Prometheus, Grafana setup (for infra repo) |

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

## Quick Links

| Resource | Location |
|----------|----------|
| Main README | [../README.md](../README.md) |
| AI Agent Protocol | [../AGENTS.md](../AGENTS.md) |
| License | [../LICENSE](../LICENSE) |
