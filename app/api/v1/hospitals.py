"""Public hospital endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.api.deps import DatabaseSession
from app.models.doctor import Doctor, DoctorAssignment
from app.models.hospital import Department, Hospital
from app.schemas.common import BasicResponse, PaginatedResponse
from app.schemas.hospital import HospitalListResponse, HospitalResponse

router = APIRouter()


@router.get("/basic", response_model=list[BasicResponse])
async def list_hospitals_basic(db: DatabaseSession):
    """List basic hospital details (ID and Name) for dropdowns."""
    query = select(Hospital.id, Hospital.name).where(Hospital.is_deleted == False).order_by(Hospital.name)
    result = await db.execute(query)
    return [BasicResponse(id=row.id, name=row.name) for row in result.all()]


@router.get("", response_model=PaginatedResponse[HospitalListResponse])
async def list_hospitals(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    city: Optional[str] = Query(default=None, description="Filter by city"),
    country: Optional[str] = Query(default=None, description="Filter by country"),
    speciality: Optional[str] = Query(default=None, description="Filter by specialty keyword"),
    search: Optional[str] = Query(default=None, description="Search by name"),
    featured: Optional[bool] = Query(default=None, description="Only featured hospitals"),
):
    """List active hospitals — used on the /hospitals public page."""
    query = select(Hospital).where(
        Hospital.is_active == True,
        Hospital.is_deleted == False,
    )
    if city:
        query = query.where(func.lower(Hospital.city) == city.lower())
    if country:
        query = query.where(func.lower(Hospital.country) == country.lower())
    if featured is not None:
        query = query.where(Hospital.is_featured == featured)
    if search:
        query = query.where(Hospital.name.ilike(f"%{search}%"))
    if speciality:
        query = query.where(Hospital.specialties.contains([speciality]))

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    query = query.order_by(Hospital.is_featured.desc(), Hospital.name).offset((page - 1) * page_size).limit(page_size)
    rows = await db.execute(query)
    return PaginatedResponse.create(list(rows.scalars().all()), total, page, page_size)


@router.get("/{hospital_id}", response_model=HospitalResponse)
async def get_hospital(hospital_id: UUID, db: DatabaseSession):
    """Get public hospital detail page."""
    result = await db.execute(
        select(Hospital).where(Hospital.id == hospital_id, Hospital.is_active == True, Hospital.is_deleted == False)
    )
    hospital = result.scalar_one_or_none()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
    return hospital


@router.get("/{hospital_id}/departments", response_model=list[dict])
async def get_hospital_departments(hospital_id: UUID, db: DatabaseSession):
    """List all active departments for a hospital."""
    result = await db.execute(
        select(Department).where(
            Department.hospital_id == hospital_id,
            Department.is_active == True,
            Department.is_deleted == False,
        ).order_by(Department.display_order, Department.name)
    )
    departments = result.scalars().all()
    return [
        {
            "id": d.id,
            "name": d.name,
            "slug": d.slug,
            "description": d.description,
            "icon": d.icon,
            "display_order": d.display_order,
        }
        for d in departments
    ]


@router.get("/{hospital_id}/doctors", response_model=list[dict])
async def get_hospital_doctors(
    hospital_id: UUID,
    db: DatabaseSession,
    department_id: Optional[UUID] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
):
    """List doctors assigned to a hospital. Optionally filter by department."""
    from app.models.user import User

    query = (
        select(Doctor, User.full_name)
        .join(User, Doctor.user_id == User.id)
        .join(DoctorAssignment, DoctorAssignment.doctor_id == Doctor.id)
        .where(
            DoctorAssignment.hospital_id == hospital_id,
            DoctorAssignment.is_deleted == False,
            Doctor.is_deleted == False,
            Doctor.is_active == True,
        )
    )
    if department_id:
        query = query.where(DoctorAssignment.department_id == department_id)
    query = query.limit(limit)

    rows = await db.execute(query)
    return [
        {
            "id": doc.id,
            "name": name,
            "specialization": doc.specialization,
            "profile_image_url": doc.profile_image_url,
            "rating": doc.rating,
            "years_of_experience": doc.years_of_experience,
            "consultation_fee": doc.consultation_fee,
        }
        for doc, name in rows.all()
    ]
