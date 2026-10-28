# Deployment

> Documentation note: The running deployment configuration and infrastructure code are authoritative. This document captures stable deployment operations.

Production deployment uses `docker-compose.prod.yml` with `podman-compose` on a rootless Podman host. Pangolin handles TLS termination and reverse proxying; Newt tunnels traffic from Pangolin to the local stack.

## Release Workflow (Dev to Prod)

Use two long-lived branches:

| Branch | Purpose | Environment |
|--------|---------|-------------|
| `dev` | Active development and integration | Local/staging (`docker-compose.yml`) |
| `main` | Production-ready code only | Production (`docker-compose.prod.yml`) |

### Standard flow

1. Implement and validate changes on `dev`.
2. Open PR from `dev` to `main` for production release.
3. Require CI checks to pass before merge.
4. Deploy from `main` on the production host.

### CI and branch protection baseline

- CI workflow (`.github/workflows/ci.yml`) runs on pull requests to both `main` and `dev`.
- `main` branch protection should require:
  - Pull request before merge
  - Required checks: Backend Lint & Typecheck, Backend Tests, Frontend Build & Lint, Frontend Tests
  - Branch up-to-date before merge

## Promotion Checklist

Before merging `dev` into `main`, install locked dependencies with `cd backend && uv sync --locked --extra dev` and `cd frontend && pnpm install --frozen-lockfile`, then validate:

- `cd backend && uv run ruff check . && uv run ruff format --check .`
- `cd backend && uv run mypy app`
- `cd backend && uv run pytest -x --tb=short`
- `cd frontend && pnpm run lint`
- `cd frontend && pnpm run build`
- `cd frontend && pnpm test`
- CI pipeline green on PR
- Migration file present and reviewed if schema changed (`backend/alembic/versions/`)
- No secrets in diff (`.env`, API keys, credentials)

## Dependency tooling

Use Python 3.11 with uv 0.11.16 and `backend/uv.lock`. Frontend development, CI and build containers use Node 22 and pnpm 10.34.9 from `frontend/package.json`. Both lockfiles include the security refresh verified on 2026-10-28. Subsequent installs must preserve `pnpm-lock.yaml` with `--frozen-lockfile`. Both lockfiles belong in version control. Only esbuild is allowed to run dependency build scripts. The development backend keeps its virtual environment at `/opt/venv`, outside the read-only source mount.

Dependabot uses the `uv` ecosystem for the backend and the `npm` ecosystem for pnpm. Version-update PRs target `dev`, preserving promotion to `main`. The pnpm 10 lock format remains compatible with GitHub dependency scanning. This configuration does not enable repository vulnerability alerts or change branch protection.

### Security refresh compatibility contract

The 2026-10-28 maintenance scope preserves API routes and response shapes, deterministic document parsing, OIDC verification, frontend routes and existing components. Dependency changes do not change the split-worker responsibilities, database schema or promotion policy. The dependency review selected updates and regression coverage within these existing boundaries.

FastAPI 0.162.0 supports the audited Starlette 1.10.0. [FastAPI's release notes](https://fastapi.tiangolo.com/release-notes/) describe Starlette 1 support and the new strict JSON Content-Type default. The application explicitly keeps `strict_content_type=False` to preserve clients that omit Content-Type. Its database dependency must propagate `RequestValidationError` to the existing 422 handler, rather than converting validation into HTTP 500. The search regression compares explicit and omitted Content-Type on invalid coordinates.

Vitest 5.0.5 replaces Vitest 3 and removes the vulnerable Tinypool dependency. The existing jsdom setup, test discovery and CLI remain in use. [Vitest's migration guide](https://vitest.dev/guide/migration/) requires Node >=22.12 and Vite >=6.4, which this project's Node 22 and Vite 7 satisfy. The existing React Hooks lint plugin remains pinned to 7.0.1. The 7.1 recommended preset changes unrelated effect rules; this maintenance does not select that lint-policy change. No audit overrides, ignored advisories or rule suppressions were added.

ApexCharts 5.16 requires explicit `ApexAxisChartSeries` type imports in the three existing chart components. Chart data, options and layout remain unchanged. Backend updates include cryptography 50.0.2 and PyArrow 26.0.0. Regression tests exercise RSA/JWKS validation and rejected claims, Fernet tampering, actual PDF tariff extraction, multiline HTML HLZF windows and the shipped Parquet reader. OpenAI 2.14.0, OpenRouter 0.1.1, pandas 2.3.3 and PyMuPDF 1.26.7 retain their existing versions to avoid unrelated provider and parser API migrations.

The disposable migrated runtime exposed an older schema mismatch: the initial migration stores HLZF seasons as TEXT, while the current ORM declares JSON. A shared decoder now reads JSON arrays, JSON text, JSON null and older time-window strings. The ORM result adapter and raw-SQL detail endpoint use that decoder; writes keep the existing JSON format. Neither migrations nor stored captures change. Regression coverage checks public search and protected detail against fresh JSON columns and both TEXT representations, and rejects unreadable content. On narrow layouts, the shared search mode buttons wrap, the existing DNO context navigation precedes the content, and chart controls wrap. Wide layouts retain the existing sidebars.

### Local verification on 2026-10-28

This is implementation evidence, not deployment or owner acceptance. The checkout remains `main` at base/HEAD `88f0746143e5e74a9b798ae97e8a7a657b4cdee0`, with an empty staging area. The original owner's changes remain part of the working diff. The pre-existing BACKLOG.md bytes retain SHA-256 `2e098cb0ebe9731758b46fbbfcf2beecba034d17d4390190861e857cc376ac42`. Entry fingerprints cover 307 tracked/untracked files; tracked captures, paused modules and personal AGENTS.md rules were preserved. Disposable PostgreSQL and Redis storage did not mount repository data directories.

The final backend lock has SHA-256 `fbae4f22895d74802281914c8e379a7065d0ed9670be1bea8c7519bcf06c8118`; the frontend lock has SHA-256 `b6327dbf252cbce8e7280fd19e3ad5fa755196de4a0968a432506756611a055d`. `pnpm audit --json` reports zero findings across 418 dependencies, down from 137 findings including 3 critical and 58 high. `uv export --locked --extra dev --no-hashes --no-emit-project` followed by `uvx --python 3.11 pip-audit -r <export> --disable-pip --no-deps -f json` reports zero known findings across 115 resolved Python packages, down from 274 findings in 25 packages. The export includes every locked dependency; `--no-deps` prevents a second dependency resolution. Neither audit excludes advisories.

| Check | Observed result |
|-------|-----------------|
| `uv lock --check`, `uv sync --locked --extra dev`, offline resync | Passed on Python 3.11.17 with uv 0.11.16 |
| Locked `ruff check .`, `ruff format --check .`, `mypy app` | Passed; mypy retains the exclusions documented in AGENTS.md |
| Locked `pytest -x --tb=short` | 45 passed, zero skips, including all original 31 tests, against disposable PostgreSQL 16.11 and Redis 7.4.7 |
| Frozen/offline pnpm install, `pnpm run lint`, `pnpm run build`, `pnpm test` | Passed on Node 22.23.4 and pnpm 10.34.9; 5 tests across 3 files |
| Deliberately mismatched manifest in a temporary directory | Rejected with `ERR_PNPM_OUTDATED_LOCKFILE` |
| Production and development frontend/backend Dockerfiles | All four built and ran; production backend used Docker image format to retain Podman's HEALTHCHECK |
| Current backend runtime source hashes | Matched the checkout in both containers |
| Runtime Python | Both backend images used Python 3.11.18 |
| Migrations and runtime probes | Applied through `a3b9c7d1e5f2`; both health/readiness HTTP 200 with database and Redis connected; production container health `healthy` |
| Authentication and unavailable Redis | Production anonymous `/auth/me` returned 401; development mock returned 200; production mock-auth startup failed with exit 3; Redis outage returned `degraded`, followed by `ready` after restart |
| Rendered production assets and development server | Chromium 156.0.8078.4 passed at 390 and 1440 pixels: visible search modes, invalid-input disabled state, synthetic 429/empty-state recovery, real local search/data preview, nested detail route, three charts and toggles, dialog Escape; no page errors or API 5xx |

The rendered journeys used synthetic records in the migrated disposable database and the existing mock-admin mode. Production assets used a local test proxy to the development API because the deployment routes `/api` outside nginx. The 429 and empty responses were UI fixtures; successful search, detail data and charts used real PostgreSQL/Redis-backed API responses. Existing Google Fonts requests were observed. Live Zitadel sign-in, external AI providers, real crawling, touch/assistive-technology testing and owner acceptance remain unverified. The original address-search smoke tests allow upstream error responses, so their passing result does not establish live VNB service availability.

Two existing React Refresh lint warnings and the large-bundle build warning remain. Initial failed checks identified the HLZF storage mismatch, validation-to-500 conversion and missing ApexCharts type imports; regression checks passed after the fixes. Registry timeouts required reduced pnpm concurrency for the refresh. An initial build-cache mount failed under SELinux; a separate disposable uv cache allowed backend builds without changing the shared cache. No production host, actual website, branch policy, CI trigger or required-check name changed. No commit, push, PR or deployment occurred. Hosted CI and independent review remain for the integrating owner.

All six disposable runtime containers, their network and the separate build cache were removed after verification. Local build images and temporary evidence reports remain available for the integrating owner's review.

## Environment Strategy

### Environment files

| File | Purpose | Tracked |
|------|---------|---------|
| `.env.example` | Canonical template and variable documentation | Yes |
| `.env` | Active environment values used by compose | No |
| `.env.prod` | Production values source | No |

Recommended practice:

- Dev machines: keep development settings in `.env`.
- Production host: copy `.env.prod` to `.env` immediately before deploy.

```bash
cp .env.prod .env
podman-compose -f docker-compose.prod.yml up -d --build
```

If supported by your compose binary, `--env-file .env.prod` is an alternative.

### Required production values

| Variable | Required production value |
|----------|---------------------------|
| `ENVIRONMENT` | `production` |
| `USE_ALEMBIC_MIGRATIONS` | `true` |
| `DEBUG` | `false` |
| `LOG_LEVEL` | `INFO` |
| `ZITADEL_DOMAIN` | Real Zitadel domain (not `auth.example.com`) |
| `TRUSTED_PROXY_COUNT` | `2` (Pangolin + Newt) |
| `VITE_API_URL` | `/api/v1` |
| `CORS_ORIGINS` | `["https://<your-domain>"]` |

## Prerequisites

### 1. Podman short-name resolution

Rootless Podman on Ubuntu does not resolve unqualified image names by default. Without this, `postgres:16-alpine` fails to pull with:

```
short-name "postgres:16-alpine" did not resolve to an alias and no unqualified-search registries are defined
```

Fix (one-time, on the host):

```bash
sudo sh -c 'echo unqualified-search-registries=["docker.io"] >> /etc/containers/registries.conf'
```

Verify:

```bash
grep "unqualified-search" /etc/containers/registries.conf
# Expected: unqualified-search-registries=["docker.io"]
```

### 2. Seed parquet file

`data/seed-data/dnos_enriched_with_stats.parquet` must exist before starting. It is tracked in git. If missing, regenerate via stages 5+6 in `docs/knowledge/SEEDING.md`.

### 3. `.env` file

Copy from `.env.example` and fill in all values. See `.env.example` for field descriptions. Key production values:

| Variable | Notes |
|----------|-------|
| `POSTGRES_PASSWORD` | Strong random password |
| `USE_ALEMBIC_MIGRATIONS` | Must be `true` in production |
| `ENVIRONMENT` | Must be `production` |
| `ZITADEL_DOMAIN` | Your Zitadel instance domain |
| `ZITADEL_CLIENT_ID` | From Zitadel OIDC app |
| `VITE_ZITADEL_AUTHORITY` | `https://<ZITADEL_DOMAIN>` |
| `VITE_ZITADEL_REDIRECT_URI` | `https://<your-domain>/callback` |
| `CORS_ORIGINS` | `["https://<your-domain>"]` |
| `PANGOLIN_ENDPOINT` | Pangolin control plane URL |
| `NEWT_ID` / `NEWT_SECRET` | From Pangolin site config |
| `TRUSTED_PROXY_COUNT` | `2` (Pangolin + Newt) |

### 4. Pangolin site

Create a Pangolin site with two resources:
- `/api/*` → `backend:8000`
- `/*` → `frontend:80`

Create a Zitadel OIDC app with redirect URI `https://<your-domain>/callback`.

### 5. Data directories

Ensure data directories exist (they are created via `.gitkeep` files):

```bash
ls data/postgres data/redis data/downloads
```

If wiping for a fresh deploy, the directories must still exist (podman volume mounts require them):

```bash
mkdir -p data/postgres data/redis data/downloads
```

Note: `data/postgres` and `data/redis` are owned by root when created by a running container. Wiping them requires `sudo rm -rf data/postgres data/redis`.

## Deploy

```bash
podman-compose -f docker-compose.prod.yml up -d --build
```

## Environment-Specific Commands

### Dev deploy

```bash
git checkout dev
podman-compose up -d --build
```

### Prod deploy

```bash
git checkout main
git pull origin main
cp .env.prod .env
podman-compose -f docker-compose.prod.yml up -d --build
```

### Rollback

Use `git revert` on `main` and redeploy. If a migration caused the regression, run the matching Alembic downgrade before restart.

### Startup order

1. `db` and `redis` start, pass healthchecks
2. `backend` entrypoint runs `alembic upgrade head` (creates/migrates all tables), then uvicorn starts
3. `worker-crawl` starts, calls `init_db()` with `USE_ALEMBIC_MIGRATIONS=true` (skips `create_all()`), then seeds DNOs from parquet
4. `worker-extract` starts, calls `init_db()` with `USE_ALEMBIC_MIGRATIONS=true` (skips `create_all()`)
5. `frontend` builds and serves via nginx on port 80
6. `newt` connects to Pangolin and exposes the stack

### Verify startup

```bash
# All services running
podman-compose -f docker-compose.prod.yml ps

# Backend healthy and migrations applied
podman logs dno-crawler-backend-prod 2>&1 | grep -E "migration|initialized|Starting"

# Seeding complete
podman logs dno-crawler-worker-crawl-prod 2>&1 | grep -E "Seeding|inserted|updated"

# Frontend serving
curl -sf http://localhost:80 | head -5
```

## Alembic migrations

The initial migration (`backend/alembic/versions/`) was generated by:

1. Starting a fresh postgres via dev compose (which exposes port 5432 to the host)
2. Running `alembic revision --autogenerate -m "initial schema"` against the empty DB
3. Formatting the output with `uv tool run ruff format`

**Rootless Podman cannot reach container IPs from the host.** The prod compose does not expose db/redis ports. Always use the dev compose (`docker-compose.yml`) when running local alembic commands.

For future schema changes:

```bash
# Start dev db
podman-compose up -d db

# Generate migration
cd backend
DATABASE_URL="postgresql+asyncpg://<user>:<pass>@localhost:5432/dno_crawler" \
  uv run alembic revision --autogenerate -m "description"

# Format (ruff is not on PATH, use uv tool)
uv tool run ruff format alembic/versions/<rev>_description.py

# Stop dev db
podman-compose down
```

The `alembic.ini` post-write hook calls `ruff` as a bare executable which is not on PATH outside the venv. The hook fails but the file is generated. Always manually format with `uv tool run ruff format` after generation.

## Teardown / reset

```bash
# Stop all services
podman-compose -f docker-compose.prod.yml down

# Wipe persistent data (requires sudo -- podman rootless creates root-owned files)
sudo rm -rf data/postgres data/redis

# Recreate empty directories
mkdir -p data/postgres data/redis
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `short-name did not resolve` on image pull | `unqualified-search-registries` not set | See Prerequisites §1 |
| Backend fails with `alembic upgrade head` error | No migration files in `alembic/versions/` | Generate initial migration (see above) |
| `alembic: not found` in entrypoint | Host `.venv` copied into image, overwriting container-built venv with host-path shebangs | Ensure `.venv/` is in `backend/.dockerignore`; remove cached images and rebuild |
| `alembic/versions/` excluded from image | `.dockerignore` blocked migration files | Remove `alembic/versions/` from `.dockerignore`; only exclude `.venv/` |
| `gin_trgm_ops does not exist` in migration | `pg_trgm` extension not created before migration runs | Add `op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")` at top of `upgrade()` in initial migration |
| `relation already exists` during migration | Workers ran `create_all()` before backend finished `alembic upgrade head` | Workers must depend on `backend: service_healthy`; set `USE_ALEMBIC_MIGRATIONS=true` on workers so they skip `create_all()` |
| Frontend fails with `privileged port 80` | Rootless Podman cannot bind ports < 1024 | Remove host port binding from frontend -- Newt reaches `frontend:80` via internal network; no host binding needed |
| `dno.kylehub.dev` returns HTTP 526 | Pangolin site not yet configured | Create site + resources in Pangolin |
| Seeding skipped with "No seed data file found" | Parquet missing from `data/seed-data/` | Regenerate via SEEDING.md stages 5+6 |
| `ai_encryption_no_key` critical log on startup | `AI_ENCRYPTION_KEY` or `SESSION_SECRET` not set | Add either variable to `.env`; without it, AI provider credentials stored in DB are not encrypted |
| API returns 503 on protected routes in production | Auth still in mock mode (`ZITADEL_DOMAIN=auth.example.com`) | Set real `ZITADEL_DOMAIN`; production startup should fail-fast if auth is disabled |
