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
    HLZFModel,
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
    
    # Count flagged records
    flagged_netzentgelte = await db.scalar(
        select(func.count(NetzentgelteModel.id)).where(NetzentgelteModel.verification_status == "flagged")
    )
    flagged_hlzf = await db.scalar(
        select(func.count(HLZFModel.id)).where(HLZFModel.verification_status == "flagged")
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
            "flagged": {
                "netzentgelte": flagged_netzentgelte or 0,
                "hlzf": flagged_hlzf or 0,
                "total": (flagged_netzentgelte or 0) + (flagged_hlzf or 0),
            },
        },
    )


@router.get("/flagged")
async def list_flagged_items(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AuthUser, Depends(require_admin)],
) -> APIResponse:
    """Get all flagged records for review."""
    # Get flagged Netzentgelte with DNO info
    netz_query = (
        select(
            NetzentgelteModel.id,
            NetzentgelteModel.year,
            NetzentgelteModel.voltage_level,
            NetzentgelteModel.flag_reason,
            NetzentgelteModel.flagged_at,
            NetzentgelteModel.flagged_by,
            DNOModel.id.label("dno_id"),
            DNOModel.name.label("dno_name"),
            DNOModel.slug.label("dno_slug"),
        )
        .join(DNOModel, NetzentgelteModel.dno_id == DNOModel.id)
        .where(NetzentgelteModel.verification_status == "flagged")
        .order_by(NetzentgelteModel.flagged_at.desc())
    )
    netz_result = await db.execute(netz_query)
    netz_flagged = [
        {
            "id": row.id,
            "type": "netzentgelte",
            "year": row.year,
            "voltage_level": row.voltage_level,
            "flag_reason": row.flag_reason,
            "flagged_at": row.flagged_at.isoformat() if row.flagged_at else None,
            "flagged_by": row.flagged_by,
            "dno_id": row.dno_id,
            "dno_name": row.dno_name,
            "dno_slug": row.dno_slug,
        }
        for row in netz_result.all()
    ]
    
    # Get flagged HLZF with DNO info
    hlzf_query = (
        select(
            HLZFModel.id,
            HLZFModel.year,
            HLZFModel.voltage_level,
            HLZFModel.flag_reason,
            HLZFModel.flagged_at,
            HLZFModel.flagged_by,
            DNOModel.id.label("dno_id"),
            DNOModel.name.label("dno_name"),
            DNOModel.slug.label("dno_slug"),
        )
        .join(DNOModel, HLZFModel.dno_id == DNOModel.id)
        .where(HLZFModel.verification_status == "flagged")
        .order_by(HLZFModel.flagged_at.desc())
    )
    hlzf_result = await db.execute(hlzf_query)
    hlzf_flagged = [
        {
            "id": row.id,
            "type": "hlzf",
            "year": row.year,
            "voltage_level": row.voltage_level,
            "flag_reason": row.flag_reason,
            "flagged_at": row.flagged_at.isoformat() if row.flagged_at else None,
            "flagged_by": row.flagged_by,
            "dno_id": row.dno_id,
            "dno_name": row.dno_name,
            "dno_slug": row.dno_slug,
        }
        for row in hlzf_result.all()
    ]
    
    # Combine and sort by flagged_at
    all_flagged = netz_flagged + hlzf_flagged
    all_flagged.sort(key=lambda x: x["flagged_at"] or "", reverse=True)
    
    return APIResponse(
        success=True,
        data={
            "items": all_flagged,
            "total": len(all_flagged),
        },
    )