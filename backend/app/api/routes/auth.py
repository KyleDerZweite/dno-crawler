"""
Authentication routes - minimal version for Zitadel.

Most auth is handled by Zitadel externally. This module only provides:
- /me endpoint for getting current user info from token
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.auth import User as AuthUser
from app.core.auth import get_current_user

router = APIRouter()


class UserInfoResponse(BaseModel):
    """User info response from Zitadel token."""
    id: str
    email: str
    name: str
    roles: list[str]
    is_admin: bool


@router.get("/me")
async def get_current_user_info(
    current_user: AuthUser = Depends(get_current_user),
) -> UserInfoResponse:
    """Get current user information from Zitadel token."""
    return UserInfoResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        roles=current_user.roles,
        is_admin=current_user.is_admin,
    )
