"""
AI Provider API Routes

Clean REST endpoints for AI provider configuration management.
All endpoints require admin authentication.

Routes:
- GET    /providers              - List all available provider types
- GET    /providers/{type}       - Get provider details and available models
- GET    /configs                - List all saved configurations
- POST   /configs                - Create a new configuration
- PATCH  /configs/{id}           - Update a configuration
- DELETE /configs/{id}           - Delete a configuration
- POST   /configs/{id}/test      - Test a saved configuration
- POST   /configs/test           - Test configuration before saving
- POST   /configs/reorder        - Reorder configurations (priority)
- GET    /status                 - Get overall AI status
"""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import User as AuthUser
from app.core.auth import require_admin
from app.core.models import APIResponse
from app.db import get_db

logger = structlog.get_logger()

router = APIRouter()


# ============================================================================
# Request Models
# ============================================================================

class ConfigCreate(BaseModel):
    """Request to create a new AI provider configuration."""
    name: str
    provider_type: str
    auth_type: str = "api_key"
    model: str
    api_key: str | None = None
    api_url: str | None = None
    supports_text: bool = True
    supports_vision: bool = True
    supports_files: bool = False
    model_parameters: dict | None = None


class ConfigUpdate(BaseModel):
    """Request to update an AI provider configuration."""
    name: str | None = None
    model: str | None = None
    api_key: str | None = None
    api_url: str | None = None
    supports_text: bool | None = None
    supports_vision: bool | None = None
    supports_files: bool | None = None
    is_enabled: bool | None = None
    model_parameters: dict | None = None


class ConfigReorder(BaseModel):
    """Request to reorder configurations."""
    config_ids: list[int]


class ConfigTestRequest(BaseModel):
    """Request to test a configuration before saving."""
    provider_type: str
    auth_type: str = "api_key"
    model: str
    api_key: str | None = None
    api_url: str | None = None
    model_parameters: dict | None = None


# ============================================================================
# Provider Endpoints (static info from provider files)
# ============================================================================

@router.get("/providers")
async def list_providers(
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """List all available AI provider types with their display info.

    Returns info from each provider's get_provider_info() method.
    """
    from app.services.ai.providers import get_all_providers

    return APIResponse(
        success=True,
        data={"providers": get_all_providers()},
    )


@router.get("/providers/{provider_type}")
async def get_provider(
    provider_type: str,
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Get provider details including available models.

    Delegates to the provider's class methods for models and configuration.
    """
    from app.services.ai.config_service import AIConfigService

    result = await AIConfigService.get_models_for_provider(provider_type)
    default_url = AIConfigService.get_default_url(provider_type)

    return APIResponse(
        success=True,
        data={
            "provider_type": provider_type,
            "provider_info": result.get("provider_info"),
            "models": result["models"],
            "default_model": result["default"],
            "default_url": default_url,
            "reasoning_options": result.get("reasoning_options"),
        },
    )


# ============================================================================
# Configuration CRUD Endpoints
# ============================================================================

@router.get("/configs")
async def list_configs(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """List all saved AI provider configurations."""
    from app.services.ai.config_service import AIConfigService

    service = AIConfigService(db)
    configs = await service.list_all()

    items = []
    for config in configs:
        items.append({
            "id": config.id,
            "name": config.name,
            "provider_type": config.provider_type,
            "auth_type": config.auth_type,
            "model": config.model,
            "api_url": config.api_url,
            "has_api_key": bool(config.api_key_encrypted),
            "supports_text": config.supports_text,
            "supports_vision": config.supports_vision,
            "supports_files": config.supports_files,
            "is_enabled": config.is_enabled,
            "priority": config.priority,
            "status": config.status_display,
            "is_subscription": config.is_subscription,
            "model_parameters": config.model_parameters,
            "last_success_at": config.last_success_at.isoformat() if config.last_success_at else None,
            "last_error_at": config.last_error_at.isoformat() if config.last_error_at else None,
            "last_error_message": config.last_error_message,
            "consecutive_failures": config.consecutive_failures,
            "total_requests": config.total_requests,
            "total_tokens_used": config.total_tokens_used,
            "created_at": config.created_at.isoformat() if config.created_at else None,
        })

    return APIResponse(
        success=True,
        data={"configs": items, "total": len(items)},
    )


@router.post("/configs")
async def create_config(
    request: ConfigCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Create a new AI provider configuration."""
    from app.services.ai.config_service import AIConfigService

    service = AIConfigService(db)

    config = await service.create(
        name=request.name,
        provider_type=request.provider_type,
        auth_type=request.auth_type,
        model=request.model,
        api_key=request.api_key,
        api_url=request.api_url,
        supports_text=request.supports_text,
        supports_vision=request.supports_vision,
        supports_files=request.supports_files,
        model_parameters=request.model_parameters,
        created_by=admin.id,
    )

    await db.commit()

    return APIResponse(
        success=True,
        message=f"Created AI provider config: {config.name}",
        data={"id": config.id},
    )


@router.patch("/configs/{config_id}")
async def update_config(
    config_id: int,
    request: ConfigUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Update an AI provider configuration."""
    from app.services.ai.config_service import AIConfigService

    service = AIConfigService(db)

    config = await service.update(
        config_id=config_id,
        name=request.name,
        model=request.model,
        api_key=request.api_key,
        api_url=request.api_url,
        supports_text=request.supports_text,
        supports_vision=request.supports_vision,
        supports_files=request.supports_files,
        is_enabled=request.is_enabled,
        model_parameters=request.model_parameters,
        modified_by=admin.id,
    )

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found",
        )

    await db.commit()

    return APIResponse(
        success=True,
        message=f"Updated AI provider config: {config.name}",
    )


@router.delete("/configs/{config_id}")
async def delete_config(
    config_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Delete an AI provider configuration."""
    from app.services.ai.config_service import AIConfigService

    service = AIConfigService(db)
    deleted = await service.delete(config_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found",
        )

    await db.commit()

    return APIResponse(success=True, message="AI provider config deleted")


@router.post("/configs/reorder")
async def reorder_configs(
    request: ConfigReorder,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Reorder AI provider configurations (fallback priority)."""
    from app.services.ai.config_service import AIConfigService

    service = AIConfigService(db)
    await service.reorder(request.config_ids)
    await db.commit()

    return APIResponse(success=True, message="Provider order updated")


# ============================================================================
# Test Endpoints
# ============================================================================

@router.post("/configs/{config_id}/test")
async def test_saved_config(
    config_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Test a saved AI provider configuration."""
    from app.services.ai.gateway import AIGateway

    gateway = AIGateway(db)
    result = await gateway.test_provider(config_id)

    return APIResponse(
        success=result.get("success", False),
        message=result.get("message") or result.get("error"),
        data=result,
    )


@router.post("/configs/test")
async def test_config_preview(
    request: ConfigTestRequest,
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Test an AI configuration BEFORE saving it.

    Sends a quick health check to verify the credentials work.
    """
    import time
    from types import SimpleNamespace

    from app.services.ai.providers import PROVIDER_REGISTRY

    start_time = time.time()

    try:
        provider_class = PROVIDER_REGISTRY.get(request.provider_type)
        if not provider_class:
            return APIResponse(
                success=False,
                message=f"Unknown provider type: {request.provider_type}",
            )

        # Create mock config for testing
        mock_config = SimpleNamespace(
            id=0,
            name="Test Config",
            provider_type=request.provider_type,
            model=request.model,
            api_key_encrypted=request.api_key,
            api_url=request.api_url,
            auth_type=request.auth_type,
            is_subscription=False,
            supports_vision=True,
            supports_files=True,
            supports_text=True,
            is_enabled=True,
            oauth_refresh_token_encrypted=None,
            model_parameters=request.model_parameters,
        )

        provider = provider_class(mock_config)

        # Override API key decryption for testing
        if request.api_key:
            provider.api_key = request.api_key

        is_healthy = await provider.health_check()
        elapsed_ms = int((time.time() - start_time) * 1000)

        if is_healthy:
            return APIResponse(
                success=True,
                message=f"Connection successful! Model responded in {elapsed_ms}ms",
                data={"model": request.model, "elapsed_ms": elapsed_ms},
            )
        else:
            return APIResponse(
                success=False,
                message=f"Health check failed after {elapsed_ms}ms",
                data={"model": request.model, "elapsed_ms": elapsed_ms},
            )

    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.warning("ai_config_test_failed", error=str(e), provider=request.provider_type)
        # Sanitize error message to avoid leaking API keys or URLs
        safe_error = _sanitize_error(str(e))
        return APIResponse(
            success=False,
            message=f"Connection failed: {safe_error}",
            data={"model": request.model, "elapsed_ms": elapsed_ms, "error": safe_error},
        )


def _sanitize_error(error: str) -> str:
    """Strip potential API keys, tokens, and full URLs from error messages."""
    import re
    # Redact anything that looks like an API key (long alphanumeric strings)
    error = re.sub(r'(sk-|key-|api-|bearer\s+)[A-Za-z0-9\-_]{16,}', r'\1[REDACTED]', error, flags=re.IGNORECASE)
    # Redact URLs with query params that might contain keys
    error = re.sub(r'https?://[^\s"\']+', '[URL REDACTED]', error)
    return error


# ============================================================================
# Status Endpoint
# ============================================================================

@router.get("/status")
async def get_status(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Get overall AI configuration status."""
    from app.services.ai.config_service import AIConfigService

    service = AIConfigService(db)
    all_configs = await service.list_all()
    enabled_configs = await service.list_enabled()
    active_config = await service.get_active_config()

    return APIResponse(
        success=True,
        data={
            "ai_enabled": len(enabled_configs) > 0,
            "total_configs": len(all_configs),
            "enabled_configs": len(enabled_configs),
            "active_provider": {
                "id": active_config.id,
                "name": active_config.name,
                "provider_type": active_config.provider_type,
                "model": active_config.model,
            } if active_config else None,
        },
    )
