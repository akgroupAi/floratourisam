"""Hospital management endpoints for admin panel."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.models.hospital import Hospital, Department
from app.models.doctor import Doctor
from app.schemas.common import PaginatedResponse, MessageResponse, BasicResponse
from pydantic import BaseModel, Field

router = APIRouter()


# ============== SCHEMAS ==============

class HospitalCreate(BaseModel):
    """Schema for creating a hospital."""
    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address_line1: str = Field(..., min_length=2)
    address_line2: Optional[str] = None
    city: str = Field(..., min_length=2)
    state: Optional[str] = None
    country: str = Field(..., min_length=2)
    postal_code: Optional[str] = None
    is_active: bool = True


class HospitalUpdate(BaseModel):
    """Schema for updating a hospital."""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    slug: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    is_active: Optional[bool] = None


class HospitalResponse(BaseModel):
    """Schema for hospital response."""
    id: UUID
    name: str
    slug: str
    description: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: Optional[str] = None
    country: str
    postal_code: Optional[str] = None
    is_active: bool
    total_doctors: int = 0
    
    class Config:
        from_attributes = True


class DepartmentCreate(BaseModel):
    """Schema for creating a department."""
    hospital_id: UUID
    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    is_active: bool = True


class DepartmentUpdate(BaseModel):
    """Schema for updating a department."""
    hospital_id: Optional[UUID] = None
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    slug: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class DepartmentResponse(BaseModel):
    """Schema for department response."""
    id: UUID
    hospital_id: UUID
    hospital_name: str
    name: str
    slug: str
    description: Optional[str] = None
    is_active: bool
    
    class Config:
        from_attributes = True


# ============== HOSPITAL KPIs ==============

@router.get("/totalhospitals", dependencies=[RequireAdmin])
async def get_total_hospitals(db: DatabaseSession):
    """Get total hospitals count."""
    result = await db.execute(
        select(func.count(Hospital.id)).where(Hospital.is_deleted == False)
    )
    return {"total_hospitals": result.scalar() or 0}


@router.get("/totalactive", dependencies=[RequireAdmin])
async def get_total_active_hospitals(db: DatabaseSession):
    """Get total active hospitals count."""
    result = await db.execute(
        select(func.count(Hospital.id)).where(
            Hospital.is_deleted == False,
            Hospital.is_active == True
        )
    )
    return {"active_hospitals": result.scalar() or 0}


@router.get("/totaldepartments", dependencies=[RequireAdmin])
async def get_total_departments(db: DatabaseSession):
    """Get total departments count across all hospitals."""
    result = await db.execute(
        select(func.count(Department.id)).where(Department.is_deleted == False)
    )
    return {"total_departments": result.scalar() or 0}


@router.get("/totaldoctors", dependencies=[RequireAdmin])
async def get_total_doctors(db: DatabaseSession):
    """Get total doctors assigned to hospitals."""
    result = await db.execute(
        select(func.count(Doctor.id)).where(
            Doctor.is_deleted == False,
            Doctor.hospital_id.isnot(None)
        )
    )
    return {"total_doctors": result.scalar() or 0}


# ============== HOSPITAL CRUD ==============




@router.get("", response_model=PaginatedResponse[HospitalResponse], dependencies=[RequireAdmin])
async def list_hospitals(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    city: Optional[str] = None,
):
    """List all hospitals with filtering."""
    from sqlalchemy import or_
    
    query = select(Hospital).where(Hospital.is_deleted == False)
    
    if search:
        query = query.where(
            or_(
                Hospital.name.ilike(f"%{search}%"),
                Hospital.city.ilike(f"%{search}%"),
                Hospital.country.ilike(f"%{search}%")
            )
        )
    
    if is_active is not None:
        query = query.where(Hospital.is_active == is_active)
    
    if city:
        query = query.where(Hospital.city.ilike(f"%{city}%"))
    
    # Count
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    
    # Paginate
    query = query.order_by(Hospital.name)
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    hospitals = result.scalars().all()
    
    return PaginatedResponse.create(hospitals, total, page, page_size)


@router.post("", response_model=HospitalResponse, dependencies=[RequireAdmin])
async def create_hospital(data: HospitalCreate, current_user: CurrentUser, db: DatabaseSession):
    """Create a new hospital."""
    # Check if slug already exists
    existing = await db.execute(
        select(Hospital).where(Hospital.slug == data.slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Hospital with slug '{data.slug}' already exists"
        )
    
    hospital = Hospital(
        **data.model_dump(),
        created_by=current_user.id,
    )
    
    db.add(hospital)
    await db.commit()
    await db.refresh(hospital)
    
    return hospital


@router.get("/{hospital_id}", response_model=HospitalResponse, dependencies=[RequireAdmin])
async def get_hospital(hospital_id: UUID, db: DatabaseSession):
    """Get hospital details."""
    result = await db.execute(
        select(Hospital).where(Hospital.id == hospital_id, Hospital.is_deleted == False)
    )
    hospital = result.scalar_one_or_none()
    
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
    
    return hospital


@router.put("/{hospital_id}", response_model=HospitalResponse, dependencies=[RequireAdmin])
async def update_hospital(
    hospital_id: UUID,
    data: HospitalUpdate,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Update hospital."""
    result = await db.execute(
        select(Hospital).where(Hospital.id == hospital_id, Hospital.is_deleted == False)
    )
    hospital = result.scalar_one_or_none()
    
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
    
    # Check slug uniqueness if being updated
    if data.slug and data.slug != hospital.slug:
        existing = await db.execute(
            select(Hospital).where(Hospital.slug == data.slug, Hospital.id != hospital_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Hospital with slug '{data.slug}' already exists"
            )
    
    # Update fields
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(hospital, field, value)
    
    hospital.updated_by = current_user.id
    await db.commit()
    await db.refresh(hospital)
    
    return hospital


@router.delete("/{hospital_id}", response_model=MessageResponse, dependencies=[RequireAdmin])
async def delete_hospital(hospital_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Soft delete hospital."""
    result = await db.execute(
        select(Hospital).where(Hospital.id == hospital_id, Hospital.is_deleted == False)
    )
    hospital = result.scalar_one_or_none()
    
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
    
    hospital.is_deleted = True
    hospital.deleted_by = current_user.id
    await db.commit()
    
    return MessageResponse(message="Hospital deleted successfully")
