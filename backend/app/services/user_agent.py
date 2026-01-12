"""
User-Agent builder for DNO Crawler.

Provides a centralized utility to build consistent User-Agent strings
with appropriate contact information based on configuration.
"""

from app.core.config import get_settings


def build_user_agent(initiator_ip: str | None = None) -> str:
    """
    Build User-Agent string with appropriate contact info.

    Priority:
    1. If CONTACT_EMAIL is configured → use email
    2. If in dev mode (mock auth) and initiator_ip provided → use IP
    3. Otherwise → reference repository

    Args:
        initiator_ip: IP address of the user who initiated the crawl job

    Returns:
        User-Agent string suitable for crawling requests
    """
    settings = get_settings()

    if settings.has_contact_email:
        contact = f"contact: {settings.contact_email}"
    elif initiator_ip:
        contact = f"initiated-by: {initiator_ip}"
    else:
        contact = "see repository"

    return (
        f"DNO-Data-Crawler/1.0 "
        f"(Netzentgelte/HLZF Research; {contact}; "
        f"+https://github.com/KyleDerZweite/dno-crawler)"
    )


def require_contact_for_bfs(initiator_ip: str | None = None) -> str:
    """
    Get User-Agent for BFS crawling, enforcing contact requirement in production.

    In production (Zitadel auth enabled), this requires CONTACT_EMAIL to be set.
    In development (mock auth), falls back to initiator IP.

    Args:
        initiator_ip: IP address of the user who initiated the crawl job

    Returns:
        User-Agent string

    Raises:
        ValueError: If in production mode and no CONTACT_EMAIL is configured
    """
    settings = get_settings()

    # If email is configured, always use it
    if settings.has_contact_email:
        return build_user_agent(initiator_ip)

    # In production (Zitadel enabled), require email
    if settings.is_auth_enabled:
        raise ValueError(
            "BFS crawling requires CONTACT_EMAIL to be configured in production. "
            "Set CONTACT_EMAIL in your .env file to a valid email address. "
            "This protects you by ensuring site administrators can reach you if needed."
        )

    # In dev mode (mock auth), allow IP fallback
    return build_user_agent(initiator_ip)
