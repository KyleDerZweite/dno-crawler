"""
Crawl API routes for SearchAgent.

Provides endpoints for:
- Address-based DNO resolution and PDF extraction
- Direct batch DNO processing
"""

from datetime import datetime
from typing import Optional

import structlog
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.models import User

logger = structlog.get_logger()
router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class AddressCrawlRequest(BaseModel):
    """Request to crawl DNO data based on address."""
    zip: str = Field(..., description="German postal code (PLZ)", example="50667")
    city: str = Field(..., description="City name", example="Köln")
    street: str = Field(..., description="Street name", example="Domkloster")
    year: int = Field(default=2025, ge=2020, le=2030, description="Year to fetch data for")


class BatchDNORequest(BaseModel):
    """Request to crawl DNO data for a list of DNO names."""
    dno_names: list[str] = Field(
        ..., 
        min_length=1, 
        max_length=50,
        description="List of DNO names to process",
        example=["RheinEnergie", "Netze BW"]
    )
    year: int = Field(default=2025, ge=2020, le=2030, description="Year to fetch data for")


class CrawlJobResponse(BaseModel):
    """Response after queueing a crawl job."""
    job_id: str
    status: str = "queued"
    message: str
    queued_at: datetime


class CrawlStatusResponse(BaseModel):
    """Response for crawl job status."""
    job_id: str
    status: str
    result: Optional[dict] = None


# ============================================================================
# Endpoints
# ============================================================================

@router.post(
    "/address",
    response_model=CrawlJobResponse,
    summary="Crawl DNO by Address",
    description="Queue a job to resolve DNO from address and extract Netzentgelte data."
)
async def crawl_by_address(
    request: AddressCrawlRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Queue a crawl job based on address.
    
    Flow:
    1. Job queued to Redis (returns immediately)
    2. Worker picks up job (sequential, one at a time)
    3. SearchAgent resolves DNO from address
    4. SearchAgent finds and processes PDF
    """
    log = logger.bind(user=current_user.email, zip=request.zip)
    log.info("Queueing address crawl job")
    
    try:
        # Connect to Redis and queue the job
        redis_pool = await create_pool(
            RedisSettings.from_dsn(str(settings.redis_url))
        )
        
        job = await redis_pool.enqueue_job(
            "job_process_search_request",
            {
                "type": "address",
                "zip": request.zip,
                "city": request.city,
                "street": request.street,
                "year": request.year,
            }
        )
        
        await redis_pool.close()
        
        log.info("Job queued", job_id=job.job_id)
        
        return CrawlJobResponse(
            job_id=job.job_id,
            status="queued",
            message=f"Crawl job queued for {request.zip} {request.city}",
            queued_at=datetime.utcnow(),
        )
        
    except Exception as e:
        log.error("Failed to queue job", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to queue job: {str(e)}")


@router.post(
    "/dno",
    response_model=CrawlJobResponse,
    summary="Crawl DNO Batch",
    description="Queue a batch job to process multiple DNOs directly."
)
async def crawl_dno_batch(
    request: BatchDNORequest,
    current_user: User = Depends(get_current_user),
):
    """
    Queue a batch crawl job for multiple DNOs.
    
    Flow:
    1. Job queued to Redis (returns immediately)
    2. Worker processes each DNO sequentially with delays
    3. SearchAgent finds and processes PDF for each DNO
    """
    log = logger.bind(user=current_user.email, count=len(request.dno_names))
    log.info("Queueing batch DNO crawl job")
    
    try:
        redis_pool = await create_pool(
            RedisSettings.from_dsn(str(settings.redis_url))
        )
        
        job = await redis_pool.enqueue_job(
            "job_process_search_request",
            {
                "type": "batch_dno",
                "dno_names": request.dno_names,
                "year": request.year,
            }
        )
        
        await redis_pool.close()
        
        log.info("Batch job queued", job_id=job.job_id)
        
        return CrawlJobResponse(
            job_id=job.job_id,
            status="queued",
            message=f"Batch crawl job queued for {len(request.dno_names)} DNOs",
            queued_at=datetime.utcnow(),
        )
        
    except Exception as e:
        log.error("Failed to queue batch job", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to queue job: {str(e)}")


@router.get(
    "/status/{job_id}",
    response_model=CrawlStatusResponse,
    summary="Get Crawl Job Status",
    description="Check the status of a queued crawl job."
)
async def get_crawl_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get the status and result of a crawl job."""
    log = logger.bind(user=current_user.email, job_id=job_id)
    
    try:
        from arq.jobs import Job
        
        redis_pool = await create_pool(
            RedisSettings.from_dsn(str(settings.redis_url))
        )
        
        job = Job(job_id=job_id, redis=redis_pool)
        status = await job.status()
        result = await job.result(timeout=0, poll_delay=0)
        
        await redis_pool.close()
        
        return CrawlStatusResponse(
            job_id=job_id,
            status=status.value if hasattr(status, 'value') else str(status),
            result=result if result else None,
        )
        
    except Exception as e:
        log.error("Failed to get job status", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")
