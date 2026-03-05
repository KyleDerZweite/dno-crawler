"""Data verification routes."""

from datetime import UTC, datetime
from typing import Any

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


class FlagRequest(BaseModel):
    """Request to flag data as incorrect."""

    reason: str = Field(
        ..., min_length=10, max_length=500, description="Reason why the data is incorrect"
    )


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


async def _get_record_or_404(
    *,
    db: AsyncSession,
    model_cls: Any,
    record_id: int,
    label: str,
):
    result = await db.execute(select(model_cls).where(model_cls.id == record_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{label} record {record_id} not found",
        )
    return record


def _to_verification_response(record: Any, message: str) -> VerificationResponse:
    return VerificationResponse(
        id=record.id,
        verification_status=record.verification_status,
        verified_by=record.verified_by,
        verified_at=record.verified_at,
        verification_notes=record.verification_notes,
        flagged_by=record.flagged_by,
        flagged_at=record.flagged_at,
        flag_reason=record.flag_reason,
        message=message,
    )


async def _verify_record(
    *,
    db: AsyncSession,
    model_cls: Any,
    record_id: int,
    label: str,
    user: User,
    request: VerifyRequest | None,
) -> VerificationResponse:
    record = await _get_record_or_404(db=db, model_cls=model_cls, record_id=record_id, label=label)

    record.verification_status = VerificationStatus.VERIFIED.value
    record.verified_by = user.id
    record.verified_at = datetime.now(UTC)
    record.verification_notes = request.notes if request else None
    record.flagged_by = None
    record.flagged_at = None
    record.flag_reason = None

    await db.commit()

    logger.info(
        "verification.record_verified",
        record_id=record_id,
        user_id=user.id,
        label=label.lower(),
        notes_present=bool(request and request.notes),
    )
    return _to_verification_response(record, "Record verified successfully")


async def _flag_record(
    *,
    db: AsyncSession,
    model_cls: Any,
    record_id: int,
    label: str,
    user: User,
    request: FlagRequest,
) -> VerificationResponse:
    record = await _get_record_or_404(db=db, model_cls=model_cls, record_id=record_id, label=label)

    record.verification_status = VerificationStatus.FLAGGED.value
    record.flagged_by = user.id
    record.flagged_at = datetime.now(UTC)
    record.flag_reason = request.reason

    await db.commit()

    logger.info(
        "verification.record_flagged",
        record_id=record_id,
        user_id=user.id,
        label=label.lower(),
        reason_present=bool(request.reason),
        reason_redacted=True,
    )
    return _to_verification_response(record, "Record flagged successfully")


async def _unflag_record(
    *,
    db: AsyncSession,
    model_cls: Any,
    record_id: int,
    label: str,
    user: User,
) -> VerificationResponse:
    record = await _get_record_or_404(db=db, model_cls=model_cls, record_id=record_id, label=label)

    if record.verification_status != VerificationStatus.FLAGGED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Record is not flagged")

    record.verification_status = VerificationStatus.UNVERIFIED.value
    record.flagged_by = None
    record.flagged_at = None
    record.flag_reason = None

    await db.commit()

    logger.info(
        "verification.record_unflagged",
        record_id=record_id,
        user_id=user.id,
        label=label.lower(),
    )
    return _to_verification_response(record, "Flag removed successfully")


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
    return await _verify_record(
        db=db,
        model_cls=NetzentgelteModel,
        record_id=record_id,
        label="Netzentgelte",
        user=user,
        request=request,
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
    return await _flag_record(
        db=db,
        model_cls=NetzentgelteModel,
        record_id=record_id,
        label="Netzentgelte",
        user=user,
        request=request,
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
    return await _unflag_record(
        db=db,
        model_cls=NetzentgelteModel,
        record_id=record_id,
        label="Netzentgelte",
        user=user,
    )


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
    return await _verify_record(
        db=db,
        model_cls=HLZFModel,
        record_id=record_id,
        label="HLZF",
        user=user,
        request=request,
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
    return await _flag_record(
        db=db,
        model_cls=HLZFModel,
        record_id=record_id,
        label="HLZF",
        user=user,
        request=request,
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
    return await _unflag_record(
        db=db,
        model_cls=HLZFModel,
        record_id=record_id,
        label="HLZF",
        user=user,
    )
