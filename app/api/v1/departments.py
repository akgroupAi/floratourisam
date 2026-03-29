"""Public department endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.api.deps import DatabaseSession
from app.models.hospital import Department, Hospital
from app.schemas.common import BasicResponse, PaginatedResponse

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


@router.get("", response_model=list[dict])
async def list_departments(
    db: DatabaseSession,
    hospital_id: Optional[UUID] = Query(default=None, description="Filter by hospital"),
    search: Optional[str] = Query(default=None, description="Search by name"),
):
    """List all active departments. Optionally scoped to a hospital."""
    query = select(Department, Hospital.name.label("hospital_name")).join(
        Hospital, Department.hospital_id == Hospital.id
    ).where(
        Department.is_active == True,
        Department.is_deleted == False,
    )
    if hospital_id:
        query = query.where(Department.hospital_id == hospital_id)
    if search:
        query = query.where(Department.name.ilike(f"%{search}%"))
    query = query.order_by(Department.display_order, Department.name)

    rows = await db.execute(query)
    return [
        {
            "id": dept.id,
            "name": dept.name,
            "slug": dept.slug,
            "description": dept.description,
            "icon": dept.icon,
            "display_order": dept.display_order,
            "hospital_id": dept.hospital_id,
            "hospital_name": hospital_name,
        }
        for dept, hospital_name in rows.all()
    ]


@router.get("/{department_id}", response_model=dict)
async def get_department(department_id: UUID, db: DatabaseSession):
    """Get department detail with hospital info."""
    result = await db.execute(
        select(Department, Hospital.name.label("hospital_name"))
        .join(Hospital, Department.hospital_id == Hospital.id)
        .where(
            Department.id == department_id,
            Department.is_active == True,
            Department.is_deleted == False,
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Department not found")
    dept, hospital_name = row
    return {
        "id": dept.id,
        "name": dept.name,
        "slug": dept.slug,
        "description": dept.description,
        "icon": dept.icon,
        "display_order": dept.display_order,
        "hospital_id": dept.hospital_id,
        "hospital_name": hospital_name,
        "head_doctor_id": dept.head_doctor_id,
    }
