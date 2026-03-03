# Dev/Prod Environment and Deployment Workflow

This document defines the branching strategy, promotion logic, environment configuration, and day-to-day workflow for managing Development and Production versions of DNO Crawler.

## 1. Branching Strategy

Use two long-lived branches:

| Branch | Purpose | Deploys To |
|--------|---------|------------|
| `main` | Production-ready code | Production server via `docker-compose.prod.yml` |
| `dev` | Active development and integration | Local or staging via `docker-compose.yml` |

### Day-to-Day Workflow

1. **All new work starts from `dev`.** Create short-lived feature branches off `dev` when working on larger changes:
   ```bash
   git checkout dev
   git pull origin dev
   git checkout -b feat/improve-crawler-regex
   ```

2. **Small fixes and single-commit changes** can be committed directly to `dev`.

3. **Feature branches merge back into `dev`** via pull request or direct merge:
   ```bash
   git checkout dev
   git merge feat/improve-crawler-regex
   git branch -d feat/improve-crawler-regex
   ```

4. **Production releases** merge `dev` into `main` after passing the Promotion Checklist (see Section 2):
   ```bash
   git checkout main
   git merge dev
   git push origin main
   ```

5. **Hotfixes** for production issues branch from `main`, fix the issue, merge into both `main` and `dev`:
   ```bash
   git checkout main
   git checkout -b hotfix/fix-auth-redirect
   # ... fix and commit ...
   git checkout main
   git merge hotfix/fix-auth-redirect
   git checkout dev
   git merge hotfix/fix-auth-redirect
   git branch -d hotfix/fix-auth-redirect
   ```

### CI Integration

The existing `.github/workflows/ci.yml` runs on pull requests to `main`. Update the trigger to also run on `dev`:

```yaml
on:
  pull_request:
    branches: [main, dev]
  push:
    branches: [dev]
  workflow_dispatch:
```

This ensures all four CI jobs (backend-lint, backend-test, frontend-build, frontend-test) gate both branches.

---

## 2. Promotion Checklist

Before merging `dev` into `main`, every item must pass:

- [ ] **Backend lint clean**: `cd backend && uv run ruff check . && uv run ruff format --check .`
- [ ] **Backend type check**: `cd backend && uv run mypy app`
- [ ] **Backend tests pass**: `cd backend && uv run pytest -x --tb=short`
- [ ] **Frontend lint clean**: `cd frontend && npm run lint`
- [ ] **Frontend build succeeds**: `cd frontend && npm run build`
- [ ] **Frontend tests pass**: `cd frontend && npm test`
- [ ] **CI pipeline green**: All four GitHub Actions jobs pass on the merge commit or PR
- [ ] **Alembic migrations reviewed**: If schema changed, verify migration file is present in `backend/alembic/versions/` and has been tested against a fresh database
- [ ] **No secrets in diff**: Confirm no API keys, passwords, or `.env` values leaked into tracked files
- [ ] **Manual smoke test** (recommended): Run `podman-compose -f docker-compose.prod.yml up -d --build` locally, verify health endpoint responds, frontend loads, and auth flow works

### Automation Suggestion

Add a GitHub Actions workflow that runs on PRs targeting `main` and blocks merge until all checks pass. The existing `ci.yml` already does this for PRs to `main`; ensure branch protection rules require status checks.

---

## 3. Environment Configuration

The project already uses a well-structured `.env` file pattern. This section formalizes it.

### Existing Pattern (Keep As-Is)

| File | Purpose | Git-Tracked |
|------|---------|-------------|
| `.env.example` | Template with placeholder values and documentation | Yes |
| `.env` | Local development overrides (currently dev config) | No (`.gitignore`) |
| `.env.prod` | Production values | No (`.gitignore`) |

Both `docker-compose.yml` and `docker-compose.prod.yml` load from `.env` via `env_file: - .env`. The prod compose also hardcodes critical overrides like `ENVIRONMENT=production` and `USE_ALEMBIC_MIGRATIONS=true` in the `environment` block.

### Recommended Approach: Swap `.env` Per Environment

Since `docker-compose` always reads `.env` by default, the cleanest approach for this project is:

**On the dev machine:**
```bash
# .env contains development values (current state -- no change needed)
podman-compose up -d --build
```

**On the production server:**
```bash
# Copy .env.prod to .env before deploying
cp .env.prod .env
podman-compose -f docker-compose.prod.yml up -d --build
```

Alternatively, use the `--env-file` flag (Compose V2+):
```bash
podman-compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

### Key Variables That Differ Between Environments

| Variable | Dev (`.env`) | Prod (`.env.prod`) |
|----------|-------------|-------------------|
| `ENVIRONMENT` | `development` | `production` |
| `DEBUG` | `true` | `false` |
| `LOG_LEVEL` | `DEBUG` | `INFO` |
| `USE_ALEMBIC_MIGRATIONS` | `false` | `true` |
| `ZITADEL_DOMAIN` | `auth.example.com` (mock mode) or real domain | Real Zitadel domain |
| `ZITADEL_CLIENT_ID` | Dev app client ID | Prod app client ID |
| `VITE_API_URL` | `http://localhost:8000/api/v1` | `/api/v1` (relative, served by nginx) |
| `VITE_ZITADEL_REDIRECT_URI` | `http://localhost:5173/callback` | `https://dno.kylehub.dev/callback` |
| `VITE_ZITADEL_POST_LOGOUT_URI` | `http://localhost:5173` | `https://dno.kylehub.dev` |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | `["https://dno.kylehub.dev"]` |
| `TRUSTED_PROXY_COUNT` | `0` | `2` |

### How `config.py` Handles This

The `Settings` class in `backend/app/core/config.py` uses `pydantic-settings` with `SettingsConfigDict(env_file=".env")`. The `environment` field is a `Literal["development", "staging", "production", "test"]` which drives behavior:

- `settings.is_production` returns `True` when `environment` is `production` or `staging`
- `settings.is_auth_enabled` returns `True` when `ZITADEL_DOMAIN` is not `auth.example.com`
- `settings.debug` controls debug-level behavior

No changes to `config.py` are needed. The existing pattern is sound.

### Frontend Environment Variables

Vite variables (`VITE_*`) are baked at build time. This is already handled correctly:
- Dev compose (`docker-compose.yml`): Reads `VITE_*` from `.env` at runtime (Vite dev server)
- Prod compose (`docker-compose.prod.yml`): Passes `VITE_*` as Docker build `args`, which get embedded during `npm run build`

---

## 4. Dev vs Prod Workflow Table

| Feature | Dev Environment | Prod Environment |
|---------|----------------|-----------------|
| **Branch** | `dev` | `main` |
| **Compose file** | `docker-compose.yml` | `docker-compose.prod.yml` |
| **Env file** | `.env` | `.env.prod` (copied to `.env` on server) |
| **Database** | Local PostgreSQL 16, `create_all()` auto-schema | Local PostgreSQL 16, Alembic migrations |
| **Schema management** | `USE_ALEMBIC_MIGRATIONS=false` | `USE_ALEMBIC_MIGRATIONS=true` |
| **Backend Dockerfile** | `backend/Dockerfile` (with `--reload`) | `backend/Dockerfile.prod` (multi-stage, 2 workers) |
| **Frontend Dockerfile** | `frontend/Dockerfile.dev` (Vite dev server) | `frontend/Dockerfile` (multi-stage, nginx) |
| **Backend hot-reload** | Yes (source mounted as volume) | No (code baked into image) |
| **Frontend hot-reload** | Yes (source mounted as volume) | No (static build served by nginx) |
| **Auth mode** | Mock admin (`ZITADEL_DOMAIN=auth.example.com`) | Zitadel OIDC (real provider) |
| **Debug mode** | `DEBUG=true`, `LOG_LEVEL=DEBUG` | `DEBUG=false`, `LOG_LEVEL=INFO` |
| **Error handling** | Verbose tracebacks, debug logs | Structured JSON logs, no tracebacks |
| **CORS** | `http://localhost:5173` | `https://dno.kylehub.dev` |
| **Proxy setup** | No proxy (`TRUSTED_PROXY_COUNT=0`) | Pangolin + Newt (`TRUSTED_PROXY_COUNT=2`) |
| **Exposed ports** | DB (5432), Redis (6379), Backend (8000), Frontend (5173) | No ports exposed externally; Newt tunnels traffic |
| **Update method** | Continuous commits to `dev` | Merge `dev` into `main` after checklist passes |
| **Deploy command** | `podman-compose up -d --build` | `podman-compose -f docker-compose.prod.yml up -d --build` |

---

## 5. Deployment Procedure

### Dev Deployment (Local Machine)

```bash
cd /home/kyle/CodingProjects/dno-crawler
git checkout dev

# Ensure .env has development values
# (Already the case if following this workflow)

podman-compose up -d --build

# Verify
curl -f http://localhost:8000/api/health
open http://localhost:5173
```

### Prod Deployment (Production Server)

```bash
cd /path/to/dno-crawler
git checkout main
git pull origin main

# Ensure .env.prod values are current, then activate them
cp .env.prod .env

# Run Alembic migration check (if schema changed)
podman-compose up -d db
cd backend
DATABASE_URL="postgresql+asyncpg://dno:<password>@localhost:5432/dno_crawler" \
  uv run alembic upgrade head
cd ..

# Deploy
podman-compose -f docker-compose.prod.yml up -d --build

# Verify
podman-compose -f docker-compose.prod.yml ps
podman logs dno-crawler-backend-prod 2>&1 | tail -20
curl -sf https://dno.kylehub.dev/api/health
```

### Rolling Back

If a production deploy fails:

```bash
git checkout main
git revert HEAD   # or: git reset --hard <last-good-commit>
podman-compose -f docker-compose.prod.yml up -d --build
```

---

## 6. Practical Recommendations

### 6.1 Create the `dev` Branch Now

```bash
git checkout main
git checkout -b dev
git push -u origin dev
```

### 6.2 Update CI Triggers

Edit `.github/workflows/ci.yml` to run on pushes to `dev` and PRs to both branches:

```yaml
on:
  pull_request:
    branches: [main, dev]
  push:
    branches: [dev]
  workflow_dispatch:
```

### 6.3 Add Branch Protection Rules (GitHub)

For **`main`**:
- Require pull request before merging
- Require status checks to pass (all four CI jobs)
- Require branches to be up to date before merging
- Restrict who can push (optional)

For **`dev`**:
- Require status checks to pass (all four CI jobs)
- Allow direct pushes for rapid iteration

### 6.4 Keep `.env.example` Updated

Whenever a new environment variable is added, update `.env.example` with a placeholder and comment. This serves as the single reference for all required configuration.

### 6.5 Never Commit Secrets

The `.gitignore` already excludes `.env` and `.env.*` (except `.env.example`). Verify this remains the case before every commit. The Promotion Checklist includes a secrets audit step.

### 6.6 Database Migrations Workflow

Schema changes require extra care when promoting to production:

1. Develop the model change on `dev`
2. Generate the Alembic migration using the dev compose DB:
   ```bash
   podman-compose up -d db
   cd backend
   DATABASE_URL="postgresql+asyncpg://dno:<pass>@localhost:5432/dno_crawler" \
     uv run alembic revision --autogenerate -m "add new column"
   uv tool run ruff format alembic/versions/<new_file>.py
   ```
3. Test the migration: `uv run alembic upgrade head` then `uv run alembic downgrade -1`
4. Commit the migration file to `dev`
5. When promoting to `main`, the prod entrypoint (`entrypoint.sh`) runs `alembic upgrade head` automatically on container start

### 6.7 Separate Zitadel OIDC Apps

The project already uses separate `ZITADEL_CLIENT_ID` values for dev and prod. This is correct. Each environment should have its own Zitadel application with appropriate redirect URIs:

- Dev: `http://localhost:5173/callback`
- Prod: `https://dno.kylehub.dev/callback`
