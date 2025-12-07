"""
File serving routes.
"""

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

router = APIRouter()


@router.get("/downloads/{filepath:path}")
async def serve_download(filepath: str) -> FileResponse:
    """Serve a downloaded file."""
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
        )
    
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )
    
    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="application/pdf",
    )
