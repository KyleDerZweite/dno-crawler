# Core Module

Configuration, authentication, and shared models for the DNO Crawler backend.

## Files

| File | Purpose |
|------|---------|
| `config.py` | Pydantic Settings for environment configuration |
| `auth.py` | JWT validation with JWKS, user dependencies |
| `models.py` | Shared Pydantic schemas (JobStatus, VerificationStatus, etc.) |
| `exceptions.py` | Custom exception classes |

## Authentication

The auth module provides a modular OIDC implementation supporting:

1. **Zitadel OIDC**: Production authentication with JWKS validation
2. **Mock Mode**: Development mode with a mock admin user when `ZITADEL_DOMAIN=auth.example.com`

### Dependencies

```python
from app.core.auth import get_current_user, require_admin, User

# Any authenticated user
@router.get("/profile")
async def get_profile(user: User = Depends(get_current_user)):
    return {"email": user.email, "roles": user.roles}

# Admin only
@router.delete("/users/{user_id}")
async def delete_user(user_id: str, user: User = Depends(require_admin)):
    ...

# Optional authentication (returns None if no token)
@router.get("/public")
async def public_endpoint(user: User | None = Depends(get_optional_user)):
    ...
```

## Configuration

Environment variables are loaded via Pydantic Settings:

```python
from app.core.config import settings

# Access configuration
db_url = settings.database_url
ai_model = settings.ai_model
```

### Key Settings

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL async connection string |
| `REDIS_URL` | Yes | Redis connection for job queue |
| `ZITADEL_DOMAIN` | No | OIDC domain (use `auth.example.com` for mock mode) |
| `AI_API_URL` | No | OpenAI-compatible endpoint |
| `AI_API_KEY` | No | API key (omit for local Ollama) |
| `AI_MODEL` | No | Model identifier |
| `STORAGE_PATH` | No | File storage path (default: `/data`) |

## Shared Models

Common enums and schemas used across the application:

```python
from app.core.models import JobStatus, VerificationStatus

# Job states
JobStatus.PENDING
JobStatus.RUNNING
JobStatus.COMPLETED
JobStatus.FAILED

# Data verification states
VerificationStatus.UNVERIFIED
VerificationStatus.VERIFIED
VerificationStatus.FLAGGED
```
