"""Public hospital endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import DatabaseSession
from app.models.hospital import Hospital
from app.schemas.common import BasicResponse

router = APIRouter()


@router.get("/basic", response_model=list[BasicResponse])
async def list_hospitals_basic(db: DatabaseSession):
    """List basic hospital details (ID and Name) for dropdowns."""
    query = select(Hospital.id, Hospital.name).where(Hospital.is_deleted == False).order_by(Hospital.name)
    result = await db.execute(query)
    return [BasicResponse(id=row.id, name=row.name) for row in result.all()]
