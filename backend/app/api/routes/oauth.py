"""
OAuth Routes for AI Provider Authentication

Handles OAuth flows for:
- Google (Gemini) - Using gemini-cli compatible OAuth
"""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.core.auth import User as AuthUser
from app.core.auth import require_admin
from app.core.config import settings
from app.core.models import APIResponse

logger = structlog.get_logger()

router = APIRouter(prefix="/oauth", tags=["oauth"])


# ==============================================================================
# CLI Credential Detection
# ==============================================================================


@router.get("/detect-credentials")
async def detect_cli_credentials(
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Detect available CLI credentials for AI providers.

    Checks for:
    - ~/.gemini/oauth_creds.json (gemini-cli)
    - ~/.codex/auth.json (codex-cli) [future]
    - ~/.claude/.credentials.json (claude-code) [future]

    Returns detected credentials with user info for auto-configuration.
    """
    from app.services.ai.oauth.google import get_credential_manager

    detected = {}

    # Check Google/Gemini CLI
    try:
        cred_manager = get_credential_manager()
        # Use load_credentials() which checks /data/auth/ first, then ~/.gemini/
        gemini_creds = cred_manager.load_credentials()

        if gemini_creds:
            user_info = cred_manager.get_user_info()
            detected["google"] = {
                "available": True,
                "source": "oauth" if gemini_creds.get("user_email") else "gemini-cli",
                "email": user_info.get("email") if user_info else None,
                "name": user_info.get("name") if user_info else None,
                "has_refresh_token": "refresh_token" in gemini_creds,
            }
        else:
            detected["google"] = {
                "available": False,
                "source": None,
                "instructions": "Run 'gemini auth login' or use OAuth to authenticate",
            }
    except Exception as e:
        detected["google"] = {
            "available": False,
            "error": str(e),
        }

    # Future: Check Anthropic/Claude Code
    detected["anthropic"] = {
        "available": False,
        "source": None,
        "instructions": "Run 'claude auth login' to authenticate (coming soon)",
    }

    # Future: Check OpenAI/Codex
    detected["openai"] = {
        "available": False,
        "source": None,
        "instructions": "Run 'codex auth login' to authenticate (coming soon)",
    }

    return APIResponse(
        success=True,
        data={
            "credentials": detected,
            "any_available": any(c.get("available", False) for c in detected.values()),
        },
    )


# ==============================================================================
# Google OAuth Endpoints
# ==============================================================================


class GoogleOAuthInitRequest(BaseModel):
    """Request to start Google OAuth flow."""

    redirect_uri: str | None = None  # Override callback URL if needed


class GoogleOAuthCallbackRequest(BaseModel):
    """Callback from Google OAuth."""

    code: str
    state: str


# In-memory state storage with TTL (for single-instance, use Redis for distributed)
_oauth_pending_states: dict[str, dict] = {}
_OAUTH_STATE_TTL = 600  # 10 minutes
_OAUTH_MAX_PENDING = 50  # Max concurrent pending states


def _cleanup_expired_states() -> None:
    """Remove expired OAuth states to prevent memory leaks."""
    import time

    now = time.time()
    expired = [
        k
        for k, v in _oauth_pending_states.items()
        if now - v.get("created_at", 0) > _OAUTH_STATE_TTL
    ]
    for k in expired:
        del _oauth_pending_states[k]


@router.post("/google/start")
async def start_google_oauth(
    request: GoogleOAuthInitRequest,
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Start Google OAuth flow.

    Returns an authorization URL that the frontend should open in a new window.
    The user authenticates with Google, then is redirected back to our callback.

    This uses the same OAuth client as gemini-cli, so:
    - Works with Google account's Gemini quota
    - Gets 1M+ token context with Google One AI Premium
    - Free tier: 60 req/min, 1000 req/day
    """
    from app.services.ai.oauth.google import GoogleOAuthFlow

    # Determine callback URL
    if request.redirect_uri:
        redirect_uri = request.redirect_uri
    else:
        # Construct from settings
        base_url = getattr(settings, "base_url", None) or "http://localhost:8000"
        redirect_uri = f"{base_url}/api/v1/admin/oauth/google/callback"

    flow = GoogleOAuthFlow(redirect_uri=redirect_uri)
    auth_url, state, code_verifier = flow.generate_authorization_url()

    # Clean up expired states before adding new one
    import time

    _cleanup_expired_states()
    if len(_oauth_pending_states) >= _OAUTH_MAX_PENDING:
        return APIResponse(
            success=False, message="Too many pending OAuth flows. Please try again shortly."
        )

    # Store state for verification (with code_verifier for PKCE)
    _oauth_pending_states[state] = {
        "code_verifier": code_verifier,
        "redirect_uri": redirect_uri,
        "initiated_by": admin.email,
        "created_at": time.time(),
    }

    logger.info(
        "google_oauth_started",
        user=admin.email,
        redirect_uri=redirect_uri,
    )

    return APIResponse(
        success=True,
        message="Open the authorization URL to authenticate with Google",
        data={
            "auth_url": auth_url,
            "state": state,
        },
    )


@router.get("/google/callback")
async def google_oauth_callback_get(
    code: Annotated[str, Query(description="Authorization code from Google")],
    state: Annotated[str, Query(description="State parameter for verification")],
):
    """Handle Google OAuth callback (GET - browser redirect).

    Google redirects here after user authorizes.
    This endpoint exchanges the code for tokens and returns HTML
    that closes the popup window.
    """
    import json as json_mod
    from html import escape as html_escape

    from fastapi.responses import HTMLResponse

    result = await _handle_google_callback_internal(code, state)

    # Determine the target origin for postMessage from settings
    post_message_origin = settings.cors_origins[0] if settings.cors_origins else "null"

    # Return HTML that closes the popup and notifies parent
    if result["success"]:
        safe_email = html_escape(str(result.get("email", "")), quote=True)
        # safe_name = html_escape(str(result.get('name', '')), quote=True)
        # JSON-encode for safe embedding in JavaScript
        js_email = json_mod.dumps(str(result.get("email", "")))
        js_name = json_mod.dumps(str(result.get("name", "")))
        js_origin = json_mod.dumps(post_message_origin)
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>OAuth Success</title>
    <style>
        body {{
            font-family: system-ui, -apple-system, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: white;
        }}
        .container {{
            text-align: center;
            padding: 2rem;
            background: rgba(255,255,255,0.1);
            border-radius: 1rem;
            backdrop-filter: blur(10px);
        }}
        .icon {{ font-size: 4rem; margin-bottom: 1rem; }}
        h1 {{ margin: 0 0 0.5rem 0; font-size: 1.5rem; }}
        p {{ margin: 0; opacity: 0.9; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">&#10003;</div>
        <h1>Authentication Successful!</h1>
        <p>Signed in as {safe_email}</p>
        <p style="margin-top: 1rem; font-size: 0.875rem; opacity: 0.7;">This window will close automatically...</p>
    </div>
    <script>
        // Notify parent window of success
        if (window.opener) {{
            window.opener.postMessage({{
                type: 'oauth_complete',
                success: true,
                email: {js_email},
                name: {js_name}
            }}, {js_origin});
        }}
        // Close popup after brief delay
        setTimeout(() => window.close(), 1500);
    </script>
</body>
</html>
"""
    else:
        safe_message = html_escape(str(result.get("message", "Unknown error")), quote=True)
        js_message = json_mod.dumps(str(result.get("message", "Unknown error")))
        js_origin = json_mod.dumps(post_message_origin)
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>OAuth Failed</title>
    <style>
        body {{
            font-family: system-ui, -apple-system, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
            color: white;
        }}
        .container {{
            text-align: center;
            padding: 2rem;
            background: rgba(255,255,255,0.1);
            border-radius: 1rem;
            backdrop-filter: blur(10px);
            max-width: 400px;
        }}
        .icon {{ font-size: 4rem; margin-bottom: 1rem; }}
        h1 {{ margin: 0 0 0.5rem 0; font-size: 1.5rem; }}
        p {{ margin: 0; opacity: 0.9; word-break: break-word; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">&#10007;</div>
        <h1>Authentication Failed</h1>
        <p>{safe_message}</p>
        <p style="margin-top: 1rem; font-size: 0.875rem; opacity: 0.7;">You can close this window and try again.</p>
    </div>
    <script>
        // Notify parent window of failure
        if (window.opener) {{
            window.opener.postMessage({{
                type: 'oauth_complete',
                success: false,
                error: {js_message}
            }}, {js_origin});
        }}
    </script>
</body>
</html>
"""

    return HTMLResponse(content=html)


@router.post("/google/callback")
async def google_oauth_callback_post(
    request: GoogleOAuthCallbackRequest,
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Handle Google OAuth callback (POST - from frontend).

    Frontend can POST the code/state after intercepting the redirect.
    """
    result = await _handle_google_callback_internal(request.code, request.state)
    if result["success"]:
        return APIResponse(
            success=True,
            message=result["message"],
            data={
                "email": result.get("email"),
                "name": result.get("name"),
                "expires_at": result.get("expires_at"),
            },
        )
    else:
        return APIResponse(
            success=False,
            message=result["message"],
        )


async def _handle_google_callback_internal(code: str, state: str) -> dict:
    """Process OAuth callback and store credentials. Returns a dict."""
    import time

    from app.services.ai.oauth.google import GoogleOAuthFlow, get_credential_manager

    # Verify state (with TTL check)
    _cleanup_expired_states()
    pending = _oauth_pending_states.get(state)
    if not pending:
        logger.warning("google_oauth_invalid_state", state=state[:8] + "...")
        return {
            "success": False,
            "message": "Invalid or expired OAuth state. Please try again.",
        }
    if time.time() - pending.get("created_at", 0) > _OAUTH_STATE_TTL:
        del _oauth_pending_states[state]
        return {
            "success": False,
            "message": "OAuth state expired. Please try again.",
        }

    # Exchange code for tokens
    try:
        flow = GoogleOAuthFlow(redirect_uri=pending["redirect_uri"])
        flow.set_pending_state(state, pending["code_verifier"])

        credentials = await flow.exchange_code(
            code=code,
            state=state,
            code_verifier=pending["code_verifier"],
        )

        # Store credentials
        cred_manager = get_credential_manager()
        cred_manager.save_credentials(credentials, to_gemini_cli=True)

        # Clean up pending state
        del _oauth_pending_states[state]

        logger.info(
            "google_oauth_complete",
            email=credentials.get("user_email"),
        )

        return {
            "success": True,
            "message": f"Successfully authenticated as {credentials.get('user_email')}",
            "email": credentials.get("user_email"),
            "name": credentials.get("user_name"),
            "expires_at": credentials.get("expires_at"),
        }

    except Exception as e:
        logger.error("google_oauth_callback_failed", error=str(e))
        return {
            "success": False,
            "message": f"OAuth failed: {e!s}",
        }


@router.get("/google/status")
async def google_oauth_status(
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Check Google OAuth authentication status.

    Also checks for gemini-cli credentials that can be shared.
    """
    from app.services.ai.oauth.google import get_credential_manager

    cred_manager = get_credential_manager()
    is_authenticated = cred_manager.is_authenticated()
    user_info = cred_manager.get_user_info() if is_authenticated else None

    # Check gemini-cli credentials too
    gemini_cli_creds = cred_manager.get_gemini_cli_credentials()

    return APIResponse(
        success=True,
        data={
            "authenticated": is_authenticated,
            "user": user_info,
            "gemini_cli_available": gemini_cli_creds is not None,
            "gemini_cli_email": gemini_cli_creds.get("user_email") if gemini_cli_creds else None,
        },
    )


@router.post("/google/logout")
async def google_oauth_logout(
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Clear Google OAuth credentials.

    Note: This only clears our credentials, not gemini-cli's.
    """
    from app.services.ai.oauth.google import get_credential_manager

    cred_manager = get_credential_manager()
    cred_manager.clear_credentials()

    logger.info("google_oauth_logout", user=admin.email)

    return APIResponse(
        success=True,
        message="Google OAuth credentials cleared",
    )


@router.post("/google/use-gemini-cli")
async def use_gemini_cli_credentials(
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Use existing gemini-cli credentials.

    If the user has already run 'gemini auth login', we can use those credentials.
    """
    from app.services.ai.oauth.google import get_credential_manager

    cred_manager = get_credential_manager()
    gemini_cli_creds = cred_manager.get_gemini_cli_credentials()

    if not gemini_cli_creds:
        return APIResponse(
            success=False,
            message="No gemini-cli credentials found. Please run 'gemini auth login' first, or use the OAuth flow.",
        )

    # Copy gemini-cli creds to our storage
    cred_manager.save_credentials(gemini_cli_creds, to_gemini_cli=False)

    logger.info(
        "using_gemini_cli_credentials",
        email=gemini_cli_creds.get("user_email"),
    )

    return APIResponse(
        success=True,
        message=f"Now using gemini-cli credentials for {gemini_cli_creds.get('user_email')}",
        data={
            "email": gemini_cli_creds.get("user_email"),
        },
    )
