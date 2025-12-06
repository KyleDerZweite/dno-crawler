"""
Admin routes - requires admin role.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_admin_user
from app.core.models import APIResponse, UserRole
from app.db import CrawlJobModel, DNOModel, NetzentgelteModel, UserModel, get_db

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
    
    query = query.order_by(CrawlJobModel.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    return APIResponse(
        success=True,
        data=[
            {
                "id": str(job.id),
                "dno_id": str(job.dno_id),
                "year": job.year,
                "data_type": job.data_type,
                "status": job.status,
                "progress": job.progress,
                "current_step": job.current_step,
                "error_message": job.error_message,
                "created_at": job.created_at.isoformat() if job.created_at else None,
            }
            for job in jobs
        ],
    )
