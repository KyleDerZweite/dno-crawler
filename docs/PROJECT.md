# DNO Crawler

## Project Overview

Full stack web application for automated extraction of regulatory data from German Distribution Network Operators (DNOs). The system resolves geographic locations to their responsible electricity grid operator, then orchestrates a multi step pipeline to discover, download, and parse pricing documents. Target data includes Netzentgelte (network usage charges) and HLZF (Hochlastzeitfenster, peak load time windows).

## Architecture

| Layer | Technology |
|-------|------------|
| Backend | FastAPI (Python 3.11+) with async SQLAlchemy 2.0, PostgreSQL, Redis |
| Frontend | React 19 + Vite 7 + TypeScript 5.9 + TailwindCSS 3.4 + TanStack Query 5 + Base UI |
| AI/ML | OpenAI compatible API (Gemini, OpenRouter, Ollama) with regex first extraction strategy |
| Auth | Modular OIDC (Zitadel) with automatic mock mode when `ZITADEL_DOMAIN=auth.example.com` |
| Jobs | arq (Redis based) for background crawl and extraction tasks |

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
│   ├── api/                # FastAPI routes and middleware
│   │   ├── middleware/     # Request logging, CORS, rate limiting
│   │   └── routes/         # Endpoint modules
│   │       ├── admin.py    # Admin dashboard and statistics
│   │       ├── ai.py       # AI provider management
│   │       ├── auth.py     # Authentication endpoints
│   │       ├── dnos/       # DNO CRUD and crawl operations
│   │       ├── files.py    # File download endpoints
│   │       ├── health.py   # Health check endpoint
│   │       ├── jobs.py     # Job tracking endpoints
│   │       ├── oauth.py    # OAuth flow endpoints
│   │       ├── search.py   # Address search endpoint
│   │       └── verification.py  # Data verification endpoints
│   ├── core/               # Config, Pydantic schemas, auth abstraction
│   ├── db/                 # SQLAlchemy ORM models
│   │   ├── models.py       # Core models (DNO, Location, Netzentgelte, HLZF, Jobs)
│   │   ├── source_models.py # Source data models (MaStR, VNB, BDEW)
│   │   ├── database.py     # Database connection and session management
│   │   └── seeder.py       # Seed data import utilities
│   ├── jobs/               # arq job definitions
│   │   ├── crawl_job.py    # Full crawl pipeline job
│   │   ├── enrichment_job.py # DNO enrichment job
│   │   ├── extract_job.py  # Extraction only job
│   │   ├── search_job.py   # Background search job
│   │   └── steps/          # Pipeline steps
│   │       ├── step_00_gather_context.py
│   │       ├── step_01_discover.py
│   │       ├── step_02_download.py
│   │       ├── step_03_extract.py
│   │       ├── step_04_validate.py
│   │       └── step_05_finalize.py
│   └── services/           # Business logic
│       ├── ai/             # AI provider abstraction and extractors
│       ├── discovery/      # Sitemap parsing, BFS crawling, URL scoring
│       ├── extraction/     # PDF, HTML, and AI extractors
│       ├── vnb/            # VNB Digital GraphQL client
│       ├── bdew_client.py  # BDEW codes API client
│       ├── content_verifier.py  # Data verification service
│       ├── crawl_recovery.py    # Job recovery on startup
│       ├── file_analyzer.py     # File type detection
│       ├── pattern_learner.py   # URL pattern learning
│       ├── robots_parser.py     # robots.txt parsing
│       ├── sample_capture.py    # Sample data capture
│       ├── url_utils.py         # URL resolution utilities
│       └── web_crawler.py       # BFS web crawler
frontend/
├── src/
│   ├── pages/              # React page components
│   │   ├── AdminPage.tsx
│   │   ├── DashboardPage.tsx
│   │   ├── DNODetailPage.tsx
│   │   ├── DNOsPage.tsx
│   │   ├── JobDetailsPage.tsx
│   │   ├── JobsPage.tsx
│   │   ├── LandingPage.tsx
│   │   ├── LogoutPage.tsx
│   │   ├── SearchPage.tsx
│   │   └── SettingsPage.tsx
│   ├── features/           # Feature modules
│   │   ├── admin/          # Admin feature components
│   │   └── dno-detail/     # DNO detail feature
│   │       ├── components/ # Feature specific components
│   │       ├── hooks/      # Feature specific hooks
│   │       ├── views/      # Tab views (Overview, DataExplorer, Technical, SQLExplorer)
│   │       └── utils/      # Feature utilities
│   ├── components/         # Reusable UI components
│   │   ├── ui/             # Base UI primitives
│   │   └── layout/         # Layout components
│   ├── lib/                # Core utilities
│   │   ├── api.ts          # Centralized API client
│   │   ├── use-auth.ts     # Authentication hook
│   │   ├── AuthProvider.tsx
│   │   ├── AuthCallback.tsx
│   │   └── ProtectedRoute.tsx
│   ├── hooks/              # Global custom hooks
│   ├── types/              # TypeScript type definitions
│   └── constants/          # Application constants
data/
├── seed-data/              # MaStR exports, enriched DNO JSON
└── downloads/              # Crawled PDFs and HTML files
```

## Database Schema

### Core Tables

| Table | Purpose |
|-------|---------|
| `dnos` | Hub entity with resolved fields, external IDs (MaStR, VNB, BDEW), crawlability status, robots.txt metadata |
| `dno_mastr_data` | Raw MaStR data (market roles, addresses, ACER codes) |
| `dno_vnb_data` | VNB Digital API data (official names, contact info) |
| `dno_bdew_data` | BDEW codes (one to many relationship) |
| `locations` | Address hash to DNO mapping for O(1) lookups |
| `netzentgelte` | Network tariffs by year and voltage level with verification status |
| `hlzf` | Peak load time windows by year, voltage, and season |
| `dno_source_profiles` | Learned URL patterns per DNO and data type |
| `crawl_path_patterns` | Cross DNO path patterns with success rates |
| `crawl_jobs` | Job state machine (status, progress, steps, parent job linking) |
| `crawl_job_steps` | Individual step execution records with timing |
| `data_sources` | Provenance tracking (source URL, file hash, extraction method) |

### Logging Tables

| Table | Purpose |
|-------|---------|
| `query_logs` | User search queries for analytics |
| `system_logs` | System level logs with trace IDs |

### Configuration Tables

| Table | Purpose |
|-------|---------|
| `ai_provider_configs` | Multi provider AI configuration with OAuth and API key support |

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

### Public Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/health` | Health check |
| `POST /api/v1/search` | Address and coordinate DNO lookup |

### Protected Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/auth/me` | Current user info |
| `GET /api/v1/dnos` | List DNOs with pagination and filtering |
| `GET /api/v1/dnos/{id}` | DNO details with data |
| `POST /api/v1/dnos/{id}/crawl` | Trigger crawl job |
| `GET /api/v1/jobs` | List jobs |
| `GET /api/v1/jobs/{id}` | Job details with steps |
| `GET /api/v1/files/{path}` | Download cached files |
| `POST /api/v1/verification/{type}/{id}` | Verify extracted data |

### Admin Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/admin/stats` | System statistics |
| `GET /api/v1/admin/dashboard` | Admin dashboard data |
| `GET /api/v1/admin/flagged` | Flagged data items |
| `POST /api/v1/admin/bulk-extract` | Bulk extraction operations |

## Frontend Routes

| Route | Component | Description |
|-------|-----------|-------------|
| `/` | LandingPage | Public landing page |
| `/login` | LoginRedirect | Redirects to OIDC provider |
| `/callback` | AuthCallback | OIDC callback handler |
| `/logout` | LogoutPage | Logout confirmation |
| `/dashboard` | DashboardPage | Main dashboard |
| `/search` | SearchPage | Address search |
| `/dnos` | DNOsPage | DNO list with filters |
| `/dnos/:id` | DNODetailPage | DNO detail with tabs |
| `/dnos/:id/overview` | Overview | DNO overview tab |
| `/dnos/:id/data` | DataExplorer | Data explorer tab |
| `/dnos/:id/analysis` | Analysis | Analysis tab |
| `/dnos/:id/files` | SourceFiles | Source files tab |
| `/dnos/:id/jobs` | JobHistory | Job history tab |
| `/dnos/:id/tools` | Tools | Tools tab |
| `/dnos/:id/technical` | Technical | Technical info (sitemap, robots.txt) |
| `/dnos/:id/sql` | SQLExplorer | Raw SQL query explorer |
| `/jobs` | JobsPage | Jobs list |
| `/jobs/:id` | JobDetailsPage | Job details |
| `/admin` | AdminPage | Admin dashboard |
| `/settings` | SettingsPage | User settings |

## Development Notes

1. Always use async/await for database operations (SQLAlchemy 2.0 style)
2. Pydantic v2 syntax (`model_validate`, `model_dump`)
3. SQLAlchemy 2.0 select statements (`select()`, not `query()`)
4. TanStack Query for server state, react-oidc-context for auth
5. TailwindCSS with CSS variables for theming
6. Regex first extraction with AI fallback when sanity checks fail
7. Zod for frontend validation, Pydantic for backend validation
