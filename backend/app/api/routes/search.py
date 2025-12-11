"""
Search API routes for natural language search with Timeline UI.

Provides endpoints for:
- Natural language search with filters (POST /search)
- Job status polling for Timeline UI (GET /search/{job_id}/status)
- Search history (GET /search/history)
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

import structlog
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, get_optional_user
from app.core.config import settings
from app.core.models import User
from app.db import get_db
from app.db.models import SearchJobModel

logger = structlog.get_logger()
router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================


class SearchFilters(BaseModel):
    """Filters for search queries."""
    years: list[int] = Field(
        default=[2024, 2025], 
        description="Years to search for. Empty = AI extracts from query."
    )
    types: list[str] = Field(
        default=["netzentgelte", "hlzf"],
        description="Data types to search for."
    )


class SearchRequest(BaseModel):
    """Request to start a natural language search."""
    prompt: str = Field(
        ..., 
        min_length=3,
        max_length=500,
        description="Natural language search query",
        example="Musterstr 5, Köln"
    )
    filters: SearchFilters = Field(default_factory=SearchFilters)


class SearchJobStatus(BaseModel):
    """Response for search job status (used for polling)."""
    job_id: str
    status: str  # pending | running | completed | failed
    input_text: str = ""
    filters: Optional[dict] = None
    current_step: Optional[str] = None
    steps_history: list[dict] = []
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: datetime


class SearchJobListItem(BaseModel):
    """Item in search history list."""
    job_id: str
    input_text: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None


class SearchResponse(BaseModel):
    """Response after starting a search job."""
    job_id: str
    status: str = "pending"
    message: str


# ============================================================================
# Endpoints
# ============================================================================


@router.post(
    "",
    response_model=SearchResponse,
    summary="Start Natural Language Search",
    description="Start a search job from natural language input. Returns job_id for polling."
)
async def create_search(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    Start a natural language search job.
    
    Flow:
    1. Create SearchJob record in DB
    2. Queue job to ARQ worker (respects max_jobs=1)
    3. Return job_id for frontend polling
    
    The frontend should poll GET /search/{job_id}/status every ~1.5 seconds.
    """
    log = logger.bind(
        prompt=request.prompt[:50],
        user=current_user.email if current_user else "anonymous"
    )
    log.info("Creating search job")
    
    try:
        # 1. Create job record in DB
        job = SearchJobModel(
            user_id=current_user.id if current_user else None,
            input_text=request.prompt,
            filters={
                "years": request.filters.years,
                "types": request.filters.types,
            },
            status="pending",
            steps_history=[],
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        
        job_id = str(job.id)
        log.info("Search job created", job_id=job_id)
        
        # 2. Queue to ARQ worker (CRITICAL: use ARQ, not BackgroundTasks)
        redis_pool = await create_pool(
            RedisSettings.from_dsn(str(settings.redis_url))
        )
        
        await redis_pool.enqueue_job(
            "job_process_search_request",
            job_id=job_id,
            prompt=request.prompt,
            filters=request.filters.model_dump(),
        )
        
        await redis_pool.close()
        
        log.info("Search job queued to ARQ", job_id=job_id)
        
        return SearchResponse(
            job_id=job_id,
            status="pending",
            message=f"Search started for: {request.prompt[:50]}..."
        )
        
    except Exception as e:
        log.error("Failed to create search job", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to start search: {str(e)}")


@router.get(
    "/{job_id}/status",
    response_model=SearchJobStatus,
    summary="Get Search Job Status",
    description="Poll for search job status. Call every ~1.5 seconds for Timeline UI."
)
async def get_search_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get the current status of a search job for the Timeline UI.
    
    Returns:
    - steps_history: Array of completed/running steps for the timeline
    - current_step: What the agent is currently doing
    - result: Final data if status == "completed"
    - error: Error message if status == "failed"
    """
    try:
        job_uuid = UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")
    
    result = await db.execute(
        select(SearchJobModel).where(SearchJobModel.id == job_uuid)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Search job not found")
    
    return SearchJobStatus(
        job_id=str(job.id),
        status=job.status,
        input_text=job.input_text,
        filters=job.filters,
        current_step=job.current_step,
        steps_history=job.steps_history or [],
        result=job.result if job.status == "completed" else None,
        error=job.error_message if job.status == "failed" else None,
        created_at=job.created_at,
    )


@router.post(
    "/{job_id}/cancel",
    summary="Cancel Search Job",
    description="Cancel a running or pending search job."
)
async def cancel_search(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cancel a pending or running search job.
    
    Sets the job status to 'cancelled'. The worker will check this
    and stop processing if it hasn't completed yet.
    """
    try:
        job_uuid = UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")
    
    result = await db.execute(
        select(SearchJobModel).where(
            SearchJobModel.id == job_uuid,
            SearchJobModel.user_id == current_user.id
        )
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Search job not found")
    
    if job.status in ("completed", "failed", "cancelled"):
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot cancel job with status: {job.status}"
        )
    
    job.status = "cancelled"
    job.error_message = "Cancelled by user"
    job.completed_at = datetime.utcnow()
    await db.commit()
    
    logger.info("Search job cancelled", job_id=job_id, user=current_user.email)
    
    return {"status": "cancelled", "message": "Search job cancelled"}


@router.get(
    "/history",
    response_model=list[SearchJobListItem],
    summary="Get Search History",
    description="Get list of past searches for the current user."
)
async def get_search_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100),
):
    """
    Get past searches for the current user's history sidebar.
    
    Returns the most recent searches, ordered by creation date.
    """
    result = await db.execute(
        select(SearchJobModel)
        .where(SearchJobModel.user_id == current_user.id)
        .order_by(SearchJobModel.created_at.desc())
        .limit(limit)
    )
    jobs = result.scalars().all()
    
    return [
        SearchJobListItem(
            job_id=str(job.id),
            input_text=job.input_text,
            status=job.status,
            created_at=job.created_at,
            completed_at=job.completed_at,
        )
        for job in jobs
    ]


@router.get(
    "/{job_id}",
    response_model=SearchJobStatus,
    summary="Get Search Job Details",
    description="Get full details of a past search job (for loading from history)."
)
async def get_search_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get full details of a search job (for loading from history).
    
    Unlike /status, this requires authentication and returns the full result.
    """
    try:
        job_uuid = UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")
    
    result = await db.execute(
        select(SearchJobModel).where(
            SearchJobModel.id == job_uuid,
            SearchJobModel.user_id == current_user.id
        )
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Search job not found")
    
    return SearchJobStatus(
        job_id=str(job.id),
        status=job.status,
        current_step=job.current_step,
        steps_history=job.steps_history or [],
        result=job.result,
        error=job.error_message,
        created_at=job.created_at,
    )
