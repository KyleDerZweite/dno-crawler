"""
Admin routes - requires admin role.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_admin_user
from app.core.models import APIResponse, UserRole
from app.db import (
    CrawlJobModel,
    DNOModel,
    NetzentgelteModel,
    UserModel,
    SessionModel,
    APIKeyModel,
    get_db,
)

router = APIRouter()


class ApproveUserRequest(BaseModel):
    approved: bool
    reason: str | None = None


class UpdateUserRoleRequest(BaseModel):
    role: UserRole


@router.get("/dashboard")
async def admin_dashboard(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[UserModel, Depends(get_admin_user)],
) -> APIResponse:
    """Get admin dashboard statistics."""
    # Count DNOs
    dno_count = await db.scalar(select(func.count(DNOModel.id)))
    
    # Count users by role
    pending_users = await db.scalar(
        select(func.count(UserModel.id)).where(UserModel.role == UserRole.PENDING.value)
    )
    active_users = await db.scalar(
        select(func.count(UserModel.id)).where(UserModel.role == UserRole.USER.value)
    )
    admin_users = await db.scalar(
        select(func.count(UserModel.id)).where(UserModel.role == UserRole.ADMIN.value)
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
            },
            "users": {
                "pending": pending_users or 0,
                "active": active_users or 0,
                "admins": admin_users or 0,
                "total": (pending_users or 0) + (active_users or 0) + (admin_users or 0),
            },
            "jobs": {
                "pending": pending_jobs or 0,
                "running": running_jobs or 0,
            },
        },
    )


@router.get("/users")
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[UserModel, Depends(get_admin_user)],
    role: UserRole | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> APIResponse:
    """List all users."""
    query = select(UserModel)
    
    if role:
        query = query.where(UserModel.role == role.value)
    
    query = query.order_by(UserModel.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return APIResponse(
        success=True,
        data=[
            {
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "is_active": user.is_active,
                "email_verified": user.email_verified,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            }
            for user in users
        ],
    )


@router.get("/users/pending")
async def list_pending_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[UserModel, Depends(get_admin_user)],
) -> APIResponse:
    """List users awaiting approval."""
    query = (
        select(UserModel)
        .where(UserModel.role == UserRole.PENDING.value)
        .order_by(UserModel.created_at.asc())
    )
    result = await db.execute(query)
    users = result.scalars().all()
    
    return APIResponse(
        success=True,
        data=[
            {
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            }
            for user in users
        ],
    )


@router.post("/users/{user_id}/approve")
async def approve_user(
    user_id: int,
    request: ApproveUserRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[UserModel, Depends(get_admin_user)],
) -> APIResponse:
    """Approve or reject a pending user."""
    query = select(UserModel).where(UserModel.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    if user.role != UserRole.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not pending approval",
        )
    
    if request.approved:
        user.role = UserRole.USER.value
        user.verification_status = "approved"
        user.approved_by = admin.id
        message = "User approved successfully"
    else:
        user.is_active = False
        user.verification_status = "rejected"
        message = "User rejected"
    
    await db.commit()
    
    return APIResponse(success=True, message=message)


@router.patch("/users/{user_id}/role")
async def update_user_role(
    user_id: int,
    request: UpdateUserRoleRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[UserModel, Depends(get_admin_user)],
) -> APIResponse:
    """Update a user's role."""
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own role",
        )
    
    query = select(UserModel).where(UserModel.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    user.role = request.role.value
    await db.commit()
    
    return APIResponse(
        success=True,
        message=f"User role updated to {request.role.value}",
    )


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[UserModel, Depends(get_admin_user)],
) -> APIResponse:
    """Delete a user."""
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself",
        )
    
    query = select(UserModel).where(UserModel.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Remove all sessions and api keys related to this user to avoid FK/NULL constraint issues
    await db.execute(delete(SessionModel).where(SessionModel.user_id == user_id))
    await db.execute(delete(APIKeyModel).where(APIKeyModel.user_id == user_id))
    await db.delete(user)
    await db.commit()
    
    return APIResponse(success=True, message="User deleted")


@router.get("/jobs")
async def list_all_jobs(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[UserModel, Depends(get_admin_user)],
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> APIResponse:
    """List all crawl jobs."""
    query = select(CrawlJobModel)
    
    if status_filter:
        query = query.where(CrawlJobModel.status == status_filter)
    
    # Get total count
    count_query = select(func.count(CrawlJobModel.id))
    if status_filter:
        count_query = count_query.where(CrawlJobModel.status == status_filter)
    total = await db.scalar(count_query) or 0
    
    query = query.order_by(CrawlJobModel.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    # Fetch DNO names for display
    dno_ids = list(set(job.dno_id for job in jobs))
    dno_query = select(DNOModel).where(DNOModel.id.in_(dno_ids))
    dno_result = await db.execute(dno_query)
    dnos = {dno.id: dno for dno in dno_result.scalars().all()}
    
    return APIResponse(
        success=True,
        data=[
            {
                "id": str(job.id),
                "dno_id": str(job.dno_id),
                "dno_name": dnos.get(job.dno_id).name if dnos.get(job.dno_id) else None,
                "user_id": str(job.user_id) if job.user_id else None,
                "year": job.year,
                "data_type": job.data_type,
                "status": job.status,
                "progress": job.progress,
                "current_step": job.current_step,
                "error_message": job.error_message,
                "priority": job.priority,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "created_at": job.created_at.isoformat() if job.created_at else None,
            }
            for job in jobs
        ],
        meta={
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page,
        },
    )


@router.get("/jobs/{job_id}")
async def get_job_details(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[UserModel, Depends(get_admin_user)],
) -> APIResponse:
    """Get detailed information about a specific job including steps."""
    from sqlalchemy.orm import selectinload
    
    query = select(CrawlJobModel).where(CrawlJobModel.id == job_id).options(
        selectinload(CrawlJobModel.steps)
    )
    result = await db.execute(query)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    
    # Get DNO info
    dno_query = select(DNOModel).where(DNOModel.id == job.dno_id)
    dno_result = await db.execute(dno_query)
    dno = dno_result.scalar_one_or_none()
    
    return APIResponse(
        success=True,
        data={
            "id": str(job.id),
            "dno_id": str(job.dno_id),
            "dno_name": dno.name if dno else None,
            "dno_slug": dno.slug if dno else None,
            "user_id": str(job.user_id) if job.user_id else None,
            "year": job.year,
            "data_type": job.data_type,
            "status": job.status,
            "progress": job.progress,
            "current_step": job.current_step,
            "error_message": job.error_message,
            "priority": job.priority,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
            "steps": [
                {
                    "id": str(step.id),
                    "step_name": step.step_name,
                    "status": step.status,
                    "started_at": step.started_at.isoformat() if step.started_at else None,
                    "completed_at": step.completed_at.isoformat() if step.completed_at else None,
                    "duration_seconds": step.duration_seconds,
                    "details": step.details,
                }
                for step in sorted(job.steps, key=lambda s: s.created_at or s.id)
            ],
        },
    )


class CreateJobRequest(BaseModel):
    """Request to create a standalone job."""
    dno_id: int
    year: int
    data_type: str = "all"
    priority: int = 5
    job_type: str = "crawl"  # crawl, rescan_pdf, rerun_extraction
    target_file_id: int | None = None  # For rescan_pdf jobs


@router.post("/jobs")
async def create_standalone_job(
    request: CreateJobRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[UserModel, Depends(get_admin_user)],
) -> APIResponse:
    """Create a standalone job (admin only)."""
    # Verify DNO exists
    dno_query = select(DNOModel).where(DNOModel.id == request.dno_id)
    dno_result = await db.execute(dno_query)
    dno = dno_result.scalar_one_or_none()
    
    if not dno:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DNO not found",
        )
    
    # Create job based on type
    job = CrawlJobModel(
        user_id=admin.id,
        dno_id=request.dno_id,
        year=request.year,
        data_type=request.data_type,
        priority=request.priority,
        current_step=f"Created ({request.job_type})",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    return APIResponse(
        success=True,
        message=f"Job created for {dno.name} ({request.year})",
        data={
            "job_id": str(job.id),
            "dno_id": str(request.dno_id),
            "dno_name": dno.name,
            "year": request.year,
            "data_type": request.data_type,
            "job_type": request.job_type,
            "status": job.status,
        },
    )


@router.post("/jobs/{job_id}/rerun")
async def rerun_job(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[UserModel, Depends(get_admin_user)],
) -> APIResponse:
    """Rerun a failed or completed job."""
    query = select(CrawlJobModel).where(CrawlJobModel.id == job_id)
    result = await db.execute(query)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    
    if job.status in ["pending", "running"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot rerun a job that is still pending or running",
        )
    
    # Create a new job based on the old one
    new_job = CrawlJobModel(
        user_id=admin.id,
        dno_id=job.dno_id,
        year=job.year,
        data_type=job.data_type,
        priority=job.priority,
        current_step=f"Rerun of job {job_id}",
    )
    db.add(new_job)
    await db.commit()
    await db.refresh(new_job)
    
    return APIResponse(
        success=True,
        message=f"Job rerun created",
        data={
            "job_id": str(new_job.id),
            "original_job_id": str(job_id),
            "status": new_job.status,
        },
    )


@router.delete("/jobs/{job_id}")
async def cancel_job(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[UserModel, Depends(get_admin_user)],
) -> APIResponse:
    """Cancel a pending job or mark a running job for cancellation."""
    query = select(CrawlJobModel).where(CrawlJobModel.id == job_id)
    result = await db.execute(query)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    
    if job.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel a completed job",
        )
    
    job.status = "cancelled"
    job.error_message = f"Cancelled by admin {admin.email}"
    await db.commit()
    
    return APIResponse(
        success=True,
        message="Job cancelled",
    )
