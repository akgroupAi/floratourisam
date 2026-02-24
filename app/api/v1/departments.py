"""Public department endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import DatabaseSession
from app.models.hospital import Department
from app.schemas.common import BasicResponse

router = APIRouter()


@router.get("/basic", response_model=list[BasicResponse])
async def list_departments_basic(
    db: DatabaseSession,
    hospital_id: Optional[UUID] = None,
):
    """List basic department details (ID and Name) for dropdowns. Filters by hospital_id if provided."""
    query = select(Department.id, Department.name).where(Department.is_deleted == False)

    if hospital_id:
        query = query.where(Department.hospital_id == hospital_id)

    query = query.order_by(Department.name)
    result = await db.execute(query)
    return [BasicResponse(id=row.id, name=row.name) for row in result.all()]
