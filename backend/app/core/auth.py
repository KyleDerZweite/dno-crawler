"""
JWT validation and auth dependencies for FastAPI.

Features:
- JWKS-based token validation (no network calls per request after caching)
- User model with role extraction
- Dependencies for protected endpoints
- Role-based access control (ADMIN, MEMBER)
"""

import time
from dataclasses import dataclass

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import auth_settings

# Security scheme for Swagger UI
bearer_scheme = HTTPBearer(auto_error=False)

# JWKS cache
_jwks_cache: dict = {}
_jwks_cache_time: float = 0
JWKS_CACHE_TTL = 3600  # 1 hour


@dataclass
class User:
    """Authenticated user extracted from JWT."""

    id: str
    email: str
    name: str
    roles: list[str]

    def has_role(self, role: str) -> bool:
        return role in self.roles

    @property
    def is_admin(self) -> bool:
        # Case-insensitive check for admin role
        return any(role.upper() == "ADMIN" for role in self.roles)

    @property
    def is_maintainer(self) -> bool:
        """Check if user has MAINTAINER role."""
        return any(role.upper() == "MAINTAINER" for role in self.roles)

    @property
    def can_manage_flags(self) -> bool:
        """Check if user can remove flags (Maintainer or Admin)."""
        return self.is_admin or self.is_maintainer



async def fetch_jwks() -> dict:
    """Fetch JWKS from Zitadel (cached)."""
    global _jwks_cache, _jwks_cache_time

    now = time.time()
    if _jwks_cache and (now - _jwks_cache_time) < JWKS_CACHE_TTL:
        return _jwks_cache

    async with httpx.AsyncClient() as client:
        response = await client.get(auth_settings.jwks_url)
        response.raise_for_status()
        _jwks_cache = response.json()
        _jwks_cache_time = now
        return _jwks_cache


def get_signing_key(token: str, jwks: dict) -> str:
    """Get the signing key for the token from JWKS."""
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")

    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return jwt.algorithms.RSAAlgorithm.from_jwk(key)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unable to find signing key",
    )


def extract_roles(claims: dict) -> list[str]:
    """Extract role keys from Zitadel token claims."""
    import structlog
    logger = structlog.get_logger()

    roles_obj = claims.get("urn:zitadel:iam:org:project:roles", {})
    logger.info("Role extraction", roles_obj=roles_obj, claim_keys=list(claims.keys()))

    if isinstance(roles_obj, dict):
        roles = list(roles_obj.keys())
        logger.info("Extracted roles", roles=roles)
        return roles
    return []


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    """
    Dependency to get the current authenticated user.

    usage:
        @router.get("/protected")
        async def protected(user: User = Depends(get_current_user)):
            return {"user": user.email}
    """
    from .config import settings

    # Handle Mock Admin if auth is disabled or pointing to example.com
    if not settings.is_auth_enabled:
        return User(
            id="mock-admin-id",
            email="admin@dno-crawler.local",
            name="Mock Admin",
            roles=["ADMIN", "MEMBER"],
        )

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        # Fetch JWKS and get signing key
        jwks = await fetch_jwks()
        signing_key = get_signing_key(token, jwks)

        # Decode and verify token
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            issuer=auth_settings.issuer,
            options={"verify_aud": False},  # Zitadel uses project-based audience
            leeway=30,  # Allow 30 seconds clock skew
        )

        # Extract roles from token claims
        roles = extract_roles(claims)
        email = claims.get("email", "")
        name = claims.get("name", claims.get("preferred_username", ""))

        # If email or roles missing from access token, fetch from userinfo endpoint
        if not email or not roles:
            userinfo_url = f"{auth_settings.issuer}/oidc/v1/userinfo"
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    userinfo_url,
                    headers={"Authorization": f"Bearer {token}"}
                )
                if response.status_code == 200:
                    userinfo = response.json()
                    if not roles:
                        roles = extract_roles(userinfo)
                    if not email:
                        email = userinfo.get("email", "")
                    if not name:
                        name = userinfo.get("name", userinfo.get("preferred_username", ""))

        return User(
            id=claims.get("sub", ""),
            email=email,
            name=name,
            roles=roles,
        )

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e!s}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {e!s}",
        )


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User | None:
    """
    Dependency to get the current user if authenticated, or None if not.

    usage:
        @router.get("/public-or-private")
        async def endpoint(user: Optional[User] = Depends(get_optional_user)):
            if user:
                return {"personalized": True}
            return {"personalized": False}
    """
    from .config import settings

    if not settings.is_auth_enabled:
        return User(
            id="mock-admin-id",
            email="admin@dno-crawler.local",
            name="Mock Admin",
            roles=["ADMIN", "MEMBER"],
        )

    if not credentials:
        return None

    token = credentials.credentials

    try:
        jwks = await fetch_jwks()
        signing_key = get_signing_key(token, jwks)

        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            issuer=auth_settings.issuer,
            options={"verify_aud": False},
            leeway=30,  # Allow 30 seconds clock skew
        )

        return User(
            id=claims.get("sub", ""),
            email=claims.get("email", ""),
            name=claims.get("name", claims.get("preferred_username", "")),
            roles=extract_roles(claims),
        )
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """
    Dependency that requires the user to have ADMIN role.

    Usage:
        @router.delete("/resource/{id}")
        async def delete_resource(id: str, user: User = Depends(require_admin)):
            ...
    """
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


async def require_member(user: User = Depends(get_current_user)) -> User:
    """
    Dependency that requires the user to have at least MEMBER role.

    Usage:
        @router.post("/resource")
        async def create_resource(user: User = Depends(require_member)):
            ...
    """
    if not user.has_role("MEMBER") and not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Member access required",
        )
    return user


async def require_maintainer_or_admin(user: User = Depends(get_current_user)) -> User:
    """
    Dependency that requires MAINTAINER or ADMIN role.

    Used for operations like removing data flags.

    Usage:
        @router.delete("/data/{id}/flag")
        async def remove_flag(user: User = Depends(require_maintainer_or_admin)):
            ...
    """
    if not user.can_manage_flags:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Maintainer or Admin access required",
        )
    return user



def require_role(role: str):
    """
    Factory for creating role-specific dependencies.

    Usage:
        @router.get("/managers-only")
        async def managers_only(user: User = Depends(require_role("MANAGER"))):
            ...
    """

    async def dependency(user: User = Depends(get_current_user)) -> User:
        if not user.has_role(role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{role} role required",
            )
        return user

    return dependency
