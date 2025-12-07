"""
Public API routes - rate-limited, no authentication required.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import APIResponse, DataType, PaginatedResponse
from app.db import DNOModel, HLZFModel, NetzentgelteModel, get_db

router = APIRouter()


@router.get("/search")
async def search_data(
    db: Annotated[AsyncSession, Depends(get_db)],
    dno: str | None = Query(None, description="DNO name or slug"),
    year: int | None = Query(None, ge=2000, le=2100),
    data_type: DataType | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> PaginatedResponse:
    """
    Search for DNO data.
    
    Public endpoint with rate limiting.
    Returns Netzentgelte and/or HLZF data matching the query.
    """
    results = []
    
    # Find DNO if specified
    dno_model = None
    if dno:
        query = select(DNOModel).where(
            (DNOModel.slug == dno.lower()) | (DNOModel.name.ilike(f"%{dno}%"))
        )
        result = await db.execute(query)
        dno_model = result.scalar_one_or_none()
        
        if not dno_model:
            return PaginatedResponse(
                success=True,
                message=f"No DNO found matching '{dno}'",
                data=[],
                meta={"total": 0, "page": page, "per_page": per_page, "total_pages": 0},
            )
    
    # Get Netzentgelte if requested
    if data_type in (None, DataType.NETZENTGELTE, DataType.ALL):
        query = select(NetzentgelteModel)
        if dno_model:
            query = query.where(NetzentgelteModel.dno_id == dno_model.id)
        if year:
            query = query.where(NetzentgelteModel.year == year)
        
        query = query.offset((page - 1) * per_page).limit(per_page)
        result = await db.execute(query)
        netzentgelte = result.scalars().all()
        
        for n in netzentgelte:
            results.append({
                "type": "netzentgelte",
                "dno_id": str(n.dno_id),
                "year": n.year,
                "voltage_level": n.voltage_level,
                "leistung": n.leistung,
                "arbeit": n.arbeit,
                "leistung_unter_2500h": n.leistung_unter_2500h,
                "arbeit_unter_2500h": n.arbeit_unter_2500h,
            })
    
    # Get HLZF if requested
    if data_type in (None, DataType.HLZF, DataType.ALL):
        query = select(HLZFModel)
        if dno_model:
            query = query.where(HLZFModel.dno_id == dno_model.id)
        if year:
            query = query.where(HLZFModel.year == year)
        
        query = query.offset((page - 1) * per_page).limit(per_page)
        result = await db.execute(query)
        hlzf = result.scalars().all()
        
        for h in hlzf:
            results.append({
                "type": "hlzf",
                "dno_id": str(h.dno_id),
                "year": h.year,
                "voltage_level": h.voltage_level,
                "winter": h.winter,
                "fruehling": h.fruehling,
                "sommer": h.sommer,
                "herbst": h.herbst,
            })
    
    return PaginatedResponse(
        success=True,
        data=results,
        meta={
            "total": len(results),  # TODO: Proper count query
            "page": page,
            "per_page": per_page,
            "total_pages": 1,  # TODO: Calculate properly
        },
    )


@router.get("/dnos")
async def list_dnos(
    db: Annotated[AsyncSession, Depends(get_db)],
    region: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
) -> PaginatedResponse:
    """
    List all available DNOs.
    
    Public endpoint to discover which DNOs have data.
    """
    query = select(DNOModel)
    
    if region:
        query = query.where(DNOModel.region.ilike(f"%{region}%"))
    
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    dnos = result.scalars().all()
    
    return PaginatedResponse(
        success=True,
        data=[
            {
                "id": str(d.id),
                "slug": d.slug,
                "name": d.name,
                "official_name": d.official_name,
                "region": d.region,
                "website": d.website,
            }
            for d in dnos
        ],
        meta={
            "total": len(dnos),
            "page": page,
            "per_page": per_page,
            "total_pages": 1,
        },
    )


@router.get("/dnos/{slug}")
async def get_dno(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> APIResponse:
    """Get details for a specific DNO."""
    query = select(DNOModel).where(DNOModel.slug == slug.lower())
    result = await db.execute(query)
    dno = result.scalar_one_or_none()
    
    if not dno:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DNO '{slug}' not found",
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
        },
    )


@router.get("/years")
async def list_available_years(
    db: Annotated[AsyncSession, Depends(get_db)],
    dno_slug: str | None = Query(None),
) -> APIResponse:
    """Get list of years that have data available."""
    # Get unique years from Netzentgelte
    query = select(NetzentgelteModel.year).distinct()
    
    if dno_slug:
        dno_query = select(DNOModel.id).where(DNOModel.slug == dno_slug.lower())
        result = await db.execute(dno_query)
        dno_id = result.scalar_one_or_none()
        if dno_id:
            query = query.where(NetzentgelteModel.dno_id == dno_id)
    
    result = await db.execute(query)
    years = sorted([row[0] for row in result.all()], reverse=True)
    
    return APIResponse(success=True, data=years)
