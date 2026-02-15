"""
JWT validation and auth dependencies for FastAPI.

Features:
- JWKS-based token validation (no network calls per request after caching)
- User model with role extraction
- Dependencies for protected endpoints
- Role-based access control (ADMIN, MEMBER)
"""

import asyncio
import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass

import httpx
import jwt
import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import auth_settings

_auth_logger = structlog.get_logger()

# Security scheme for Swagger UI
bearer_scheme = HTTPBearer(auto_error=False)

# JWKS cache
_jwks_cache: dict = {}
_jwks_cache_time: float = 0
_jwks_lock = asyncio.Lock()
JWKS_CACHE_TTL = 3600  # 1 hour

# Userinfo cache: avoids HTTP call to Zitadel userinfo on every request.
# Keyed by truncated SHA-256 of the access token.
_userinfo_cache: OrderedDict[str, tuple[dict, float]] = OrderedDict()
USERINFO_CACHE_TTL = 300  # 5 minutes
USERINFO_CACHE_MAX_SIZE = 500
USERINFO_HTTP_TIMEOUT = 5.0
USERINFO_RETRY_DELAY = 0.3


# API key cache: avoids DB lookup on every request for machine API keys.
# Keyed by full SHA-256 hash of the API key. Values are (User, timestamp) tuples.
_apikey_cache: OrderedDict[str, tuple] = OrderedDict()
APIKEY_CACHE_TTL = 300  # 5 minutes
APIKEY_CACHE_MAX_SIZE = 200


def invalidate_api_key_cache(key_hash: str) -> None:
    """Remove a specific API key from the auth cache."""
    _apikey_cache.pop(key_hash, None)


async def _authenticate_api_key(token: str) -> "User":
    """Authenticate a request using a dno_ prefixed API key."""
    from datetime import UTC, datetime

    from sqlalchemy import select

    from app.db.database import async_session_maker
    from app.db.models import APIKeyModel

    key_hash = hashlib.sha256(token.encode()).hexdigest()

    # Check cache
    entry = _apikey_cache.get(key_hash)
    if entry is not None:
        user, cached_at = entry
        if time.time() - cached_at <= APIKEY_CACHE_TTL:
            _apikey_cache.move_to_end(key_hash)
            return user
        _apikey_cache.pop(key_hash, None)

    # DB lookup (own session, not request-scoped)
    async with async_session_maker() as session:
        result = await session.execute(
            select(APIKeyModel).where(
                APIKeyModel.key_hash == key_hash,
                APIKeyModel.is_active.is_(True),
            )
        )
        api_key = result.scalar_one_or_none()

        if api_key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or inactive API key",
            )

        user = User(
            id=f"apikey:{api_key.id}",
            email="",
            name=api_key.name,
            roles=api_key.roles,
        )

        # Update usage metrics
        api_key.request_count = api_key.request_count + 1
        api_key.last_used_at = datetime.now(UTC)
        await session.commit()

    # Cache the user
    _apikey_cache[key_hash] = (user, time.time())
    _apikey_cache.move_to_end(key_hash)
    while len(_apikey_cache) > APIKEY_CACHE_MAX_SIZE:
        _apikey_cache.popitem(last=False)

    return user


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:16]


def _get_cached_userinfo(token: str) -> dict | None:
    """Return cached userinfo dict if present and not expired."""
    key = _token_hash(token)
    entry = _userinfo_cache.get(key)
    if entry is None:
        return None
    userinfo, cached_at = entry
    if time.time() - cached_at > USERINFO_CACHE_TTL:
        _userinfo_cache.pop(key, None)
        return None
    _userinfo_cache.move_to_end(key)
    return userinfo


def _set_cached_userinfo(token: str, userinfo: dict) -> None:
    """Store userinfo in the cache, evicting oldest entries if needed."""
    key = _token_hash(token)
    _userinfo_cache[key] = (userinfo, time.time())
    _userinfo_cache.move_to_end(key)
    while len(_userinfo_cache) > USERINFO_CACHE_MAX_SIZE:
        _userinfo_cache.popitem(last=False)


async def _fetch_userinfo(token: str) -> dict | None:
    """Fetch userinfo from Zitadel with retry for transient failures."""
    userinfo_url = f"{auth_settings.issuer}/oidc/v1/userinfo"
    async with httpx.AsyncClient(timeout=USERINFO_HTTP_TIMEOUT) as client:
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response = await client.get(
                    userinfo_url, headers={"Authorization": f"Bearer {token}"}
                )
                if response.status_code == 200:
                    userinfo = response.json()
                    _set_cached_userinfo(token, userinfo)
                    return userinfo
                _auth_logger.warning(
                    "Userinfo request failed",
                    status_code=response.status_code,
                    attempt=attempt + 1,
                )
                return None
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                last_error = exc
                if attempt == 0:
                    _auth_logger.debug(
                        "Userinfo connect error, retrying",
                        error=str(exc),
                    )
                    await asyncio.sleep(USERINFO_RETRY_DELAY)
                    continue
        _auth_logger.warning("Userinfo unavailable after retries", error=str(last_error))
        return None


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

    @property
    def is_service_account(self) -> bool:
        """Check if this user represents an API key service account."""
        return self.id.startswith("apikey:")


async def fetch_jwks() -> dict:
    """Fetch JWKS from Zitadel (cached, with lock to prevent thundering herd)."""
    global _jwks_cache, _jwks_cache_time

    now = time.time()
    if _jwks_cache and (now - _jwks_cache_time) < JWKS_CACHE_TTL:
        return _jwks_cache

    async with _jwks_lock:
        # Double-check after acquiring lock (another coroutine may have refreshed)
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
    roles_obj = claims.get("urn:zitadel:iam:org:project:roles", {})
    _auth_logger.debug("Role extraction", roles_obj=roles_obj, claim_keys=list(claims.keys()))

    if isinstance(roles_obj, dict):
        roles = list(roles_obj.keys())
        _auth_logger.debug("Extracted roles", roles=roles)
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
        if settings.is_production:
            _auth_logger.critical(
                "AUTH DISABLED IN PRODUCTION! "
                "Set ZITADEL_DOMAIN to a valid domain. "
                "Rejecting all requests until auth is configured."
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication is not configured. Service unavailable.",
            )
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

    # API key authentication (dno_ prefix)
    if token.startswith("dno_"):
        return await _authenticate_api_key(token)

    try:
        # Fetch JWKS and get signing key
        jwks = await fetch_jwks()
        signing_key = get_signing_key(token, jwks)

        # Decode and verify token
        # Enable audience verification when ZITADEL_CLIENT_ID is configured
        jwt_options = {"verify_aud": bool(settings.zitadel_client_id)}
        decode_kwargs: dict = {
            "algorithms": ["RS256"],
            "issuer": auth_settings.issuer,
            "options": jwt_options,
            "leeway": 30,  # Allow 30 seconds clock skew
        }
        if settings.zitadel_client_id:
            decode_kwargs["audience"] = settings.zitadel_client_id

        claims = jwt.decode(token, signing_key, **decode_kwargs)

        # Extract roles from token claims
        roles = extract_roles(claims)
        email = claims.get("email", "")
        name = claims.get("name", claims.get("preferred_username", ""))

        # If email or roles missing from access token, fetch from userinfo endpoint
        if not email or not roles:
            # Check cache first to avoid HTTP call
            userinfo = _get_cached_userinfo(token)
            if userinfo is None:
                userinfo = await _fetch_userinfo(token)
            if userinfo:
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
        ) from None
    except jwt.InvalidTokenError as e:
        _auth_logger.warning("Invalid token", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from e
    except Exception as e:
        _auth_logger.error("Authentication failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
        ) from e


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
        if settings.is_production:
            _auth_logger.critical(
                "AUTH DISABLED IN PRODUCTION! Set ZITADEL_DOMAIN to a valid domain."
            )
            return None
        return User(
            id="mock-admin-id",
            email="admin@dno-crawler.local",
            name="Mock Admin",
            roles=["ADMIN", "MEMBER"],
        )

    if not credentials:
        return None

    token = credentials.credentials

    # API key authentication (dno_ prefix)
    if token.startswith("dno_"):
        try:
            return await _authenticate_api_key(token)
        except HTTPException:
            return None

    try:
        jwks = await fetch_jwks()
        signing_key = get_signing_key(token, jwks)

        jwt_options = {"verify_aud": bool(settings.zitadel_client_id)}
        decode_kwargs: dict = {
            "algorithms": ["RS256"],
            "issuer": auth_settings.issuer,
            "options": jwt_options,
            "leeway": 30,
        }
        if settings.zitadel_client_id:
            decode_kwargs["audience"] = settings.zitadel_client_id

        claims = jwt.decode(token, signing_key, **decode_kwargs)

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
