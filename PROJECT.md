# DNO Crawler

## Project Overview

Python/React web application for crawling German Distribution Network Operator (DNO) websites to extract Netzentgelte (network charges) and HLZF (high load time windows) data.

## Architecture

- **Backend**: FastAPI (Python 3.11+) with async SQLAlchemy, PostgreSQL, Redis
- **Frontend**: React 18 + Vite + TypeScript + TailwindCSS
- **AI/ML**: Ollama for LLM-powered extraction strategy learning
- **Jobs**: arq (Redis-based) for background crawling tasks

## Key Directories

- `backend/src/api/` - FastAPI routes and middleware
- `backend/src/core/` - Pydantic models, config
- `backend/src/db/` - SQLAlchemy ORM models
- `backend/src/crawler/` - Web crawling logic (TODO)
- `backend/src/intelligence/` - LLM integration (TODO)
- `frontend/src/pages/` - React page components
- `frontend/src/components/` - Reusable UI components
- `frontend/src/lib/` - API client, auth, utilities

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
uvicorn src.api.main:create_app --factory --reload

# Frontend
cd frontend
npm run dev

# Docker
docker compose up -d
```

## API Structure

- `/api/health` - Health checks
- `/api/public/` - Rate-limited public endpoints
- `/api/auth/` - Authentication (JWT)
- `/api/dnos/` - DNO management (authenticated)
- `/api/admin/` - Admin endpoints (admin role required)

## Development Notes

1. Always use async/await for database operations
2. Pydantic v2 syntax (model_validate, model_dump)
3. SQLAlchemy 2.0 style (select(), not query())
4. React Query for server state, context for auth
5. TailwindCSS with custom CSS variables for theming
