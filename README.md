# DNO Crawler

## Project Description

DNO Crawler is a full-stack application for automated extraction of regulatory data from German Distribution Network Operators (DNOs). The system resolves geographic locations to their responsible electricity grid operator via the VNB Digital GraphQL API, then orchestrates a multi-step pipeline to discover, download, and parse pricing documents from operator websites. Extracted data includes **Netzentgelte** (network usage charges per voltage level) and **HLZF** (Hochlastzeitfenster, peak-load time windows).

## Key Features

- **Geographic DNO Resolution**: Maps any German address or coordinate pair to the responsible distribution network operator using the VNB Digital external API.
- **Breadth-First Web Crawler**: Discovers data sources on DNO websites using BFS traversal with adaptive URL scoring, robots.txt compliance, and sitemap parsing.
- **Regex-First Extraction with AI Fallback**: Prioritizes deterministic regex and HTML parsing for structured data extraction. When sanity checks fail (e.g., insufficient voltage levels), the system falls back to OpenAI-compatible vision/text models (Gemini, OpenRouter, Ollama).
- **Pattern Learning System**: Records successful URL path patterns with year placeholders (e.g., `/downloads/{year}/netzentgelte.pdf`) in a cross-DNO database, enabling faster discovery on subsequent crawls.
- **Async Job Queue**: Offloads long-running crawl and extraction tasks to Redis-backed arq workers (split into `worker-crawl` for discovery/download and `worker-extract` for extraction/validation), providing real-time progress tracking via a polling API.
- **OIDC Authentication**: Secures protected endpoints via Zitadel-based OpenID Connect, with an automatic mock mode for local development.
- **Data Provenance Tracking**: Stores extraction metadata (source URL, file hash, extraction method, AI model used) for auditability.

## Technical Architecture

### System Overview

The application follows a layered architecture with clear separation between the HTTP API, background processing, and data persistence.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Frontend (React SPA)                           │
│   Vite + TypeScript + TailwindCSS + TanStack Query + react-oidc-context     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ REST API + JWT Bearer Token
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Backend (FastAPI)                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │  Public Routes  │  │ Protected Routes│  │      Service Layer          │  │
│  │  POST /search   │  │ POST /dnos/crawl│  │  VNBDigitalClient (GraphQL) │  │
│  │  GET /api/health│  │ GET /dnos/{id}  │  │  BDEWClient (JTables POST)  │  │
│  │  GET /api/ready │  │ GET /jobs/{id}  │  │  MaStR Seed Import (Manual) │  │
│  │                 │  │ AI Config CRUD  │  │  WebCrawler (BFS Engine)    │  │
│  │                 │  │ Admin Dashboard │  │  AIExtractor (OpenAI SDK)   │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              │                       │                       │
              ▼                       ▼                       ▼
     ┌────────────────┐      ┌────────────────┐      ┌────────────────┐
     │   PostgreSQL   │      │     Redis      │      │   arq Worker   │
     │   (SQLAlchemy  │      │  (Job Queue +  │      │  (Background   │
     │    Async ORM)  │      │     Cache)     │      │   Processing)  │
     └────────────────┘      └────────────────┘      └────────────────┘
```

### Data Flow: Address to Extracted Data

1. **Search Request**: User submits an address via `POST /api/v1/search`. The backend queries the VNB Digital GraphQL API to resolve the address to coordinates, then looks up the responsible DNO.

2. **Skeleton Creation**: If the DNO does not exist in the database, a skeleton record is created with the VNB-provided name, website, and contact information. The location is cached by address hash for future lookups.

3. **Crawl Job Dispatch**: An authenticated user triggers `POST /api/v1/dnos/{id}/crawl`, which creates a `CrawlJob` entity and enqueues a task to Redis. The arq worker picks up the job asynchronously.

4. **Pipeline Execution**: The worker executes a multi-step pipeline:
   - **Step 00 (Gather Context)**: Loads DNO metadata, source profiles, and enrichment data.
   - **Step 01 (Discover)**: Uses cached file paths, learned URL patterns, or BFS crawling to locate the data source. The `WebCrawler` class implements priority-queue BFS with keyword-based URL scoring.
   - **Step 02 (Download)**: Fetches the discovered PDF or HTML document to local storage.
   - **Step 03 (Extract)**: Applies regex extraction (`PDFExtractor`, `HTMLExtractor`) first. If validation fails (e.g., fewer than 3 voltage level records), falls back to `AIExtractor` which uses the OpenAI SDK with vision or text mode.
   - **Step 04 (Validate)**: Runs sanity checks on extracted records.
   - **Step 05 (Finalize)**: Persists Netzentgelte and HLZF records, updates source profiles with successful URL patterns for future crawls.

5. **Result Retrieval**: Frontend polls `GET /api/v1/dnos/{id}/jobs` until status is `completed`, then fetches structured data via `GET /api/v1/dnos/{id}`.

### External Data Sources

The system aggregates DNO metadata from three authoritative sources:

| Source | Integration Method | Data Provided |
|--------|-------------------|---------------|
| **VNB Digital** | GraphQL API queries | Address-to-DNO resolution, official names, homepage URLs, contact information |
| **Marktstammdatenregister (MaStR)** | Manual XML export, offline transform, database import | Market roles, ACER codes, legal names, connection-point statistics, network statistics, installed capacity statistics |
| **BDEW Codes Registry** | JTables endpoint via POST request interception | BDEW identification codes, grid operator function codes |

VNB Digital provides real-time lookups. MaStR data requires periodic manual export from the Bundesnetzagentur portal due to API access restrictions, then local transformation before import. BDEW codes are retrieved by reverse-engineering the JTables jQuery plugin requests used by the BDEW public registry interface.

## MaStR Pipeline (Current Workflow)

The current MaStR module lives in `marktstammdatenregister/` and is used as an offline transformation/import pipeline.

Detailed instructions: `marktstammdatenregister/README.md`

Quick start:

```bash
# 1) Transform MaStR XML export to JSON stats (from repo root)
python marktstammdatenregister/transform_mastr.py \
   --data-dir ./marktstammdatenregister/data \
   --output ./marktstammdatenregister/dno_stats.json

# 2) Apply DB migration and import (from backend/)
cd backend
alembic upgrade head
python scripts/import_mastr_stats.py --file ../marktstammdatenregister/dno_stats.json --dry-run
python scripts/import_mastr_stats.py --file ../marktstammdatenregister/dno_stats.json
```

Notes:
- `dno_stats.json`, `.csv`, and raw export files are local artifacts and not meant to be committed.
- MaStR connection points are stored with canonical 7-level distribution and legacy aggregate compatibility fields.

### Database Schema (Core Entities)

| Table | Purpose |
|-------|---------|
| `dnos` | Hub entity for DNOs. Contains resolved display fields, external IDs (MaStR, VNB, BDEW), denormalized MaStR quick-access stats (`connection_points_count`, `total_capacity_mw`), crawlability status, and robots.txt metadata. |
| `dno_mastr_data` | Marktstammdatenregister source data and computed MaStR statistics (canonical connection-point levels, compatibility buckets, network flags, capacity and unit totals, quality metadata). |
| `dno_vnb_data` | VNB Digital API data (official names, homepage URLs, contact info). |
| `dno_bdew_data` | BDEW identification codes and market function codes (one to many). |
| `locations` | Geographic lookups. Maps address hashes and coordinates to DNO IDs for O(1) cache hits. |
| `netzentgelte` | Network tariffs by year and voltage level. Stores Arbeitspreis (ct/kWh) and Leistungspreis (EUR/kW). |
| `hlzf` | Peak load time windows by year, voltage level, and season (winter, spring, summer, autumn). |
| `data_sources` | Extraction provenance tracking (source URL, file hash, extraction method, confidence). |
| `dno_source_profiles` | Learned discovery state per DNO and data type. Stores URL patterns with `{year}` placeholders. |
| `crawl_path_patterns` | Cross DNO learned URL path patterns with success/failure counts for prioritization. |
| `crawl_jobs` | Job state machine tracking status, progress, current step, parent job linking, and error messages. |
| `crawl_job_steps` | Individual step execution records with timestamps and structured details. |
| `ai_provider_configs` | Multi provider AI configuration with API key and OAuth support, priority ordering. |
| `query_logs` | User search queries for analytics. |
| `system_logs` | System level logs with trace IDs. |

### Extraction Strategy

The extraction layer implements a cost-aware, deterministic-first approach:

1. **Regex/HTML Parsing**: `PDFExtractor` uses `pdfplumber` for tabular data extraction with regex post-processing. `HTMLExtractor` uses BeautifulSoup with CSS selectors.

2. **Sanity Validation**: Extracted records must pass domain-specific checks:
   - Netzentgelte: ≥3 voltage levels, each with at least one price value.
   - HLZF: ≥1 record with a winter time window present.

3. **AI Fallback**: If validation fails and AI is configured, the file is sent to an OpenAI-compatible endpoint. For PDFs, irrelevant pages are pre-filtered using keyword matching to reduce token costs. The response follows a structured JSON schema enforced via prompt engineering.

## Getting Started

### Prerequisites

- **Container Runtime**: Podman with Podman Compose, or Docker with Docker Compose
- **Authentication Provider**: Zitadel instance, or use mock mode for development
- **AI Provider** (optional): API credentials for Gemini, OpenRouter, or local Ollama

### Installation

Clone the repository:

```bash
git clone https://github.com/KyleDerZweite/dno-crawler.git
cd dno-crawler
```

Copy and configure environment variables:

```bash
cp .env.example .env
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Yes | PostgreSQL credentials |
| `REDIS_URL` | Yes | Redis connection string for job queue |
| `ZITADEL_DOMAIN` | No | Zitadel domain. Set to `auth.example.com` to enable mock mode |
| `AI_API_URL` | No | OpenAI-compatible endpoint URL |
| `AI_API_KEY` | No | API key for AI provider (omit for local Ollama) |
| `AI_MODEL` | No | Model identifier (e.g., `gemini-2.0-flash`, `gpt-4o`) |
| `VITE_API_URL` | Yes | Backend API URL for frontend |

### Build and Run

Start all services with the container runtime:

```bash
podman-compose up -d --build
# or
docker compose up -d --build
```

Access the application:

- **Frontend**: http://localhost:5173
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/health

### Local Development (Without Containers)

Backend:

```bash
cd backend
uv sync  # or pip install -r requirements.txt
uvicorn app.api.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

### Database Migrations

Schema changes are managed via Alembic:

```bash
cd backend

# Generate a new migration after model changes
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

**Production Setup:**
1. Set `USE_ALEMBIC_MIGRATIONS=true` in your environment
2. Run `alembic upgrade head` before starting the application
3. The application will skip `create_all()` and use the migrated schema

**Development:**
- By default, the application uses `create_all()` for automatic schema creation
- No manual migrations required during development

### Running Tests

```bash
cd backend
pytest
```

## Documentation

For detailed technical documentation, see the [docs](docs/) directory:

- [Architecture](docs/ARCHITECTURE.md) - System design, data flow diagrams, database schema, API reference
- [File Naming Conventions](docs/conventions/FILE_NAMING.md) - Code style guidelines

## Maintenance

### Job Recovery

The `crawl_recovery` service automatically resets jobs stuck in `running` or `crawling` state on backend startup, handling cases where the worker was terminated mid-execution.

### Observability

- **Logging**: Structured JSON logging via `structlog` with correlation IDs
- **Health Endpoint**: `GET /api/health` and `GET /api/ready` for uptime and readiness monitoring
- **Job Visibility**: Real-time step-by-step progress via `crawl_jobs` and `crawl_job_steps` tables

## License

MIT License © 2025 KyleDerZweite. See [LICENSE](LICENSE) for details.