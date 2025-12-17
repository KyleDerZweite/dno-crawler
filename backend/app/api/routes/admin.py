"""
Admin routes - requires admin role.

User management has been moved to Zitadel.
This module only contains job management and data normalization routes.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_admin, User as AuthUser
from app.core.models import APIResponse
from app.core.config import settings
from app.db import (
    CrawlJobModel,
    DNOModel,
    NetzentgelteModel,
    get_db,
)
from arq import create_pool
from arq.connections import RedisSettings
import structlog

logger = structlog.get_logger()

router = APIRouter()


@router.get("/dashboard")
async def admin_dashboard(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Get admin dashboard statistics."""
    # Count DNOs
    dno_count = await db.scalar(select(func.count(DNOModel.id)))
    
    # Count DNOs by status
    uncrawled_count = await db.scalar(
        select(func.count(DNOModel.id)).where(DNOModel.status == "uncrawled")
    )
    crawled_count = await db.scalar(
        select(func.count(DNOModel.id)).where(DNOModel.status == "crawled")
    )
    
    # Count pending jobs
    pending_jobs = await db.scalar(
        select(func.count(CrawlJobModel.id)).where(CrawlJobModel.status == "pending")
    )
    running_jobs = await db.scalar(
        select(func.count(CrawlJobModel.id)).where(CrawlJobModel.status == "running")
    )
    
    return APIResponse(
        success=True,
        data={
            "dnos": {
                "total": dno_count or 0,
                "uncrawled": uncrawled_count or 0,
                "crawled": crawled_count or 0,
            },
            "jobs": {
                "pending": pending_jobs or 0,
                "running": running_jobs or 0,
            },
        },
    )