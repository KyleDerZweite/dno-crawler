# DNO Crawler

## Project Overview

Python/React web application for crawling German Distribution Network Operator (DNO) websites to extract Netzentgelte (network charges) and HLZF (high load time windows) data.

## Architecture

- **Backend**: FastAPI (Python 3.11+) with async SQLAlchemy, PostgreSQL, Redis
- **Frontend**: React 18 + Vite + TypeScript + TailwindCSS + Base UI
- **AI/ML**: Google Gemini for structured data extraction
- **Auth**: Modular OIDC (Zitadel) or automatic mock mode (`ZITADEL_DOMAIN=auth.example.com`)
- **Jobs**: arq (Redis-based) for background crawling tasks

## Key Directories

- `backend/app/api/` - FastAPI routes and middleware
- `backend/app/core/` - Pydantic models, config, auth abstraction
- `backend/app/db/` - SQLAlchemy ORM models
- `backend/app/crawler/` - BFS engine & discovery logic
- `backend/app/services/` - VNB client, AI extraction, recovery
- `frontend/src/pages/` - React page components
- `frontend/src/components/` - Reusable UI components
- `frontend/src/lib/` - API client, auth abstraction, utilities

## Database Schema

Main tables:
- `dnos` - Distribution network operators
- `netzentgelte` - Network charges (prices by PLZ)
- `hlzf` - High load time windows
- `users` - User accounts with roles
- `crawl_jobs` - Crawl job tracking
- `extraction_strategies` - Learned extraction patterns
- `crawl_attempts` - Success/failure tracking for learning

## Commands

```bash
# Backend
cd backend
uvicorn app.api.main:app --reload

# Frontend
cd frontend
npm run dev

# Docker
docker compose up -d
```

## API Structure

- `/health` - Health checks
- `/api/v1/search/` - Public search (DNO/Location skeleton creation)
- `/api/v1/auth/` - Authentication endpoints
- `/api/v1/dnos/` - DNO management (authenticated)
- `/api/v1/jobs/` - Job tracking & management
- `/api/v1/admin/` - System admin endpoints

## Development Notes

1. Always use async/await for database operations
2. Pydantic v2 syntax (model_validate, model_dump)
3. SQLAlchemy 2.0 style (select(), not query())
4. React Query for server state, context for auth
5. TailwindCSS with custom CSS variables for theming
