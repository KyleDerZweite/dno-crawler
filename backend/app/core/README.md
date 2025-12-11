# FastAPI Auth Template

Token validation and role-based access control for FastAPI backends.

## Files

| File | Purpose |
|------|---------|
| `auth.py` | JWT validation with JWKS, dependencies for protected endpoints |
| `config.py` | Zitadel configuration from environment |

## Installation

```bash
pip install pyjwt[crypto] httpx
```

## Setup

1. Copy files to your `app/core/` or `app/auth/` directory
2. Add environment variables:

```
ZITADEL_DOMAIN=auth.kylehub.dev
```

3. Use dependencies on protected endpoints

## Usage

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
```
