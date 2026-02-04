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
│       ├── encoding_utils.py    # Character encoding detection
│       ├── file_analyzer.py     # File type detection
│       ├── html_content_detector.py  # HTML content classification
│       ├── impressum_extractor.py    # Impressum page address extraction
│       ├── pattern_learner.py   # URL pattern learning
│       ├── pdf_downloader.py    # PDF download with retry
│       ├── retry_utils.py       # Retry and backoff utilities
│       ├── robots_parser.py     # robots.txt parsing
│       ├── sample_capture.py    # Sample data capture
│       ├── url_utils.py         # URL resolution utilities
│       ├── user_agent.py        # User-Agent string management
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
| `GET /api/health` | Health check (service status) |
| `GET /api/ready` | Readiness check (database and Redis connectivity) |
| `POST /api/v1/search` | Address, coordinate, and name based DNO lookup |
| `GET /api/v1/files/downloads/{path}` | Download cached files (rate limited) |

### Protected Endpoints (Authenticated User)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/auth/me` | Current user info from OIDC token |
| `GET /api/v1/dnos` | List DNOs with pagination, search, and filtering |
| `GET /api/v1/dnos/stats` | Dashboard statistics (DNO and data counts) |
| `GET /api/v1/dnos/search-vnb` | Search VNB Digital for DNO name autocomplete |
| `GET /api/v1/dnos/search-vnb/{vnb_id}/details` | Get extended VNB details |
| `POST /api/v1/dnos` | Create a new DNO |
| `GET /api/v1/dnos/{id}` | DNO details with all associated data |
| `PATCH /api/v1/dnos/{id}` | Update DNO metadata (admin only) |
| `DELETE /api/v1/dnos/{id}` | Delete DNO and all associated data (admin only) |
| `POST /api/v1/dnos/{id}/crawl` | Trigger crawl, extract, or full pipeline job |
| `GET /api/v1/dnos/{id}/jobs` | Get recent crawl jobs for a DNO |
| `GET /api/v1/dnos/{id}/data` | Get all Netzentgelte and HLZF data |
| `PATCH /api/v1/dnos/{id}/netzentgelte/{record_id}` | Update a Netzentgelte record (admin only) |
| `DELETE /api/v1/dnos/{id}/netzentgelte/{record_id}` | Delete a Netzentgelte record (admin only) |
| `PATCH /api/v1/dnos/{id}/hlzf/{record_id}` | Update an HLZF record (admin only) |
| `DELETE /api/v1/dnos/{id}/hlzf/{record_id}` | Delete an HLZF record (admin only) |
| `GET /api/v1/dnos/{id}/files` | List source files for a DNO |
| `POST /api/v1/dnos/{id}/upload` | Upload a file for a DNO |
| `GET /api/v1/dnos/{id}/export` | Export DNO data as JSON download |
| `POST /api/v1/dnos/{id}/import` | Import JSON data (merge or replace mode) |
| `GET /api/v1/jobs` | List all jobs with filtering and pagination |
| `GET /api/v1/jobs/{id}` | Job details with individual step records |
| `DELETE /api/v1/jobs/{id}` | Delete a job |
| `POST /api/v1/verification/netzentgelte/{id}/verify` | Mark Netzentgelte record as verified |
| `POST /api/v1/verification/netzentgelte/{id}/flag` | Flag Netzentgelte record as incorrect |
| `DELETE /api/v1/verification/netzentgelte/{id}/flag` | Remove flag (maintainer or admin) |
| `POST /api/v1/verification/hlzf/{id}/verify` | Mark HLZF record as verified |
| `POST /api/v1/verification/hlzf/{id}/flag` | Flag HLZF record as incorrect |
| `DELETE /api/v1/verification/hlzf/{id}/flag` | Remove flag (maintainer or admin) |

### Admin Endpoints (Require Admin Role)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/admin/dashboard` | Admin dashboard statistics |
| `GET /api/v1/admin/flagged` | List all flagged data records for review |
| `GET /api/v1/admin/files` | List cached files with extraction status |
| `POST /api/v1/admin/extract/preview` | Preview bulk extraction (dry run) |
| `POST /api/v1/admin/extract/bulk` | Trigger bulk extraction jobs |
| `GET /api/v1/admin/extract/bulk/status` | Get bulk extraction job status |
| `POST /api/v1/admin/extract/bulk/cancel` | Cancel pending bulk extraction jobs |
| `DELETE /api/v1/admin/extract/bulk` | Delete all bulk extraction jobs (reset) |

### AI Provider Endpoints (Require Admin Role)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/ai/providers` | List available AI provider types |
| `GET /api/v1/ai/providers/{type}` | Get provider details and available models |
| `GET /api/v1/ai/configs` | List all saved AI configurations |
| `POST /api/v1/ai/configs` | Create a new AI configuration |
| `PATCH /api/v1/ai/configs/{id}` | Update an AI configuration |
| `DELETE /api/v1/ai/configs/{id}` | Delete an AI configuration |
| `POST /api/v1/ai/configs/reorder` | Reorder configurations (fallback priority) |
| `POST /api/v1/ai/configs/{id}/test` | Test a saved AI configuration |
| `POST /api/v1/ai/configs/test` | Test configuration before saving |
| `GET /api/v1/ai/status` | Get overall AI system status |

### OAuth Management Endpoints (Require Admin Role)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/admin/oauth/detect-credentials` | Detect available CLI credentials |
| `POST /api/v1/admin/oauth/google/start` | Start Google OAuth flow |
| `GET /api/v1/admin/oauth/google/callback` | Handle Google OAuth callback (browser redirect) |
| `POST /api/v1/admin/oauth/google/callback` | Handle Google OAuth callback (frontend POST) |
| `GET /api/v1/admin/oauth/google/status` | Check Google OAuth authentication status |
| `POST /api/v1/admin/oauth/google/logout` | Clear Google OAuth credentials |
| `POST /api/v1/admin/oauth/google/use-gemini-cli` | Use existing gemini-cli credentials |

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
