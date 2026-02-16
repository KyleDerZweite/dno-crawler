# AI Agent Operational Protocol

This is the single source of truth for all AI coding agents working in this repository. Tool-specific files (e.g. `CLAUDE.md`) should reference this file rather than duplicate its content.

## 1. Context and Knowledge Retrieval

**DO NOT HALLUCINATE.** You are strictly bound by the Source of Truth documentation. Before generating code, planning features, or answering questions, you must ingest the context from the following files.

| Document | Purpose |
|----------|---------|
| `docs/ARCHITECTURE.md` | System design, data flow diagrams, database schema, API reference, and frontend routes |
| `README.md` | Installation guide and available development commands |

## 2. Conventions (`docs/conventions/`)

These files are **always loaded** at the start of every session. They contain short, dense, project-agnostic rules.

| File | Content |
|------|---------|
| `docs/conventions/FILE_NAMING.md` | File, directory, and variable naming rules for frontend and backend |
| `docs/conventions/LOGGING.md` | Wide Events pattern, log levels, field naming, best practices |
| `docs/conventions/CODING.md` | Python and TypeScript style rules, validation, error handling |

Apply project-specific overrides from section 7 of this file on top of these base rules.

## 3. Knowledge Base (`docs/knowledge/`)

The `docs/knowledge/` directory contains topic-specific reference files written for AI agents. These files capture operational knowledge (pipelines, processes, non-obvious context) that does not belong in user-facing `docs/`.

**Reading**: Before working on a task, check if a relevant `docs/knowledge/` file exists. If it does, read it first. These files contain verified context that prevents repeated discovery of the same information.

**Writing**: When you complete a task that involved non-trivial discovery (multi-step processes, workarounds, data flow understanding, integration details), check if a matching `docs/knowledge/` file exists:
- If yes, update it with the new information.
- If no, create a new file for the topic.

**Rules**:
- One file per topic. Use `UPPER_SNAKE_CASE.md` naming (e.g., `SEEDING.md`, `DEPLOYMENT.md`).
- Write for a future AI agent that has zero prior context. Include exact commands, file paths, and expected outputs.
- Keep content factual and verified. Do not write speculative or aspirational content.
- Update files when the underlying code or process changes. Stale knowledge is worse than no knowledge.
- Do not duplicate content from `docs/`. Reference `docs/` files where appropriate instead of copying.

**Current files**:

| File | Topic |
|------|-------|
| `docs/knowledge/SEEDING.md` | Seed data pipeline: scripts, data files, stages, regeneration, runtime seeding |
| `docs/knowledge/FRONTEND_PATTERNS.md` | TanStack Query v5 key factory, react-router-dom v7 routes, import patterns, abbreviations |
| `docs/knowledge/LOGGING_DOMAIN.md` | DNO Crawler domain fields, complete wide event example, tail sampling, file references |

## 4. Project Overview

DNO Crawler is a full-stack app for automated extraction of regulatory data (Netzentgelte and HLZF) from German Distribution Network Operators. It resolves addresses to grid operators via the VNB Digital GraphQL API, then crawls operator websites to discover, download, and parse pricing documents.

## 5. Commands

### Backend (run from `backend/`)
```bash
uv sync                                    # Install dependencies (uses uv, not pip)
uvicorn app.api.main:app --reload          # Dev server on :8000
pytest                                     # Run tests (asyncio_mode=auto)
pytest tests/path/test_file.py::test_name  # Run single test
ruff check .                               # Lint
ruff check . --fix                         # Lint with auto-fix
ruff format .                              # Format (or: black .)
mypy app                                   # Type check (strict mode)
alembic revision --autogenerate -m "msg"   # Generate migration
alembic upgrade head                       # Apply migrations
python scripts/import_mastr_stats.py --file ../marktstammdatenregister/dno_stats.json --dry-run  # Validate MaStR stats import
python scripts/import_mastr_stats.py --file ../marktstammdatenregister/dno_stats.json            # Import MaStR stats
```

### MaStR Offline Pipeline (run from repo root)
```bash
python marktstammdatenregister/transform_mastr.py --data-dir ./marktstammdatenregister/data --output ./marktstammdatenregister/dno_stats.json
python marktstammdatenregister/import_mastr_stats.py --file ./marktstammdatenregister/dno_stats.json --dry-run
```

### Frontend (run from `frontend/`)
```bash
npm install        # Install dependencies
npm run dev        # Vite dev server on :5173
npm run build      # tsc -b && vite build
npm run lint       # ESLint
npm test           # Run Vitest tests
npm run test:watch # Run tests in watch mode
```

### Podman
```bash
podman-compose up -d --build    # Start all 7 services
```

## 6. Architecture

### Backend (Python/FastAPI)
```
backend/app/
  api/
    main.py              # App factory: create_app(), lifespan, middleware
    routes/              # HTTP endpoints
      dnos/              # Decomposed: schemas.py, crud.py, crawl.py, data.py, files.py, import_export.py
      health.py, auth.py, search.py, jobs.py, verification.py, ai.py, admin.py
    middleware/
      wide_events.py     # Canonical log line (one structured event per request)
  core/
    config.py            # Pydantic Settings (reads .env)
    auth.py              # Zitadel OIDC JWT; mock mode when ZITADEL_DOMAIN=auth.example.com
    logging.py           # structlog + Wide Events
    models.py            # Shared enums (JobStatus, DataType) + Pydantic base schemas
    exceptions.py        # Custom exception hierarchy
  db/
    database.py          # SQLAlchemy async engine + session factory (asyncpg)
    models.py            # Core ORM models (DNOModel, NetzentgelteModel, HLZFModel, CrawlJobModel)
    source_models.py     # External source ORM models (MaStR, VNB, BDEW)
  jobs/
    __init__.py          # arq worker settings (CrawlWorkerSettings, ExtractWorkerSettings)
    crawl_job.py         # Steps 0-3 handler
    extract_job.py       # Steps 4-6 handler
    steps/               # Pipeline: gather_context → discover → download → extract → validate → finalize
  services/
    vnb/                 # VNB Digital GraphQL client
    discovery/           # URL discovery (BFS crawler, sitemap parser, URL scorer)
    extraction/          # Data extraction (PDF/HTML extractors, AI prompts)
    ai/                  # AI provider gateway (OpenRouter, LiteLLM, encryption)
    web_crawler.py       # BFS web crawler engine

marktstammdatenregister/
  transform_mastr.py     # MaStR XML to DNO statistics JSON
  import_mastr_stats.py  # Compatibility wrapper for backend import
  mastr/
    models.py            # Transformation data classes and catalogs
    parsers.py           # Iterative XML parsers
    aggregators.py       # DNO-level statistics aggregation
```

### Frontend (React 19 + TypeScript + Vite)
```
frontend/src/
  App.tsx                # Route definitions (react-router-dom v7, code-based routing)
  lib/
    api.ts               # Centralized Axios client, all types, all API functions
    auth-config.ts       # OIDC configuration
    ProtectedRoute.tsx   # Auth guard
  pages/                 # Top-level pages (PascalCase + Page suffix)
  features/
    dno-detail/          # Feature module: components/, views/, hooks/, utils/
  components/
    ui/                  # shadcn/ui components (keep lowercase naming)
    layout/Layout.tsx    # App shell with sidebar
```

### Key Architectural Decisions

- **Split worker architecture**: `worker-crawl` (single instance, I/O bound, polite crawling) and `worker-extract` (scalable, CPU/AI bound). Both use arq with Redis queues named `"crawl"` and `"extract"`.
- **Deterministic-first extraction**: Regex/HTML parsing first, AI fallback only when validation fails (cost-aware).
- **Pattern learning**: Successful URL patterns with `{year}` placeholders stored in `crawl_path_patterns` table, reused across DNOs.
- **Hub-and-spoke data model**: `DNOModel` is the central hub; source data (MaStR, VNB, BDEW) in separate spoke tables.
- **MaStR stats pipeline**: MaStR XML exports are transformed offline into DNO statistics, then imported into `dno_mastr_data` and denormalized quick-access fields in `dnos`.
- **Alembic migrations**: Database schema changes are managed via Alembic. In development, `USE_ALEMBIC_MIGRATIONS=false` (default) uses `create_all()` for auto-creation. In production, set `USE_ALEMBIC_MIGRATIONS=true` and run `alembic upgrade head`.
- **Wide Events logging**: One canonical structured JSON log line per request via structlog middleware. See `docs/conventions/LOGGING.md` and `docs/knowledge/LOGGING_DOMAIN.md`.

### Infrastructure
- **Database**: PostgreSQL 16 (async via asyncpg, pool size 20)
- **Job queue**: Redis 7 + arq
- **Auth**: Zitadel OIDC with role-based access (ADMIN, MEMBER, MAINTAINER). Set `ZITADEL_DOMAIN=auth.example.com` for mock mode.
- **Frontend proxy**: Vite dev server proxies `/api` to `http://backend:8000`

## 7. Coding Conventions (Project Overrides)

Base rules are in `docs/conventions/`. The overrides below are specific to this project.

### Python
- **Target**: Python 3.11
- **Line length**: 100 (ruff + black)
- **Ruff ignores**: E501, B008 (FastAPI Depends), ARG001/ARG002, RUF001/RUF003 (German text), RUF012 (SQLAlchemy patterns)

### TypeScript
- **shadcn/ui exception**: Keep original lowercase naming (`button.tsx`, `dialog.tsx`)
- **Abbreviations**: Keep `DNO`, `HLZF`, `API` uppercase in names

## 8. Tech Stack Autonomy

Do not rely on text descriptions of the stack. Determine the active versioning and dependencies by inspecting the live configuration files.

| Component | Configuration File |
|-----------|-------------------|
| Backend | `backend/pyproject.toml` |
| Frontend | `frontend/package.json` and `frontend/vite.config.ts` |
| Infrastructure | `docker-compose.yml` |

## 9. Development Workflow

When assigned a task, follow this loop.

1. **Analysis** Check `docs/ARCHITECTURE.md` for context and `README.md` for available scripts.
2. **Plan** Briefly outline proposed changes. Check `docs/ARCHITECTURE.md` to ensure architectural consistency.
3. **Implementation**
   - Apply the KISS principle (Keep It Simple, Stupid).
   - Follow naming rules in `docs/conventions/FILE_NAMING.md`.
   - Implement observability per `docs/conventions/LOGGING.md`.
   - Do not hard code secrets.
4. **Verification** Ensure new code passes linting and tests.

## 10. Interaction Guidelines

| Guideline | Description |
|-----------|-------------|
| Output Style | Provide short, detailed, and technical responses. Exclude verbose feedback loops and internal summaries. Only state relevant information. |
| Tone | Maintain a strictly professional and enterprise grade tone. **DO NOT USE EMOJIS.** Avoid informal sentence structures and dashes within sentences. |
| Reference Strategy | Link to relevant `docs/` files instead of duplicating explanations. |
| Design Philosophy | Strictly adhere to the KISS principle. Prefer modular and single responsibility functions. |
| Defensive Coding | Always validate inputs (Zod for frontend and Pydantic for backend) and handle errors gracefully. |
