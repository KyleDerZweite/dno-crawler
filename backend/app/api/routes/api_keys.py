"""
Admin CRUD routes for API key management.

All endpoints require ADMIN role.
"""

import hashlib
import secrets
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import User, invalidate_api_key_cache, require_admin
from app.db.database import get_db
from app.db.models import APIKeyModel

logger = structlog.get_logger()

router = APIRouter()


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------


class APIKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    roles: list[str] = Field(..., min_length=1)


class APIKeyCreateResponse(BaseModel):
    id: int
    name: str
    key: str  # Plaintext key, shown once
    key_prefix: str
    roles: list[str]


class APIKeyInfo(BaseModel):
    id: int
    name: str
    key_prefix: str
    roles: list[str]
    is_active: bool
    request_count: int
    last_used_at: datetime | None
    created_at: datetime
    created_by: str


class APIKeyListResponse(BaseModel):
    keys: list[APIKeyInfo]


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------


@router.get("", response_model=APIKeyListResponse)
async def list_api_keys(
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all API keys (metadata only, never the secret)."""
    result = await db.execute(
        select(APIKeyModel).order_by(APIKeyModel.created_at.desc())
    )
    keys = result.scalars().all()

    return APIKeyListResponse(
        keys=[
            APIKeyInfo(
                id=k.id,
                name=k.name,
                key_prefix=k.key_prefix,
                roles=k.roles,
                is_active=k.is_active,
                request_count=k.request_count,
                last_used_at=k.last_used_at,
                created_at=k.created_at,
                created_by=k.created_by,
            )
            for k in keys
        ]
    )


@router.post("", response_model=APIKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    request: APIKeyCreateRequest,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new API key. Returns the plaintext key ONCE."""
    allowed_roles = {"ADMIN", "MEMBER", "MAINTAINER"}
    for role in request.roles:
        if role.upper() not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {role}. Allowed: {', '.join(sorted(allowed_roles))}",
            )

    # Generate key
    raw_key = "dno_" + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:12]

    api_key = APIKeyModel(
        name=request.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        roles=[r.upper() for r in request.roles],
        created_by=user.id,
    )
    db.add(api_key)
    await db.flush()

    logger.info(
        "API key created",
        key_id=api_key.id,
        key_name=request.name,
        created_by=user.id,
    )

    await db.commit()

    return APIKeyCreateResponse(
        id=api_key.id,
        name=api_key.name,
        key=raw_key,
        key_prefix=key_prefix,
        roles=api_key.roles,
    )


@router.delete("/{key_id}")
async def delete_api_key(
    key_id: int,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete an API key and invalidate its cache entry."""
    result = await db.execute(
        select(APIKeyModel).where(APIKeyModel.id == key_id)
    )
    api_key = result.scalar_one_or_none()

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    # Invalidate cache before deleting
    invalidate_api_key_cache(api_key.key_hash)

    await db.delete(api_key)
    await db.commit()

    logger.info(
        "API key deleted",
        key_id=key_id,
        key_name=api_key.name,
        deleted_by=user.id,
    )

    return {"message": f"API key '{api_key.name}' deleted"}
