# DNO Crawler

## Project Overview

Full-stack web application for automated extraction of regulatory data from German Distribution Network Operators (DNOs). The system resolves geographic locations to their responsible electricity grid operator, then orchestrates a multi-step pipeline to discover, download, and parse pricing documents. Target data includes Netzentgelte (network usage charges) and HLZF (Hochlastzeitfenster, peak-load time windows).

## Architecture

- **Backend**: FastAPI (Python 3.11+) with async SQLAlchemy 2.0, PostgreSQL, Redis
- **Frontend**: React 18 + Vite + TypeScript + TailwindCSS + TanStack Query + Base UI
- **AI/ML**: OpenAI-compatible API (Gemini, OpenRouter, Ollama) with regex-first extraction strategy
- **Auth**: Modular OIDC (Zitadel) with automatic mock mode (`ZITADEL_DOMAIN=auth.example.com`)
- **Jobs**: arq (Redis-based) for background crawl and extraction tasks

## External Data Sources

| Source | Integration | Data |
|--------|-------------|------|
| VNB Digital | GraphQL API | Address resolution, DNO contact info |
| Marktstammdatenregister (MaStR) | Manual XML/CSV import | Market roles, ACER codes, legal names |
| BDEW Codes Registry | JTables POST interception | BDEW identification codes |

## Key Directories

```
backend/
├── app/
│   ├── api/            # FastAPI routes and middleware
│   │   └── routes/     # Endpoint modules (dnos, jobs, search, auth, admin)
│   ├── core/           # Config, Pydantic schemas, auth abstraction
│   ├── db/             # SQLAlchemy ORM models (models.py, source_models.py)
│   ├── jobs/           # arq job definitions
│   │   └── steps/      # Pipeline steps (discover, download, extract, validate)
│   └── services/       # Business logic
│       ├── discovery/  # Sitemap, BFS, scoring
│       ├── extraction/ # AI, PDF, HTML extractors
│       └── vnb/        # VNB Digital GraphQL client
frontend/
├── src/
│   ├── pages/          # React page components
│   ├── components/     # Reusable UI components
│   ├── lib/            # API client, auth utilities, types
│   └── hooks/          # Custom React hooks
data/
├── seed-data/          # MaStR exports, enriched DNO JSON
└── downloads/          # Crawled PDFs and HTML files
```

## Database Schema

Core tables:

| Table | Purpose |
|-------|---------|
| `dnos` | Hub entity with resolved fields, external IDs (MaStR, VNB, BDEW), crawlability status |
| `dno_mastr_data` | Raw MaStR data (market roles, addresses) |
| `dno_vnb_data` | VNB Digital API data (official names, contact) |
| `dno_bdew_data` | BDEW codes (one-to-many) |
| `locations` | Address hash → DNO mapping for O(1) lookups |
| `netzentgelte` | Network tariffs by year and voltage level |
| `hlzf` | Peak-load time windows by year, voltage, season |
| `dno_source_profiles` | Learned URL patterns per DNO/data type |
| `crawl_path_patterns` | Cross-DNO path patterns with success rates |
| `crawl_jobs` | Job state machine (status, progress, steps) |
| `crawl_job_steps` | Individual step execution records |
| `data_sources` | Provenance tracking (source URL, file hash, method) |

## Quick Start

```bash
# Development with containers
podman-compose up -d --build

# Local backend
cd backend
uv sync
uvicorn app.api.main:app --reload

# Local frontend
cd frontend
npm install
npm run dev
```

## API Structure

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /api/v1/health` | Public | Health check |
| `POST /api/v1/search` | Public | Address/coordinate DNO lookup |
| `GET /api/v1/auth/me` | Protected | Current user info |
| `GET /api/v1/dnos` | Protected | List DNOs |
| `GET /api/v1/dnos/{id}` | Protected | DNO details with data |
| `POST /api/v1/dnos/{id}/crawl` | Protected | Trigger crawl job |
| `GET /api/v1/jobs` | Protected | List jobs |
| `GET /api/v1/jobs/{id}` | Protected | Job details with steps |
| `GET /api/v1/admin/stats` | Admin | System statistics |

## Development Notes

1. Always use async/await for database operations (SQLAlchemy 2.0 style)
2. Pydantic v2 syntax (`model_validate`, `model_dump`)
3. SQLAlchemy 2.0 select statements (`select()`, not `query()`)
4. TanStack Query for server state, react-oidc-context for auth
5. TailwindCSS with CSS variables for theming
6. Regex-first extraction with AI fallback when sanity checks fail
