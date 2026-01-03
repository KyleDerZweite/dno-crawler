# DNO Crawler

## Overview

DNO Crawler is a full-stack application designed to extract, normalize, and serve data from German Distribution Network Operators (DNOs). The system automates the retrieval of Netzentgelte (network charges) and HLZF (high-load time windows) by combining intelligent web crawling with AI-powered document extraction. Users can resolve any German address or coordinate to its responsible DNO using the VNB Digital API, then trigger automated data extraction from the operator's website.

## Core Features

- **VNB Digital Resolution**: Resolves German addresses and coordinates to their responsible distribution network operator via the VNB Digital API.
- **AI-Powered Extraction**: Supports OpenAI-compatible APIs (Gemini, OpenRouter, Ollama) for structured data extraction from PDFs and HTML documents, with regex-based fallback when AI is unavailable.
- **BFS Web Crawler**: Implements breadth-first search discovery with robots.txt compliance, sitemap parsing, and adaptive URL scoring.
- **OIDC Authentication**: Provides secure access control via Zitadel with a mock mode for local development.
- **Async Job Processing**: Handles long-running extraction tasks through Redis and arq workers with real-time status tracking.

## Architecture

The backend is built with **FastAPI** (Python 3.11+) using **SQLAlchemy 2.0** for async PostgreSQL operations. Background jobs are processed via **arq** with Redis as the message broker. The frontend is a **React** single-page application built with **Vite**, **TypeScript**, and **TailwindCSS**, using **TanStack Query** for server-state management.

```
dno-crawler/
├── backend/
│   ├── app/
│   │   ├── api/          # REST endpoints and authentication
│   │   ├── core/         # Configuration, models, exceptions
│   │   ├── db/           # SQLAlchemy ORM models
│   │   ├── jobs/         # Background job step definitions
│   │   └── services/     # VNB client, extraction, crawling logic
├── frontend/
│   ├── src/
│   │   ├── pages/        # React page components
│   │   ├── components/   # Reusable UI components
│   │   └── lib/          # API client and auth utilities
└── data/                 # Persistent storage for downloads
```

## Installation

### Prerequisites

- Podman and Podman Compose (or Docker equivalent)
- A Zitadel instance for authentication, or use `auth.example.com` to enable mock mode
- Optional: AI API credentials for extraction (Gemini, OpenRouter, or local Ollama)

### Setup

Clone the repository and configure environment variables:

```bash
git clone https://github.com/KyleDerZweite/dno-crawler.git
cd dno-crawler
cp .env.example .env
```

Edit .env to set your database URL, Zitadel credentials, and optional AI provider settings.

Start all services:

```bash
podman-compose up -d --build
```

### Configuration

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection for job queue |
| `ZITADEL_DOMAIN` | Zitadel domain (set to `auth.example.com` to disable auth) |
| `AI_API_URL` | OpenAI-compatible API endpoint |
| `AI_API_KEY` | API key for AI provider |
| `AI_MODEL` | Model name (e.g., `gemini-2.0-flash`, `gpt-4o`) |

## Usage

Access the application at the following endpoints:

- **Frontend**: `http://localhost:5173`
- **API Documentation**: `http://localhost:8000/docs`
- **Health Check**: `http://localhost:8000/api/v1/health`

To search for a DNO, submit an address or coordinates via the search interface. The system will resolve the operator and create a skeleton record. Authenticated users can then trigger a crawl job to extract pricing data from the operator's website.

For local development without containers:

```bash
# Backend
cd backend
uvicorn app.api.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

Run backend tests:

```bash
cd backend
pytest
```

## Production Readiness

For production deployments, ensure the following standards are met:

- **Security**: Strict OIDC configuration with Zitadel. Mock auth must be disabled.
- **Reliability**: Use the provided `docker-compose.yml` for containerized orchestration with health checks.
- **Observability**: Monitor logs via `structlog` and use the `/api/v1/health` endpoint for uptime tracking.
- **Backup**: Regularly backup the PostgreSQL volume managed by the `db` service.

Consult [PRODUCTION_REPORT.md](PRODUCTION_REPORT.md) for a detailed checklist of remaining production gaps.

---

## Maintenance

### Background Jobs
Async jobs are managed via **arq**. If the worker crashes, the `crawl_recovery` service will automatically reset stuck jobs on the next backend startup.

### Database Migrations
When updating the schema, generate and apply migrations via Alembic:
```bash
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.