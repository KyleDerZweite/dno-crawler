# AI Agent Operational Protocol

This is the single source of truth for all AI coding agents working in this repository. Tool-specific files (e.g. `CLAUDE.md`) should reference this file rather than duplicate its content.

## 1. Context and Knowledge Retrieval

**DO NOT HALLUCINATE.** You are strictly bound by the Source of Truth documentation. Before generating code, planning features, or answering questions, you must ingest the context from the following files.

| Document | Purpose |
|----------|---------|
| `docs/PROJECT.md` | Project scope, API reference, and directory structure |
| `docs/ARCHITECTURE.md` | System design, data flow diagrams, and database schema |
| `docs/FILE_NAMING_CONVENTIONS.md` | Files, classes, variables, functions, and directory structure |
| `docs/LOGGING_CONVENTIONS.md` | Structured logging, log levels, and Wide Events patterns |
| `README.md` | Installation guide and available development commands |

## 2. Project Overview

DNO Crawler is a full-stack app for automated extraction of regulatory data (Netzentgelte and HLZF) from German Distribution Network Operators. It resolves addresses to grid operators via the VNB Digital GraphQL API, then crawls operator websites to discover, download, and parse pricing documents.

## 3. Commands

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
```

### Frontend (run from `frontend/`)
```bash
npm install        # Install dependencies
npm run dev        # Vite dev server on :5173
npm run build      # tsc -b && vite build
npm run lint       # ESLint
```

### Podman
```bash
podman-compose up -d --build    # Start all 7 services
```

## 4. Architecture

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
- **No migrations (dev phase)**: The project is pre-v1. The database is recreated and seeded from scratch rather than migrated. Alembic is a dependency and will be set up for v1 production use. Tables are currently created via `Base.metadata.create_all()` in `init_db()`.
- **Wide Events logging**: One canonical structured JSON log line per request via structlog middleware. See `docs/LOGGING_CONVENTIONS.md`.

### Infrastructure
- **Database**: PostgreSQL 16 (async via asyncpg, pool size 20)
- **Job queue**: Redis 7 + arq
- **Auth**: Zitadel OIDC with role-based access (ADMIN, MEMBER, MAINTAINER). Set `ZITADEL_DOMAIN=auth.example.com` for mock mode.
- **Frontend proxy**: Vite dev server proxies `/api` to `http://backend:8000`

## 5. Coding Conventions

### Python (Backend)
- **Line length**: 100 (ruff + black)
- **Target**: Python 3.11
- **Ruff ignores**: E501, B008 (FastAPI Depends), ARG001/ARG002, RUF001/RUF003 (German text), RUF012 (SQLAlchemy patterns)
- **snake_case** for all Python files, functions, variables

### TypeScript (Frontend)
- **Components**: PascalCase.tsx (`DNOHeader.tsx`)
- **Hooks**: `use-{name}.ts` kebab-case (`use-auth.ts`)
- **Utilities**: kebab-case.ts (`data-utils.ts`)
- **Pages**: `{Name}Page.tsx` (`DashboardPage.tsx`)
- **shadcn/ui**: Keep original lowercase naming (`button.tsx`, `dialog.tsx`)
- **Path alias**: `@/*` maps to `src/*`
- **Abbreviations**: Keep `DNO`, `HLZF`, `API` uppercase in names

### Validation
- Zod for frontend, Pydantic for backend

### Logging
- Use structlog with Wide Events pattern (one event per request)
- snake_case field names, ISO 8601 timestamps
- See `docs/LOGGING_CONVENTIONS.md` for field conventions

## 6. Tech Stack Autonomy

Do not rely on text descriptions of the stack. Determine the active versioning and dependencies by inspecting the live configuration files.

| Component | Configuration File |
|-----------|-------------------|
| Backend | `backend/pyproject.toml` |
| Frontend | `frontend/package.json` and `frontend/vite.config.ts` |
| Infrastructure | `docker-compose.yml` |

## 7. Development Workflow

When assigned a task, follow this loop.

1. **Analysis** Check `docs/PROJECT.md` for context and `README.md` for available scripts.
2. **Plan** Briefly outline proposed changes. Check `docs/ARCHITECTURE.md` to ensure architectural consistency.
3. **Implementation**
   - Apply the KISS principle (Keep It Simple, Stupid).
   - Follow naming rules in `docs/FILE_NAMING_CONVENTIONS.md`.
   - Implement observability per `docs/LOGGING_CONVENTIONS.md`.
   - Do not hard code secrets.
4. **Verification** Ensure new code passes linting and tests.

## 8. Interaction Guidelines

| Guideline | Description |
|-----------|-------------|
| Output Style | Provide short, detailed, and technical responses. Exclude verbose feedback loops and internal summaries. Only state relevant information. |
| Tone | Maintain a strictly professional and enterprise grade tone. **DO NOT USE EMOJIS.** Avoid informal sentence structures and dashes within sentences. |
| Reference Strategy | Link to relevant `docs/` files instead of duplicating explanations. |
| Design Philosophy | Strictly adhere to the KISS principle. Prefer modular and single responsibility functions. |
| Defensive Coding | Always validate inputs (Zod for frontend and Pydantic for backend) and handle errors gracefully. |
