# DNO Crawler

An intelligent web crawler for extracting German Distribution Network Operator (DNO) data, specifically Netzentgelte (network charges) and HLZF (Hochlastzeitfenster - high load time windows).

## Features

- **Smart Crawling**: Automatically discovers and extracts pricing data from DNO websites
- **PDF Extraction**: Downloads and parses PDF documents, storing originals for verification
- **Learning System**: Uses LLM (Ollama) to improve extraction strategies over time
- **REST API**: Full-featured API with authentication and role-based access
- **Web Dashboard**: React-based UI for searching data and managing crawls
- **Background Jobs**: Async job processing with Redis/arq
- **File Storage**: Local file storage with support for remote backends (OpenCloud, S3)

## Tech Stack

### Backend
- **Python 3.11+** - Core language
- **FastAPI** - Modern async web framework
- **SQLAlchemy 2.0** - Async ORM with PostgreSQL
- **Pydantic v2** - Data validation
- **arq** - Redis-based job queue
- **Ollama** - Local LLM for intelligent extraction
- **BeautifulSoup4** - HTML parsing
- **pdfplumber/PyMuPDF** - PDF text extraction
- **Playwright** - Browser automation for JS-rendered pages

### Frontend
- **React 18** - UI library
- **Vite** - Build tool
- **TypeScript** - Type safety
- **TailwindCSS** - Styling
- **Radix UI** - Accessible components
- **TanStack Query** - Server state management

### Infrastructure
- **PostgreSQL 16** - Primary database
- **Redis 7** - Caching and job queue
- **Podman / Podman Compose** - Container orchestration
- **Ollama** - Local LLM inference

## Quick Start

### Prerequisites

- **Podman** and **Podman Compose** (or Docker/Docker Compose)
- Node.js 20+ (for frontend development)
- Python 3.11+ (for backend development)

### Environment Setup

1. **Clone and enter directory**
   ```bash
   git clone https://github.com/KyleDerZweite/dno-crawler.git
   cd dno-crawler
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env
   # Edit .env with your settings (especially JWT_SECRET, POSTGRES_PASSWORD)
   ```

### Full Container Setup (Recommended)

```bash
# Start all services
podman-compose up -d

# View logs
podman-compose logs -f backend

# Pull Ollama models (first time only)
podman exec dno-crawler-ollama ollama pull llama3.2
podman exec dno-crawler-ollama ollama pull llava

# Stop everything
podman-compose down
```

### Development Setup (Local Backend/Frontend)

1. **Start infrastructure services only**
   ```bash
   ```

2. **Backend setup**
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   
   # Run migrations (once alembic is set up)
   # alembic upgrade head
   
   # Start server
   uvicorn app.api.main:create_app --factory --reload
   ```

3. **Frontend setup** (new terminal)
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

4. **Access the application**
   - Frontend: http://localhost:5173
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

## Project Structure

```
dno-crawler/
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI routes and middleware
│   │   ├── core/          # Pydantic models and config
│   │   ├── db/            # SQLAlchemy models and database
│   │   ├── crawler/       # Web crawling logic
│   │   │   ├── discovery/ # URL/source discovery
│   │   │   ├── fetcher/   # HTTP/browser fetching
│   │   │   └── parser/    # HTML/PDF parsing
│   │   ├── intelligence/  # LLM integration and learning
│   │   │   ├── analyzer/  # Data analysis
│   │   │   ├── llm/       # Ollama client
│   │   │   └── strategy/  # Extraction strategies
│   │   └── worker/        # Background job processing
│   ├── migrations/        # Alembic database migrations
│   ├── tests/             # pytest tests
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── pages/         # Page components
│   │   ├── lib/           # Utilities, API client, auth
│   │   └── hooks/         # Custom React hooks
│   └── package.json
├── data/                  # Persistent file storage (mounted volume)
│   ├── downloads/         # Downloaded PDFs and documents
│   └── strategies/        # LLM extraction strategies
├── docker-compose.yml     # Podman/Docker compose file
└── README.md
```

## API Endpoints

### Public (rate-limited)
- `GET /api/v1/search` - Search data by DNO, year, type
- `GET /api/v1/dnos` - List all DNOs (public info)
- `GET /api/v1/years` - List available years

### Authenticated
- `POST /api/v1/auth/login` - Login
- `POST /api/v1/auth/register` - Register (requires admin approval)
- `POST /api/v1/auth/refresh` - Refresh access token
- `GET /api/v1/auth/me` - Current user info
- `GET /api/v1/dnos/` - List DNOs with stats
- `GET /api/v1/dnos/{id}` - DNO details
- `POST /api/v1/dnos/{id}/crawl` - Trigger crawl job
- `GET /api/v1/dnos/{id}/data` - Get DNO data
- `GET /api/v1/dnos/{id}/jobs` - Get DNO crawl history

### Admin
- `GET /api/v1/admin/dashboard` - System statistics
- `GET /api/v1/admin/users` - List users
- `GET /api/v1/admin/users/pending` - Pending approvals
- `POST /api/v1/admin/users/{id}/approve` - Approve/reject user
- `PATCH /api/v1/admin/users/{id}/role` - Update user role
- `DELETE /api/v1/admin/users/{id}` - Delete user
- `GET /api/v1/admin/jobs` - List all jobs
- `POST /api/v1/admin/jobs` - Create standalone job

## Configuration

Environment variables (set in `.env`):

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `OLLAMA_URL` | Ollama API URL | `http://localhost:11434` |
| `JWT_SECRET` | JWT signing secret (min 32 chars) | Required |
| `CORS_ORIGINS` | Allowed CORS origins (JSON array) | `["http://localhost:5173"]` |
| `STORAGE_PATH` | Base path for file storage | `./data` |
| `ADMIN_EMAIL` | Initial admin email | Optional |
| `ADMIN_USERNAME` | Initial admin username | Optional |
| `ADMIN_PASSWORD` | Initial admin password | Optional |

## File Storage

Downloaded PDFs and documents are stored locally with the following structure:

```
data/downloads/{dno_slug}/{year}/{content_hash}.pdf
```

Each file record in the database includes:
- Original download URL
- Content hash (SHA-256)
- Download timestamp
- File size and MIME type
- Link to extracted data records

This allows:
- Serving files via API for user download
- Keeping original files for human verification
- Deduplication via content hashing
- Future migration to cloud storage (S3, OpenCloud)

## Development

### Running Tests

```bash
cd backend
pytest
```

### Code Style

```bash
# Backend
ruff check .
ruff format .

# Frontend
npm run lint
npm run format
```

### Database Migrations

```bash
cd backend

# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

## License

MIT License - see [LICENSE](LICENSE) file
