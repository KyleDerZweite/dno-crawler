# DNO Crawler

An intelligent web crawler for discovering German Distribution Network Operator (DNO) data. It automates the extraction of Netzentgelte (network charges) and HLZF (high-load time windows) using AI-powered extraction and systematic web crawling.

## Key Features

- **VNB Digital Resolution**: Resolve any German address or coordinate to its responsible DNO using the VNB Digital API.
- **AI Extraction**: Configurable OpenAI-compatible API for structured data extraction (supports Gemini, OpenRouter, Ollama).
- **BFS Web Crawler**: Robust crawling engine with robots.txt respect and adaptive discovery patterns.
- **OIDC Authentication**: Secure access management via Zitadel (OpenID Connect).
- **Interactive API Docs**: Built-in Swagger UI for testing all backend endpoints.
- **Async Pipeline**: Scalable job processing with Redis/arq and structured logging.

## Tech Stack

### Backend
- **Python 3.11+ / FastAPI**: Core async web framework.
- **SQLAlchemy 2.0**: Modern async ORM with PostgreSQL.
- **OpenAI-compatible AI**: Configurable extraction engine (Gemini, OpenRouter, local Ollama).
- **arq**: Redis-based async job processing.
- **Playwright**: Browser automation for JavaScript-heavy DNO sites.
- **structlog**: High-performance structured logging.

### Frontend
- **React / Vite**: Modern UI build system.
- **Base UI**: Performance-focused, accessible components.
- **TanStack Query (v5)**: Sophisticated server-state management.
- **TailwindCSS**: Utility-first styling with custom design tokens.

## Quick Start

### Prerequisites
- **Podman** & **Podman Compose** (or Docker equivalent)
- Zitadel Instance (OR keep `auth.example.com` for developer mock mode)
- Optional: AI API credentials (for AI-powered extraction)

### Running with Podman Compose

1. **Clone & Configure**
   ```bash
   git clone https://github.com/KyleDerZweite/dno-crawler.git
   cd dno-crawler
   cp .env.example .env # Update with your Zitadel and Gemini keys
   ```

2. **Start Services**
   ```bash
   # Build and start all containers
   podman-compose up -d --build
   ```

3. **Access Application**
   - **Frontend**: http://localhost:5173
   - **API Docs**: http://localhost:8000/docs
   - **Metrics**: http://localhost:8000/api/v1/health

## Project Structure

```text
dno-crawler/
├── backend/            # FastAPI Backend
│   ├── app/
│   │   ├── api/        # REST controllers & OIDC security
│   │   ├── crawler/    # BFS engine & discovery logic
│   │   ├── services/   # VNB client, AI extraction, recovery
│   │   └── db/         # PostgreSQL models & migrations
├── frontend/           # React Frontend
│   ├── src/
│   │   ├── pages/      # Search, DNO management, Jobs
│   │   ├── lib/        # API client & Auth provider
│   │   └── components/ # Base UI primitives
└── data/               # Persistent storage for downloads & logs
```

## Configuration

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `VITE_API_URL` | Frontend pointer to Backend API |
| `ZITADEL_DOMAIN` | Zitadel domain (set to `auth.example.com` to disable auth) |
| `AI_API_URL` | OpenAI-compatible API URL (optional, falls back to regex extraction) |
| `AI_API_KEY` | API key for AI provider (optional for local Ollama) |
| `AI_MODEL` | Vision model name (e.g., `gemini-2.0-flash`, `gpt-4o`, `qwen2.5-vl:8b`) |
| `VITE_ZITADEL_AUTHORITY` | Must match `ZITADEL_DOMAIN` (with https:// prefix) |
| `VITE_ZITADEL_CLIENT_ID` | Zitadel OIDC client ID |

## Development

```bash
# Backend Tests
cd backend && pytest

# Frontend Linting
cd frontend && npm run lint
```

## License

MIT License - see [LICENSE](LICENSE)
