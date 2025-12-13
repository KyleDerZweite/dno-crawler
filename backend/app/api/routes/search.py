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


# ============================================================================
# Structured Input Models (for batch search)
# ============================================================================


class AddressInput(BaseModel):
    """Address input with street and PLZ+City."""
    street: str = Field(..., min_length=1, description="Street + housenumber")
    plz_city: str = Field(..., min_length=3, description="PLZ + City (e.g., '50859 Köln')")


class DNOInput(BaseModel):
    """Direct DNO name input."""
    dno_name: str = Field(..., min_length=2, description="DNO name")


class CoordinatesInput(BaseModel):
    """Geographic coordinates input."""
    longitude: float = Field(..., ge=-180, le=180, description="Longitude")
    latitude: float = Field(..., ge=-90, le=90, description="Latitude")


class SearchPayloadItem(BaseModel):
    """A single search payload - one of three types."""
    type: str = Field(..., pattern="^(address|dno|coordinates)$")
    address: Optional[AddressInput] = None
    dno: Optional[DNOInput] = None
    coordinates: Optional[CoordinatesInput] = None
    
    def get_display_label(self) -> str:
        """Generate a display label for this search item."""
        if self.type == "address" and self.address:
            return f"{self.address.street}, {self.address.plz_city}"
        elif self.type == "dno" and self.dno:
            return self.dno.dno_name
        elif self.type == "coordinates" and self.coordinates:
            return f"({self.coordinates.latitude:.4f}, {self.coordinates.longitude:.4f})"
        return "Unknown"


class BatchSearchRequest(BaseModel):
    """Batch of search payloads to queue."""
    payloads: list[SearchPayloadItem] = Field(..., min_length=1)
    filters: SearchFilters = Field(default_factory=SearchFilters)


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
    # Batch fields
    batch_id: Optional[str] = None
    batch_index: Optional[int] = None
    batch_total: Optional[int] = None
    dno_name: Optional[str] = None
    dno_coordinates: Optional[dict] = None
    year: Optional[int] = None
    data_type: Optional[str] = None


class SearchJobListItem(BaseModel):
    """Item in search history list."""
    job_id: str
    input_text: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    # Batch info for grouped display
    batch_id: Optional[str] = None
    batch_total: Optional[int] = None
    batch_completed: Optional[int] = None  # How many in batch are done
    dno_names: Optional[list[str]] = None  # DNOs in this batch


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


@router.post(
    "/batch",
    summary="Start Batch Search",
    description="Start multiple search jobs from structured payloads. Pre-resolves DNOs and creates sub-jobs for each year/type combination."
)
async def create_batch_search(
    request: BatchSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    Start batch search with two phases:
    
    Phase 1: DNO Resolution (synchronous)
    - Address → VNB Digital API → DNO name + coordinates
    - Coordinates → VNB Digital API → DNO name
    - DNO name → pass through
    
    Phase 2: Create Sub-Jobs
    - For each resolved DNO, create jobs for each year × type combination
    - E.g., 2 DNOs × 2 years × 2 types = 8 jobs
    
    Returns batch_id for tracking all jobs together.
    """
    from uuid import uuid4
    from app.services.vnb_digital import VNBDigitalClient
    
    log = logger.bind(
        batch_size=len(request.payloads),
        user=current_user.email if current_user else "anonymous"
    )
    log.info("Creating batch search")
    
    # Generate batch ID for grouping
    batch_id = uuid4()
    
    # Phase 1: Resolve all DNOs first
    vnb_client = VNBDigitalClient(request_delay=1.0)
    resolved_dnos = []  # List of {"dno_name": ..., "coordinates": {...}, "source_label": ...}
    
    for payload in request.payloads:
        source_label = payload.get_display_label()
        dno_info = {"dno_name": None, "coordinates": None, "source_label": source_label}
        
        try:
            if payload.type == "address" and payload.address:
                # Address → VNB Digital API → DNO + coordinates
                full_address = f"{payload.address.street}, {payload.address.plz_city}"
                
                # First get coordinates
                location = vnb_client.search_address(full_address)
                if location:
                    dno_info["coordinates"] = {"lat": location.latitude, "lon": location.longitude}
                    # Then get DNO from coordinates
                    vnbs = vnb_client.lookup_by_coordinates(location.latitude, location.longitude)
                    if vnbs:
                        # Find electricity (Strom) DNO
                        for vnb in vnbs:
                            if vnb.sparte == "Strom":
                                dno_info["dno_name"] = vnb.name
                                break
                        if not dno_info["dno_name"] and vnbs:
                            dno_info["dno_name"] = vnbs[0].name
                
            elif payload.type == "coordinates" and payload.coordinates:
                # Coordinates → VNB Digital API → DNO
                lat = payload.coordinates.latitude
                lon = payload.coordinates.longitude
                dno_info["coordinates"] = {"lat": lat, "lon": lon}
                
                vnbs = vnb_client.lookup_by_coordinates(lat, lon)
                if vnbs:
                    for vnb in vnbs:
                        if vnb.sparte == "Strom":
                            dno_info["dno_name"] = vnb.name
                            break
                    if not dno_info["dno_name"] and vnbs:
                        dno_info["dno_name"] = vnbs[0].name
                
            elif payload.type == "dno" and payload.dno:
                # Direct DNO name - pass through
                dno_info["dno_name"] = payload.dno.dno_name
            
            log.debug("DNO resolved", source=source_label, dno=dno_info["dno_name"])
            
        except Exception as e:
            log.warning("DNO resolution failed", source=source_label, error=str(e))
        
        if dno_info["dno_name"]:
            resolved_dnos.append(dno_info)
    
    if not resolved_dnos:
        raise HTTPException(
            status_code=400, 
            detail="Could not resolve any DNO names from the provided inputs"
        )
    
    # Phase 2: Create sub-jobs for each DNO × year × type
    job_ids = []
    years = request.filters.years
    types = request.filters.types
    
    # Calculate total jobs
    total_jobs = len(resolved_dnos) * len(years) * len(types)
    job_index = 0
    
    try:
        redis_pool = await create_pool(
            RedisSettings.from_dsn(str(settings.redis_url))
        )
        
        for dno_info in resolved_dnos:
            dno_name = dno_info["dno_name"]
            coordinates = dno_info["coordinates"]
            source_label = dno_info["source_label"]
            
            for year in years:
                for data_type in types:
                    job_index += 1
                    
                    # Generate display label
                    type_label = "Netzentgelte" if data_type == "netzentgelte" else "HLZF"
                    input_text = f"{year} {type_label} - {dno_name}"
                    
                    # Create job record
                    job = SearchJobModel(
                        user_id=current_user.id if current_user else None,
                        batch_id=batch_id,
                        batch_index=job_index,
                        batch_total=total_jobs,
                        dno_name=dno_name,
                        dno_coordinates=coordinates,
                        year=year,
                        data_type=data_type,
                        input_text=input_text,
                        filters={
                            "years": [year],
                            "types": [data_type],
                            "source_label": source_label,
                        },
                        status="pending",
                        steps_history=[],
                    )
                    db.add(job)
                    await db.commit()
                    await db.refresh(job)
                    
                    job_id = str(job.id)
                    job_ids.append(job_id)
                    
                    # Queue to ARQ worker
                    await redis_pool.enqueue_job(
                        "job_process_search_request",
                        job_id=job_id,
                        payload={
                            "type": "dno",
                            "dno": {"dno_name": dno_name},
                        },
                        filters={
                            "years": [year],
                            "types": [data_type],
                        },
                    )
                    
                    log.debug("Sub-job created", job_id=job_id, job_index=job_index)
        
        await redis_pool.close()
        
        log.info("Batch search queued", batch_id=str(batch_id), total_jobs=total_jobs)
        
        return {
            "batch_id": str(batch_id),
            "job_ids": job_ids,
            "count": len(job_ids),
            "resolved_dnos": [
                {"dno_name": d["dno_name"], "source": d["source_label"], "coordinates": d["coordinates"]}
                for d in resolved_dnos
            ],
            "status": "queued",
        }
        
    except Exception as e:
        log.error("Failed to create batch search", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to start batch search: {str(e)}")

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
        # Batch fields
        batch_id=str(job.batch_id) if job.batch_id else None,
        batch_index=job.batch_index,
        batch_total=job.batch_total,
        dno_name=job.dno_name,
        dno_coordinates=job.dno_coordinates,
        year=job.year,
        data_type=job.data_type,
    )


@router.get(
    "/batch/{batch_id}",
    summary="Get Batch Search Status",
    description="Get status of all jobs in a batch. Use for BatchProgressPage UI."
)
async def get_batch_status(
    batch_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get the status of all jobs in a batch.
    
    Returns:
    - jobs: List of all jobs with their status and progress
    - resolved_dnos: DNO names that were resolved
    - progress: Overall completion percentage
    - current_job: Index of currently running job
    """
    try:
        batch_uuid = UUID(batch_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid batch ID format")
    
    result = await db.execute(
        select(SearchJobModel)
        .where(SearchJobModel.batch_id == batch_uuid)
        .order_by(SearchJobModel.batch_index)
    )
    jobs = result.scalars().all()
    
    if not jobs:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Calculate progress
    completed = sum(1 for j in jobs if j.status == "completed")
    failed = sum(1 for j in jobs if j.status == "failed")
    running = sum(1 for j in jobs if j.status == "running")
    pending = sum(1 for j in jobs if j.status == "pending")
    
    current_job_index = None
    for j in jobs:
        if j.status == "running":
            current_job_index = j.batch_index
            break
    
    # Build job list with essential info
    job_list = []
    for j in jobs:
        job_list.append({
            "job_id": str(j.id),
            "batch_index": j.batch_index,
            "batch_total": j.batch_total,
            "input_text": j.input_text,
            "dno_name": j.dno_name,
            "year": j.year,
            "data_type": j.data_type,
            "status": j.status,
            "current_step": j.current_step,
            "steps_history": j.steps_history or [],
            "error": j.error_message,
        })
    
    # Determine overall batch status
    if running > 0:
        batch_status = "running"
    elif pending > 0 and completed == 0 and failed == 0:
        batch_status = "pending"
    elif pending == 0 and running == 0:
        batch_status = "completed" if failed == 0 else "completed_with_errors"
    else:
        batch_status = "running"
    
    return {
        "batch_id": batch_id,
        "status": batch_status,
        "total_jobs": len(jobs),
        "completed": completed,
        "failed": failed,
        "running": running,
        "pending": pending,
        "progress_percent": int((completed + failed) / len(jobs) * 100) if jobs else 0,
        "current_job_index": current_job_index,
        "jobs": job_list,
    }


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
    "/jobs",
    summary="List All Search Jobs",
    description="Get all search jobs for Jobs page. Admins see all, users see their own."
)
async def list_search_jobs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    limit: int = Query(default=50, ge=1, le=200),
):
    """
    List all search jobs for the Jobs page.
    
    - Admins see all jobs
    - Regular users see only their own jobs
    - Jobs sorted by created_at (newest first) with queue position
    """
    # Build query
    query = select(SearchJobModel)
    
    # Admin sees all, regular users see only their own
    if current_user.role != "ADMIN":
        query = query.where(SearchJobModel.user_id == current_user.id)
    
    if status:
        query = query.where(SearchJobModel.status == status)
    
    query = query.order_by(SearchJobModel.created_at.desc()).limit(limit)
    
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    # Count total pending/running for queue positions
    queue_result = await db.execute(
        select(SearchJobModel)
        .where(SearchJobModel.status.in_(["pending", "running"]))
        .order_by(SearchJobModel.created_at.asc())
    )
    queue_jobs = list(queue_result.scalars().all())
    queue_positions = {str(j.id): idx + 1 for idx, j in enumerate(queue_jobs)}
    
    job_list = []
    for job in jobs:
        queue_pos = queue_positions.get(str(job.id))
        
        job_list.append({
            "job_id": str(job.id),
            "input_text": job.input_text,
            "status": job.status,
            "dno_name": job.dno_name,
            "year": job.year,
            "data_type": job.data_type,
            "current_step": job.current_step,
            "queue_position": queue_pos,
            "batch_id": str(job.batch_id) if job.batch_id else None,
            "batch_index": job.batch_index,
            "batch_total": job.batch_total,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "error": job.error_message,
        })
    
    return {
        "jobs": job_list,
        "total": len(job_list),
        "queue_length": len(queue_jobs),
    }

@router.get(
    "/history",
    response_model=list[SearchJobListItem],
    summary="Get Search History",
    description="Get list of past searches for the current user, grouped by batch."
)
async def get_search_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100),
):
    """
    Get past searches for the current user's history sidebar.
    
    Batches are grouped into a single entry showing progress (e.g., "3/8 completed").
    Non-batch jobs are returned individually.
    """
    result = await db.execute(
        select(SearchJobModel)
        .where(SearchJobModel.user_id == current_user.id)
        .order_by(SearchJobModel.created_at.desc())
        .limit(limit * 4)  # Fetch more to account for grouping
    )
    jobs = result.scalars().all()
    
    # Group by batch_id
    batches: dict[str, list] = {}
    individual_jobs = []
    
    for job in jobs:
        if job.batch_id:
            batch_key = str(job.batch_id)
            if batch_key not in batches:
                batches[batch_key] = []
            batches[batch_key].append(job)
        else:
            individual_jobs.append(job)
    
    # Build response
    items = []
    seen_batches = set()
    
    for job in jobs:
        if job.batch_id:
            batch_key = str(job.batch_id)
            if batch_key in seen_batches:
                continue
            seen_batches.add(batch_key)
            
            batch_jobs = batches[batch_key]
            batch_completed = sum(1 for j in batch_jobs if j.status in ("completed", "failed"))
            batch_total = batch_jobs[0].batch_total or len(batch_jobs)
            
            # Get unique DNO names
            dno_names = list(set(j.dno_name for j in batch_jobs if j.dno_name))
            
            # Determine overall batch status
            running = any(j.status == "running" for j in batch_jobs)
            all_done = all(j.status in ("completed", "failed") for j in batch_jobs)
            
            if all_done:
                batch_status = "completed"
            elif running:
                batch_status = "running"
            else:
                batch_status = "pending"
            
            # Use first job's created_at for ordering
            first_job = min(batch_jobs, key=lambda j: j.created_at)
            
            # Create display text
            if dno_names:
                display_text = ", ".join(dno_names[:2])
                if len(dno_names) > 2:
                    display_text += f" +{len(dno_names) - 2} more"
            else:
                display_text = f"Batch ({batch_total} jobs)"
            
            items.append(SearchJobListItem(
                job_id=batch_key,  # Use batch_id as job_id for navigation
                input_text=display_text,
                status=batch_status,
                created_at=first_job.created_at,
                completed_at=None,
                batch_id=batch_key,
                batch_total=batch_total,
                batch_completed=batch_completed,
                dno_names=dno_names,
            ))
        else:
            # Individual job (non-batch)
            items.append(SearchJobListItem(
                job_id=str(job.id),
                input_text=job.input_text,
                status=job.status,
                created_at=job.created_at,
                completed_at=job.completed_at,
            ))
    
    # Sort by created_at and limit
    items.sort(key=lambda x: x.created_at, reverse=True)
    return items[:limit]


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
