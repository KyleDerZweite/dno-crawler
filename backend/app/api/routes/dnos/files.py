"""
File operations for DNO management.
"""

import asyncio
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import User as AuthUser
from app.core.auth import get_current_user
from app.core.config import settings
from app.core.models import APIResponse
from app.db import DNOModel, get_db

router = APIRouter()


@router.get("/{dno_id}/files")
async def list_dno_files(
    dno_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> APIResponse:
    """List available source files for a DNO (PDFs, HTMLs, etc)."""
    # Find DNO
    dno = await db.get(DNOModel, dno_id)
    if not dno:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DNO not found",
        )

    # Get storage path (with path traversal protection)
    storage_path = settings.storage_path
    base_dir = Path(storage_path) / "downloads"
    downloads_dir = base_dir / dno.slug
    if not downloads_dir.resolve().is_relative_to(base_dir.resolve()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid DNO slug")

    files = []
    if downloads_dir.exists():
        for f in downloads_dir.iterdir():
            if f.is_file() and not f.name.startswith("."):
                # Get file info
                stat = f.stat()
                files.append(
                    {
                        "name": f.name,
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                        "extension": f.suffix.lower(),
                        "path": f"/files/downloads/{dno.slug}/{f.name}",
                    }
                )

    # Sort by name for consistent ordering
    files.sort(key=lambda x: x["name"])

    return APIResponse(
        success=True,
        data=files,
    )


@router.post("/{dno_id}/upload")
async def upload_file(
    dno_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    file: UploadFile = File(...),
) -> APIResponse:
    """
    Upload a file for a DNO.

    Automatically detects data type and year from filename using weighted
    keyword scoring, then renames to canonical format: {data_type}-{year}.{ext}

    This enables extraction for protected DNOs where automated crawling fails.
    """
    import aiofiles
    import structlog

    from app.services.file_analyzer import file_analyzer

    logger = structlog.get_logger()

    # Find DNO by ID or slug
    dno = None
    if isinstance(dno_id, int) or str(dno_id).isdigit():
        query = select(DNOModel).where(DNOModel.id == int(dno_id))
        result = await db.execute(query)
        dno = result.scalar_one_or_none()

    if not dno:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DNO not found",
        )

    # Validate file extension
    original_filename = file.filename or "unknown.pdf"
    ALLOWED_EXTENSIONS = {
        ".pdf",
        ".xlsx",
        ".xls",
        ".csv",
        ".html",
        ".htm",
        ".docx",
        ".doc",
        ".txt",
        ".png",
        ".jpg",
        ".jpeg",
    }
    file_ext = Path(original_filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '{file_ext}' not allowed. Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # Analyze filename
    data_type, year = file_analyzer.analyze(original_filename)

    if not data_type or not year:
        return APIResponse(
            success=False,
            message="Could not detect data type or year from filename",
            data={
                "detected_type": data_type,
                "detected_year": year,
                "filename": original_filename,
                "hint": "Rename file to include type keywords and year (e.g., preisblaetter-2025.pdf or zeitfenster-2025.pdf)",
            },
        )

    # Construct canonical filename (matches existing cache discovery pattern)
    extension = Path(original_filename).suffix.lower() or ".pdf"
    target_filename = f"{dno.slug}-{data_type}-{year}{extension}"

    storage_path = settings.storage_path
    base_dir = Path(storage_path) / "downloads"
    target_dir = base_dir / dno.slug
    if not target_dir.resolve().is_relative_to(base_dir.resolve()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid DNO slug")
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / target_filename

    # Save file with size limit (overwrites existing - user intent takes precedence)
    # Current limit: 250MB. To increase, change the value below.
    MAX_UPLOAD_SIZE = 250 * 1024 * 1024  # 250MB
    total_size = 0
    try:
        async with aiofiles.open(target_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                total_size += len(chunk)
                if total_size > MAX_UPLOAD_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024 * 1024)}MB.",
                    )
                await f.write(chunk)
    except HTTPException:
        await asyncio.to_thread(target_path.unlink, missing_ok=True)
        raise

    logger.info(
        "File uploaded",
        original=original_filename,
        target=target_filename,
        detected_type=data_type,
        detected_year=year,
        dno=dno.slug,
        user=current_user.email,
    )

    return APIResponse(
        success=True,
        message=f"File saved as {target_filename}",
        data={
            "filename": target_filename,
            "path": f"/files/downloads/{dno.slug}/{target_filename}",
            "detected_type": data_type,
            "detected_year": year,
            "original_filename": original_filename,
        },
    )
