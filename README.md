# DNO Crawler

An intelligent web crawler for extracting German Distribution Network Operator (DNO) data, specifically Netzentgelte (network charges) and HLZF (Hochlastzeitfenster - high load time windows).

## Features

- **Smart Crawling**: Automatically discovers and extracts pricing data from DNO websites
- **Learning System**: Uses LLM (Ollama) to improve extraction strategies over time
- **REST API**: Full-featured API with authentication and rate limiting
- **Web Dashboard**: React-based UI for searching data and managing crawls
- **Background Jobs**: Async job processing with Redis/arq
- **Caching**: Redis caching for fast API responses

## Tech Stack

### Backend
- **Python 3.11+** - Core language
- **FastAPI** - Modern async web framework
- **SQLAlchemy 2.0** - Async ORM with PostgreSQL
- **Pydantic v2** - Data validation
- **arq** - Redis-based job queue
- **Ollama** - Local LLM for intelligent extraction
- **BeautifulSoup4** - HTML parsing
- **Playwright** - Browser automation for JS-rendered pages

### Frontend
- **React 18** - UI library
- **Vite** - Build tool
- **TypeScript** - Type safety
- **TailwindCSS** - Styling
- **Radix UI** - Accessible components
- **TanStack Query** - Server state management

### Infrastructure
- **PostgreSQL** - Primary database
- **Redis** - Caching and job queue
- **Docker Compose** - Container orchestration

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Node.js 20+ (for frontend development)
- Python 3.11+ (for backend development)

### Development Setup

1. **Clone and enter directory**
   ```bash
   cd dno-crawler
   ```

2. **Start infrastructure services**
   ```bash
   docker compose up -d db redis ollama
   ```

3. **Pull Ollama models**
   ```bash
   docker compose exec ollama ollama pull llama3.2
   docker compose exec ollama ollama pull llava
   ```

4. **Backend setup**
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

5. **Frontend setup** (new terminal)
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

6. **Access the application**
   - Frontend: http://localhost:5173
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

### Full Docker Setup

```bash
# Start everything
docker compose up -d

# View logs
docker compose logs -f backend

# Stop everything
docker compose down
```

## Project Structure

```
dno-crawler/
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI routes and middleware
│   │   ├── core/          # Pydantic models and config
│   │   ├── db/            # SQLAlchemy models and database
│   │   ├── crawler/       # Web crawling logic
│   │   ├── intelligence/  # LLM integration and learning
│   │   └── worker/        # Background job processing
│   ├── tests/             # pytest tests
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── pages/         # Page components
│   │   ├── lib/           # Utilities, API client, auth
│   │   └── hooks/         # Custom React hooks
│   └── package.json
├── docker-compose.yml
└── README.md
```

## API Endpoints

### Public (rate-limited)
- `GET /api/public/search?postal_code=70173` - Search by postal code

### Authenticated
- `POST /api/auth/login` - Login
- `POST /api/auth/register` - Register
- `GET /api/dnos` - List DNOs
- `POST /api/dnos/{id}/crawl` - Trigger crawl

### Admin
- `GET /api/admin/stats` - System statistics
- `GET /api/admin/users` - User management

## Configuration

Environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `OLLAMA_BASE_URL` | Ollama API URL | `http://localhost:11434` |
| `JWT_SECRET` | JWT signing secret | Required in production |
| `CORS_ORIGINS` | Allowed CORS origins | `http://localhost:5173` |

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

## License

MIT License - see [LICENSE](LICENSE) file
