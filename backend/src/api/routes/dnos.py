"""
DNO management routes (authenticated).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.routes.auth import get_current_active_user
from src.core.models import APIResponse, CrawlJob, CrawlJobCreate, DataType
from src.db import CrawlJobModel, DNOModel, UserModel, get_db

router = APIRouter()


class TriggerCrawlRequest(BaseModel):
    year: int
    data_type: DataType = DataType.ALL
    priority: int = 5


@router.get("/")
async def list_dnos_detailed(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    include_stats: bool = Query(False),
) -> APIResponse:
    """
    List all DNOs with detailed information.
    
    Authenticated endpoint with more details than public endpoint.
    """
    query = select(DNOModel).order_by(DNOModel.name)
    result = await db.execute(query)
    dnos = result.scalars().all()
    
    data = []
    for dno in dnos:
        dno_data = {
            "id": str(dno.id),
            "slug": dno.slug,
            "name": dno.name,
            "official_name": dno.official_name,
            "description": dno.description,
            "region": dno.region,
            "website": dno.website,
            "created_at": dno.created_at.isoformat() if dno.created_at else None,
            "updated_at": dno.updated_at.isoformat() if dno.updated_at else None,
        }
        
        if include_stats:
            # TODO: Add actual stats (data counts, last crawl, etc.)
            dno_data["stats"] = {
                "netzentgelte_count": 0,
                "hlzf_count": 0,
                "years_available": [],
                "last_crawl": None,
            }
        
        data.append(dno_data)
    
    return APIResponse(success=True, data=data)


@router.get("/{dno_id}")
async def get_dno_details(
    dno_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
) -> APIResponse:
    """Get detailed information about a specific DNO."""
    query = select(DNOModel).where(DNOModel.id == dno_id)
    result = await db.execute(query)
    dno = result.scalar_one_or_none()
    
    if not dno:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DNO not found",
        )
    
    return APIResponse(
        success=True,
        data={
            "id": str(dno.id),
            "slug": dno.slug,
            "name": dno.name,
            "official_name": dno.official_name,
            "description": dno.description,
            "region": dno.region,
            "website": dno.website,
            "created_at": dno.created_at.isoformat() if dno.created_at else None,
            "updated_at": dno.updated_at.isoformat() if dno.updated_at else None,
        },
    )


@router.post("/{dno_id}/crawl")
async def trigger_crawl(
    dno_id: UUID,
    request: TriggerCrawlRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
) -> APIResponse:
    """
    Trigger a crawl job for a specific DNO.
    
    Creates a new crawl job that will be picked up by the worker.
    """
    # Verify DNO exists
    query = select(DNOModel).where(DNOModel.id == dno_id)
    result = await db.execute(query)
    dno = result.scalar_one_or_none()
    
    if not dno:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DNO not found",
        )
    
    # Check for existing pending/running job
    existing_query = select(CrawlJobModel).where(
        CrawlJobModel.dno_id == dno_id,
        CrawlJobModel.year == request.year,
        CrawlJobModel.status.in_(["pending", "running"]),
    )
    result = await db.execute(existing_query)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A crawl job for this DNO and year is already in progress",
        )
    
    # Create crawl job
    job = CrawlJobModel(
        user_id=current_user.id,
        dno_id=dno_id,
        year=request.year,
        data_type=request.data_type.value,
        priority=request.priority,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    return APIResponse(
        success=True,
        message=f"Crawl job created for {dno.name} ({request.year})",
        data={
            "job_id": str(job.id),
            "dno_id": str(dno_id),
            "dno_name": dno.name,
            "year": request.year,
            "data_type": request.data_type.value,
            "status": job.status,
        },
    )


@router.get("/{dno_id}/data")
async def get_dno_data(
    dno_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    year: int | None = Query(None),
    data_type: DataType | None = Query(None),
) -> APIResponse:
    """Get all data for a specific DNO."""
    # Verify DNO exists
    query = select(DNOModel).where(DNOModel.id == dno_id)
    result = await db.execute(query)
    dno = result.scalar_one_or_none()
    
    if not dno:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DNO not found",
        )
    
    # TODO: Implement actual data retrieval
    return APIResponse(
        success=True,
        data={
            "dno": {
                "id": str(dno.id),
                "name": dno.name,
            },
            "netzentgelte": [],
            "hlzf": [],
        },
    )


@router.get("/{dno_id}/jobs")
async def get_dno_crawl_jobs(
    dno_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
    limit: int = Query(10, ge=1, le=50),
) -> APIResponse:
    """Get recent crawl jobs for a DNO."""
    query = (
        select(CrawlJobModel)
        .where(CrawlJobModel.dno_id == dno_id)
        .order_by(CrawlJobModel.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    return APIResponse(
        success=True,
        data=[
            {
                "id": str(job.id),
                "year": job.year,
                "data_type": job.data_type,
                "status": job.status,
                "progress": job.progress,
                "current_step": job.current_step,
                "error_message": job.error_message,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "created_at": job.created_at.isoformat() if job.created_at else None,
            }
            for job in jobs
        ],
    )
