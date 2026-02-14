"""
Data endpoints for Netzentgelte and HLZF management.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import User as AuthUser
from app.core.auth import get_current_user
from app.core.models import APIResponse
from app.db import DNOModel, get_db

from .schemas import UpdateHLZFRequest, UpdateNetzentgelteRequest

router = APIRouter()


@router.get("/{dno_id}/data")
async def get_dno_data(
    dno_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
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

    # Query netzentgelte data
    netzentgelte_query = text("""
        SELECT id, voltage_level, year, leistung, arbeit, leistung_unter_2500h, arbeit_unter_2500h,
               verification_status, extraction_source, extraction_model, extraction_source_format,
               last_edited_by, last_edited_at, verified_by, verified_at, flagged_by, flagged_at, flag_reason
        FROM netzentgelte
        WHERE dno_id = :dno_id
        ORDER BY year DESC, voltage_level
    """)
    result = await db.execute(netzentgelte_query, {"dno_id": dno_id})
    netzentgelte_rows = result.fetchall()

    netzentgelte = []
    for row in netzentgelte_rows:
        netzentgelte.append({
            "id": row[0],
            "voltage_level": row[1],
            "year": row[2],
            "leistung": row[3],  # T >= 2500 h/a
            "arbeit": row[4],    # T >= 2500 h/a
            "leistung_unter_2500h": row[5],  # T < 2500 h/a
            "arbeit_unter_2500h": row[6],
            "verification_status": row[7],
            # Extraction source fields
            "extraction_source": row[8],
            "extraction_model": row[9],
            "extraction_source_format": row[10],
            "last_edited_by": row[11],
            "last_edited_at": row[12].isoformat() if row[12] else None,
            # Verification/flag fields
            "verified_by": row[13],
            "verified_at": row[14].isoformat() if row[14] else None,
            "flagged_by": row[15],
            "flagged_at": row[16].isoformat() if row[16] else None,
            "flag_reason": row[17],
        })

    # Query HLZF data
    hlzf_query = text("""
        SELECT id, voltage_level, year, winter, fruehling, sommer, herbst,
               verification_status, extraction_source, extraction_model, extraction_source_format,
               last_edited_by, last_edited_at, verified_by, verified_at, flagged_by, flagged_at, flag_reason
        FROM hlzf
        WHERE dno_id = :dno_id
        ORDER BY year DESC, voltage_level
    """)
    result = await db.execute(hlzf_query, {"dno_id": dno_id})
    hlzf_rows = result.fetchall()

    # Import time parsing function from search module
    from app.api.routes.search import _parse_hlzf_times

    hlzf = []
    for row in hlzf_rows:
        winter_val = row[3]
        fruehling_val = row[4]
        sommer_val = row[5]
        herbst_val = row[6]

        hlzf.append({
            "id": row[0],
            "voltage_level": row[1],
            "year": row[2],
            "winter": winter_val,
            "fruehling": fruehling_val,
            "sommer": sommer_val,
            "herbst": herbst_val,
            # Parsed time ranges
            "winter_ranges": [{"start": r.start, "end": r.end} for r in (_parse_hlzf_times(winter_val) or [])],
            "fruehling_ranges": [{"start": r.start, "end": r.end} for r in (_parse_hlzf_times(fruehling_val) or [])],
            "sommer_ranges": [{"start": r.start, "end": r.end} for r in (_parse_hlzf_times(sommer_val) or [])],
            "herbst_ranges": [{"start": r.start, "end": r.end} for r in (_parse_hlzf_times(herbst_val) or [])],
            "verification_status": row[7],
            # Extraction source fields
            "extraction_source": row[8],
            "extraction_model": row[9],
            "extraction_source_format": row[10],
            "last_edited_by": row[11],
            "last_edited_at": row[12].isoformat() if row[12] else None,
            # Verification/flag fields
            "verified_by": row[13],
            "verified_at": row[14].isoformat() if row[14] else None,
            "flagged_by": row[15],
            "flagged_at": row[16].isoformat() if row[16] else None,
            "flag_reason": row[17],
        })

    return APIResponse(
        success=True,
        data={
            "dno": {
                "id": str(dno.id),
                "name": dno.name,
            },
            "netzentgelte": netzentgelte,
            "hlzf": hlzf,
        },
    )


@router.patch("/{dno_id}/netzentgelte/{record_id}")
async def update_netzentgelte(
    dno_id: int,
    record_id: int,
    request: UpdateNetzentgelteRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> APIResponse:
    """Update a Netzentgelte record (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    from app.db import NetzentgelteModel

    query = select(NetzentgelteModel).where(
        NetzentgelteModel.id == record_id,
        NetzentgelteModel.dno_id == dno_id,
    )
    result = await db.execute(query)
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Record not found",
        )

    # Update only provided fields
    if request.leistung is not None:
        record.leistung = request.leistung
    if request.arbeit is not None:
        record.arbeit = request.arbeit
    if request.leistung_unter_2500h is not None:
        record.leistung_unter_2500h = request.leistung_unter_2500h
    if request.arbeit_unter_2500h is not None:
        record.arbeit_unter_2500h = request.arbeit_unter_2500h

    # Track manual edit
    record.extraction_source = "manual"
    record.last_edited_by = current_user.id or current_user.email
    record.last_edited_at = datetime.now(UTC)

    await db.commit()

    return APIResponse(
        success=True,
        message="Record updated successfully",
        data={"id": str(record.id)},
    )


@router.delete("/{dno_id}/netzentgelte/{record_id}")
async def delete_netzentgelte(
    dno_id: int,
    record_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> APIResponse:
    """Delete a Netzentgelte record (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    from app.db import NetzentgelteModel

    query = select(NetzentgelteModel).where(
        NetzentgelteModel.id == record_id,
        NetzentgelteModel.dno_id == dno_id,
    )
    result = await db.execute(query)
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Record not found",
        )

    await db.delete(record)
    await db.commit()

    return APIResponse(
        success=True,
        message="Record deleted successfully",
    )


@router.patch("/{dno_id}/hlzf/{record_id}")
async def update_hlzf(
    dno_id: int,
    record_id: int,
    request: UpdateHLZFRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> APIResponse:
    """Update an HLZF record (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    from app.db import HLZFModel

    query = select(HLZFModel).where(
        HLZFModel.id == record_id,
        HLZFModel.dno_id == dno_id,
    )
    result = await db.execute(query)
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Record not found",
        )

    # Update only provided fields
    if request.winter is not None:
        record.winter = request.winter if request.winter != "" else None
    if request.fruehling is not None:
        record.fruehling = request.fruehling if request.fruehling != "" else None
    if request.sommer is not None:
        record.sommer = request.sommer if request.sommer != "" else None
    if request.herbst is not None:
        record.herbst = request.herbst if request.herbst != "" else None

    # Track manual edit
    record.extraction_source = "manual"
    record.last_edited_by = current_user.id or current_user.email
    record.last_edited_at = datetime.now(UTC)

    await db.commit()

    return APIResponse(
        success=True,
        message="Record updated successfully",
        data={"id": str(record.id)},
    )


@router.delete("/{dno_id}/hlzf/{record_id}")
async def delete_hlzf(
    dno_id: int,
    record_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> APIResponse:
    """Delete an HLZF record (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    from app.db import HLZFModel

    query = select(HLZFModel).where(
        HLZFModel.id == record_id,
        HLZFModel.dno_id == dno_id,
    )
    result = await db.execute(query)
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Record not found",
        )

    await db.delete(record)
    await db.commit()

    return APIResponse(
        success=True,
        message="Record deleted successfully",
    )
