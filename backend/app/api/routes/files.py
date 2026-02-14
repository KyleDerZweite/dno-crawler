"""
File serving routes with rate limiting.
"""

import mimetypes
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import FileResponse

from app.core.rate_limiter import get_client_ip, get_rate_limiter

router = APIRouter()


@router.get("/downloads/{filepath:path}")
async def serve_download(filepath: str, request: Request) -> FileResponse:
    """Serve a downloaded file (public, rate-limited)."""
    # Apply rate limiting (30 downloads per minute per IP)
    try:
        rate_limiter = get_rate_limiter()
        client_ip = get_client_ip(request)
        await rate_limiter.check_ip_limit(client_ip)
    except RuntimeError:
        pass  # Rate limiter not initialized (dev mode), allow request

    storage_path = os.environ.get("STORAGE_PATH", "/data")
    file_path = Path(storage_path) / "downloads" / filepath

    # Security check - ensure path is within downloads directory
    downloads_base = (Path(storage_path) / "downloads").resolve()
    try:
        resolved_path = file_path.resolve()
        if not str(resolved_path).startswith(str(downloads_base)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        ) from None

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    media_type, _ = mimetypes.guess_type(file_path.name)
    if not media_type:
        media_type = "application/octet-stream"

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type=media_type,
    )
