"""
Import/Export endpoints for DNO data.
"""

import json
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, User as AuthUser
from app.core.models import APIResponse
from app.db import DNOModel, get_db

from .schemas import ImportRequest


router = APIRouter()


@router.get("/{dno_id}/export")
async def export_dno_data(
    dno_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    data_types: list[str] = Query(["netzentgelte", "hlzf"]),
    years: list[int] | None = Query(None),
    include_metadata: bool = Query(True),
) -> Response:
    """
    Export DNO data as downloadable JSON file.
    
    Available to all authenticated users.
    
    Args:
        dno_id: DNO ID
        data_types: Data types to export (netzentgelte, hlzf)
        years: Optional year filter
        include_metadata: Include DNO metadata in export
    
    Returns:
        JSON file download
    """
    from app.db.models import NetzentgelteModel, HLZFModel
    
    # Get DNO
    dno = await db.get(DNOModel, dno_id)
    if not dno:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DNO not found")
    
    export_data = {
        "export_version": "1.0",
        "exported_at": datetime.now().isoformat(),
        "exported_by": current_user.email,
    }
    
    # Include metadata if requested
    if include_metadata:
        export_data["dno"] = {
            "name": dno.name,
            "slug": dno.slug,
            "official_name": dno.official_name,
            "region": dno.region,
            "website": dno.website,
            "description": dno.description,
        }
    
    # Export Netzentgelte
    if "netzentgelte" in data_types:
        query = select(NetzentgelteModel).where(NetzentgelteModel.dno_id == dno_id)
        if years:
            query = query.where(NetzentgelteModel.year.in_(years))
        result = await db.execute(query)
        netz_records = result.scalars().all()
        
        export_data["netzentgelte"] = [
            {
                "year": r.year,
                "voltage_level": r.voltage_level,
                "leistung": float(r.leistung) if r.leistung else None,
                "arbeit": float(r.arbeit) if r.arbeit else None,
                "leistung_unter_2500h": float(r.leistung_unter_2500h) if r.leistung_unter_2500h else None,
                "arbeit_unter_2500h": float(r.arbeit_unter_2500h) if r.arbeit_unter_2500h else None,
                "verification_status": r.verification_status,
                "extraction_source": r.extraction_source,
            }
            for r in netz_records
        ]
    
    # Export HLZF
    if "hlzf" in data_types:
        query = select(HLZFModel).where(HLZFModel.dno_id == dno_id)
        if years:
            query = query.where(HLZFModel.year.in_(years))
        result = await db.execute(query)
        hlzf_records = result.scalars().all()
        
        export_data["hlzf"] = [
            {
                "year": r.year,
                "voltage_level": r.voltage_level,
                "winter": r.winter,
                "fruehling": r.fruehling,
                "sommer": r.sommer,
                "herbst": r.herbst,
                "verification_status": r.verification_status,
                "extraction_source": r.extraction_source,
            }
            for r in hlzf_records
        ]
    
    # Generate filename
    filename = f"{dno.slug}-export-{datetime.now().strftime('%Y%m%d')}.json"
    
    return Response(
        content=json.dumps(export_data, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{dno_id}/import")
async def import_dno_data(
    dno_id: int,
    request: ImportRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
) -> APIResponse:
    """
    Import JSON data with validation and sanitization.
    
    Available to all authenticated users.
    
    Modes:
    - merge: Add/update records, keep existing data
    - replace: Delete existing data, then insert new
    
    Security:
    - Pydantic schema validation
    - Content sanitization (blocks injection attempts)
    - Numeric bounds checking
    - Record count limits
    """
    from app.db.models import NetzentgelteModel, HLZFModel
    from app.core.sanitize import sanitize_string, sanitize_time_string, SanitizationError
    import structlog
    
    logger = structlog.get_logger()
    
    # Get DNO
    dno = await db.get(DNOModel, dno_id)
    if not dno:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DNO not found")
    
    logger.info(
        "import_started",
        dno_id=dno_id,
        dno_slug=dno.slug,
        mode=request.mode,
        netzentgelte_count=len(request.netzentgelte),
        hlzf_count=len(request.hlzf),
        user=current_user.email,
    )
    
    # Track changes
    netz_created = 0
    netz_updated = 0
    hlzf_created = 0
    hlzf_updated = 0
    
    try:
        # Handle replace mode - delete existing data first
        if request.mode == "replace":
            # Delete only for the years being imported
            netz_years = set(r.year for r in request.netzentgelte)
            hlzf_years = set(r.year for r in request.hlzf)
            
            if netz_years:
                await db.execute(
                    delete(NetzentgelteModel).where(
                        and_(
                            NetzentgelteModel.dno_id == dno_id,
                            NetzentgelteModel.year.in_(netz_years),
                        )
                    )
                )
            
            if hlzf_years:
                await db.execute(
                    delete(HLZFModel).where(
                        and_(
                            HLZFModel.dno_id == dno_id,
                            HLZFModel.year.in_(hlzf_years),
                        )
                    )
                )
        
        # Import Netzentgelte
        for record in request.netzentgelte:
            # Check for existing record
            existing = await db.execute(
                select(NetzentgelteModel).where(
                    and_(
                        NetzentgelteModel.dno_id == dno_id,
                        NetzentgelteModel.year == record.year,
                        NetzentgelteModel.voltage_level == record.voltage_level,
                    )
                )
            )
            existing_record = existing.scalar_one_or_none()
            
            if existing_record:
                # Update existing
                if record.leistung is not None:
                    existing_record.leistung = record.leistung
                if record.arbeit is not None:
                    existing_record.arbeit = record.arbeit
                if record.leistung_unter_2500h is not None:
                    existing_record.leistung_unter_2500h = record.leistung_unter_2500h
                if record.arbeit_unter_2500h is not None:
                    existing_record.arbeit_unter_2500h = record.arbeit_unter_2500h
                if record.verification_status:
                    existing_record.verification_status = record.verification_status
                if record.extraction_source:
                    existing_record.extraction_source = sanitize_string(
                        record.extraction_source, "extraction_source", max_length=100
                    )
                netz_updated += 1
            else:
                # Create new
                new_record = NetzentgelteModel(
                    dno_id=dno_id,
                    year=record.year,
                    voltage_level=record.voltage_level,
                    leistung=record.leistung,
                    arbeit=record.arbeit,
                    leistung_unter_2500h=record.leistung_unter_2500h,
                    arbeit_unter_2500h=record.arbeit_unter_2500h,
                    verification_status=record.verification_status or "unverified",
                    extraction_source=sanitize_string(
                        record.extraction_source or "import", "extraction_source", max_length=100
                    ),
                )
                db.add(new_record)
                netz_created += 1
        
        # Import HLZF
        for record in request.hlzf:
            # Sanitize time strings
            winter = sanitize_time_string(record.winter or "", "winter") if record.winter else None
            fruehling = sanitize_time_string(record.fruehling or "", "fruehling") if record.fruehling else None
            sommer = sanitize_time_string(record.sommer or "", "sommer") if record.sommer else None
            herbst = sanitize_time_string(record.herbst or "", "herbst") if record.herbst else None
            
            # Check for existing record
            existing = await db.execute(
                select(HLZFModel).where(
                    and_(
                        HLZFModel.dno_id == dno_id,
                        HLZFModel.year == record.year,
                        HLZFModel.voltage_level == record.voltage_level,
                    )
                )
            )
            existing_record = existing.scalar_one_or_none()
            
            if existing_record:
                # Update existing
                if winter:
                    existing_record.winter = winter
                if fruehling:
                    existing_record.fruehling = fruehling
                if sommer:
                    existing_record.sommer = sommer
                if herbst:
                    existing_record.herbst = herbst
                if record.verification_status:
                    existing_record.verification_status = record.verification_status
                if record.extraction_source:
                    existing_record.extraction_source = sanitize_string(
                        record.extraction_source, "extraction_source", max_length=100
                    )
                hlzf_updated += 1
            else:
                # Create new
                new_record = HLZFModel(
                    dno_id=dno_id,
                    year=record.year,
                    voltage_level=record.voltage_level,
                    winter=winter,
                    fruehling=fruehling,
                    sommer=sommer,
                    herbst=herbst,
                    verification_status=record.verification_status or "unverified",
                    extraction_source=sanitize_string(
                        record.extraction_source or "import", "extraction_source", max_length=100
                    ),
                )
                db.add(new_record)
                hlzf_created += 1
        
        await db.commit()
        
        logger.info(
            "import_completed",
            dno_id=dno_id,
            netz_created=netz_created,
            netz_updated=netz_updated,
            hlzf_created=hlzf_created,
            hlzf_updated=hlzf_updated,
        )
        
        return APIResponse(
            success=True,
            message=f"Import completed: {netz_created + hlzf_created} created, {netz_updated + hlzf_updated} updated",
            data={
                "netzentgelte": {"created": netz_created, "updated": netz_updated},
                "hlzf": {"created": hlzf_created, "updated": hlzf_updated},
                "mode": request.mode,
            },
        )
    
    except SanitizationError as e:
        logger.warning("import_sanitization_failed", error=str(e), dno_id=dno_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Content sanitization failed: {str(e)}",
        )
    except Exception as e:
        logger.error("import_failed", error=str(e), dno_id=dno_id)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {str(e)}",
        )
