"""
Data verification routes.

Provides endpoints for:
- Verifying data as correct (any authenticated user)
- Flagging data as incorrect (any authenticated user)
- Removing flags (Maintainer/Admin only)
"""

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import User, get_current_user, require_maintainer_or_admin
from app.core.models import VerificationStatus
from app.db import get_db
from app.db.models import HLZFModel, NetzentgelteModel

logger = structlog.get_logger()

router = APIRouter()


# ==============================================================================
# Request/Response Schemas
# ==============================================================================


class FlagRequest(BaseModel):
    """Request to flag data as incorrect."""
    reason: str = Field(..., min_length=10, max_length=500, description="Reason why the data is incorrect")


class VerifyRequest(BaseModel):
    """Optional notes when verifying data."""
    notes: str | None = Field(None, max_length=500, description="Optional verification notes")


class VerificationResponse(BaseModel):
    """Response after verification action."""
    id: int
    verification_status: str
    verified_by: str | None = None
    verified_at: datetime | None = None
    verification_notes: str | None = None
    flagged_by: str | None = None
    flagged_at: datetime | None = None
    flag_reason: str | None = None
    message: str


# ==============================================================================
# Netzentgelte Verification Endpoints
# ==============================================================================


@router.post(
    "/netzentgelte/{record_id}/verify",
    response_model=VerificationResponse,
    summary="Verify Netzentgelte record",
    description="Mark a Netzentgelte record as verified. Any authenticated user can verify data.",
)
async def verify_netzentgelte(
    record_id: int,
    request: VerifyRequest | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VerificationResponse:
    """Mark a Netzentgelte record as verified."""
    result = await db.execute(
        select(NetzentgelteModel).where(NetzentgelteModel.id == record_id)
    )
    record = result.scalar_one_or_none()
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Netzentgelte record {record_id} not found"
        )
    
    # Update verification status
    record.verification_status = VerificationStatus.VERIFIED.value
    record.verified_by = user.id
    record.verified_at = datetime.now(timezone.utc)
    record.verification_notes = request.notes if request else None
    
    # Clear any existing flags when verifying
    record.flagged_by = None
    record.flagged_at = None
    record.flag_reason = None
    
    await db.commit()
    
    logger.info(
        "Netzentgelte record verified",
        record_id=record_id,
        user_id=user.id,
        user_email=user.email,
    )
    
    return VerificationResponse(
        id=record.id,
        verification_status=record.verification_status,
        verified_by=record.verified_by,
        verified_at=record.verified_at,
        verification_notes=record.verification_notes,
        flagged_by=record.flagged_by,
        flagged_at=record.flagged_at,
        flag_reason=record.flag_reason,
        message="Record verified successfully",
    )


@router.post(
    "/netzentgelte/{record_id}/flag",
    response_model=VerificationResponse,
    summary="Flag Netzentgelte record as incorrect",
    description="Flag a Netzentgelte record as potentially incorrect. Any authenticated user can flag data.",
)
async def flag_netzentgelte(
    record_id: int,
    request: FlagRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VerificationResponse:
    """Flag a Netzentgelte record as potentially incorrect."""
    result = await db.execute(
        select(NetzentgelteModel).where(NetzentgelteModel.id == record_id)
    )
    record = result.scalar_one_or_none()
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Netzentgelte record {record_id} not found"
        )
    
    # Update status to flagged
    record.verification_status = VerificationStatus.FLAGGED.value
    record.flagged_by = user.id
    record.flagged_at = datetime.now(timezone.utc)
    record.flag_reason = request.reason
    
    await db.commit()
    
    logger.info(
        "Netzentgelte record flagged",
        record_id=record_id,
        user_id=user.id,
        user_email=user.email,
        reason=request.reason,
    )
    
    return VerificationResponse(
        id=record.id,
        verification_status=record.verification_status,
        verified_by=record.verified_by,
        verified_at=record.verified_at,
        verification_notes=record.verification_notes,
        flagged_by=record.flagged_by,
        flagged_at=record.flagged_at,
        flag_reason=record.flag_reason,
        message="Record flagged successfully",
    )


@router.delete(
    "/netzentgelte/{record_id}/flag",
    response_model=VerificationResponse,
    summary="Remove flag from Netzentgelte record",
    description="Remove a flag from a Netzentgelte record. Only Maintainers and Admins can remove flags.",
)
async def unflag_netzentgelte(
    record_id: int,
    user: User = Depends(require_maintainer_or_admin),
    db: AsyncSession = Depends(get_db),
) -> VerificationResponse:
    """Remove a flag from a Netzentgelte record (Maintainer/Admin only)."""
    result = await db.execute(
        select(NetzentgelteModel).where(NetzentgelteModel.id == record_id)
    )
    record = result.scalar_one_or_none()
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Netzentgelte record {record_id} not found"
        )
    
    if record.verification_status != VerificationStatus.FLAGGED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Record is not flagged"
        )
    
    # Reset to unverified status
    record.verification_status = VerificationStatus.UNVERIFIED.value
    record.flagged_by = None
    record.flagged_at = None
    record.flag_reason = None
    
    await db.commit()
    
    logger.info(
        "Netzentgelte record unflagged",
        record_id=record_id,
        user_id=user.id,
        user_email=user.email,
    )
    
    return VerificationResponse(
        id=record.id,
        verification_status=record.verification_status,
        verified_by=record.verified_by,
        verified_at=record.verified_at,
        verification_notes=record.verification_notes,
        flagged_by=record.flagged_by,
        flagged_at=record.flagged_at,
        flag_reason=record.flag_reason,
        message="Flag removed successfully",
    )


# ==============================================================================
# HLZF Verification Endpoints
# ==============================================================================


@router.post(
    "/hlzf/{record_id}/verify",
    response_model=VerificationResponse,
    summary="Verify HLZF record",
    description="Mark an HLZF record as verified. Any authenticated user can verify data.",
)
async def verify_hlzf(
    record_id: int,
    request: VerifyRequest | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VerificationResponse:
    """Mark an HLZF record as verified."""
    result = await db.execute(
        select(HLZFModel).where(HLZFModel.id == record_id)
    )
    record = result.scalar_one_or_none()
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HLZF record {record_id} not found"
        )
    
    # Update verification status
    record.verification_status = VerificationStatus.VERIFIED.value
    record.verified_by = user.id
    record.verified_at = datetime.now(timezone.utc)
    
    # Clear any existing flags when verifying
    record.flagged_by = None
    record.flagged_at = None
    record.flag_reason = None
    
    await db.commit()
    
    logger.info(
        "HLZF record verified",
        record_id=record_id,
        user_id=user.id,
        user_email=user.email,
    )
    
    return VerificationResponse(
        id=record.id,
        verification_status=record.verification_status,
        verified_by=record.verified_by,
        verified_at=record.verified_at,
        verification_notes=None,  # HLZF model doesn't have verification_notes
        flagged_by=record.flagged_by,
        flagged_at=record.flagged_at,
        flag_reason=record.flag_reason,
        message="Record verified successfully",
    )


@router.post(
    "/hlzf/{record_id}/flag",
    response_model=VerificationResponse,
    summary="Flag HLZF record as incorrect",
    description="Flag an HLZF record as potentially incorrect. Any authenticated user can flag data.",
)
async def flag_hlzf(
    record_id: int,
    request: FlagRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VerificationResponse:
    """Flag an HLZF record as potentially incorrect."""
    result = await db.execute(
        select(HLZFModel).where(HLZFModel.id == record_id)
    )
    record = result.scalar_one_or_none()
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HLZF record {record_id} not found"
        )
    
    # Update status to flagged
    record.verification_status = VerificationStatus.FLAGGED.value
    record.flagged_by = user.id
    record.flagged_at = datetime.now(timezone.utc)
    record.flag_reason = request.reason
    
    await db.commit()
    
    logger.info(
        "HLZF record flagged",
        record_id=record_id,
        user_id=user.id,
        user_email=user.email,
        reason=request.reason,
    )
    
    return VerificationResponse(
        id=record.id,
        verification_status=record.verification_status,
        verified_by=record.verified_by,
        verified_at=record.verified_at,
        verification_notes=None,
        flagged_by=record.flagged_by,
        flagged_at=record.flagged_at,
        flag_reason=record.flag_reason,
        message="Record flagged successfully",
    )


@router.delete(
    "/hlzf/{record_id}/flag",
    response_model=VerificationResponse,
    summary="Remove flag from HLZF record",
    description="Remove a flag from an HLZF record. Only Maintainers and Admins can remove flags.",
)
async def unflag_hlzf(
    record_id: int,
    user: User = Depends(require_maintainer_or_admin),
    db: AsyncSession = Depends(get_db),
) -> VerificationResponse:
    """Remove a flag from an HLZF record (Maintainer/Admin only)."""
    result = await db.execute(
        select(HLZFModel).where(HLZFModel.id == record_id)
    )
    record = result.scalar_one_or_none()
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HLZF record {record_id} not found"
        )
    
    if record.verification_status != VerificationStatus.FLAGGED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Record is not flagged"
        )
    
    # Reset to unverified status
    record.verification_status = VerificationStatus.UNVERIFIED.value
    record.flagged_by = None
    record.flagged_at = None
    record.flag_reason = None
    
    await db.commit()
    
    logger.info(
        "HLZF record unflagged",
        record_id=record_id,
        user_id=user.id,
        user_email=user.email,
    )
    
    return VerificationResponse(
        id=record.id,
        verification_status=record.verification_status,
        verified_by=record.verified_by,
        verified_at=record.verified_at,
        verification_notes=None,
        flagged_by=record.flagged_by,
        flagged_at=record.flagged_at,
        flag_reason=record.flag_reason,
        message="Flag removed successfully",
    )
