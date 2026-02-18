"""Department management endpoints for admin panel."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.models.hospital import Hospital, Department
from app.models.doctor import Doctor
from app.schemas.common import PaginatedResponse, MessageResponse
from pydantic import BaseModel, Field

router = APIRouter()


# ============== SCHEMAS ==============

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


# ============== DEPARTMENT KPIs ==============

@router.get("/totaldepartments", dependencies=[RequireAdmin])
async def get_total_departments(db: DatabaseSession):
    """Get total departments count."""
    result = await db.execute(
        select(func.count(Department.id)).where(Department.is_deleted == False)
    )
    return {"total_departments": result.scalar() or 0}


@router.get("/totalactive", dependencies=[RequireAdmin])
async def get_total_active_departments(db: DatabaseSession):
    """Get total active departments count."""
    result = await db.execute(
        select(func.count(Department.id)).where(
            Department.is_deleted == False,
            Department.is_active == True
        )
    )
    return {"active_departments": result.scalar() or 0}


@router.get("/totalhospitals", dependencies=[RequireAdmin])
async def get_total_hospitals(db: DatabaseSession):
    """Get count of hospitals that have departments."""
    result = await db.execute(
        select(func.count(func.distinct(Department.hospital_id))).where(
            Department.is_deleted == False
        )
    )
    return {"total_hospitals": result.scalar() or 0}


@router.get("/totaldoctors", dependencies=[RequireAdmin])
async def get_total_doctors(db: DatabaseSession):
    """Get total doctors count."""
    result = await db.execute(
        select(func.count(Doctor.id)).where(Doctor.is_deleted == False)
    )
    return {"total_doctors": result.scalar() or 0}


# ============== DEPARTMENT CRUD ==============

@router.get("", dependencies=[RequireAdmin])
async def list_departments(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    hospital_id: Optional[UUID] = None,
    is_active: Optional[bool] = None,
):
    """List all departments with filtering."""
    from sqlalchemy import or_
    
    query = select(Department).options(
        selectinload(Department.hospital)
    ).where(Department.is_deleted == False)
    
    if search:
        query = query.where(Department.name.ilike(f"%{search}%"))
    
    if hospital_id:
        query = query.where(Department.hospital_id == hospital_id)
    
    if is_active is not None:
        query = query.where(Department.is_active == is_active)
    
    # Count
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    
    # Paginate
    query = query.order_by(Department.name)
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    departments = result.scalars().all()
    
    # Transform to response
    items = [
        DepartmentResponse(
            id=dept.id,
            hospital_id=dept.hospital_id,
            hospital_name=dept.hospital.name if dept.hospital else "Unknown",
            name=dept.name,
            slug=dept.slug,
            description=dept.description,
            is_active=dept.is_active,
        )
        for dept in departments
    ]
    
    return PaginatedResponse.create(items, total, page, page_size)


@router.post("", response_model=DepartmentResponse, dependencies=[RequireAdmin])
async def create_department(data: DepartmentCreate, current_user: CurrentUser, db: DatabaseSession):
    """Create a new department."""
    # Check if hospital exists
    hospital_result = await db.execute(
        select(Hospital).where(Hospital.id == data.hospital_id, Hospital.is_deleted == False)
    )
    hospital = hospital_result.scalar_one_or_none()
    
    if not hospital:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hospital not found"
        )
    
    # Check if slug already exists for this hospital
    existing = await db.execute(
        select(Department).where(
            Department.hospital_id == data.hospital_id,
            Department.slug == data.slug
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Department with slug '{data.slug}' already exists in this hospital"
        )
    
    department = Department(
        **data.model_dump(),
        created_by=current_user.id,
    )
    
    db.add(department)
    await db.commit()
    await db.refresh(department)
    
    # Load hospital for response
    await db.refresh(department, ["hospital"])
    
    return DepartmentResponse(
        id=department.id,
        hospital_id=department.hospital_id,
        hospital_name=department.hospital.name,
        name=department.name,
        slug=department.slug,
        description=department.description,
        is_active=department.is_active,
    )


@router.get("/{department_id}", response_model=DepartmentResponse, dependencies=[RequireAdmin])
async def get_department(department_id: UUID, db: DatabaseSession):
    """Get department details."""
    result = await db.execute(
        select(Department)
        .options(selectinload(Department.hospital))
        .where(Department.id == department_id, Department.is_deleted == False)
    )
    department = result.scalar_one_or_none()
    
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    
    return DepartmentResponse(
        id=department.id,
        hospital_id=department.hospital_id,
        hospital_name=department.hospital.name if department.hospital else "Unknown",
        name=department.name,
        slug=department.slug,
        description=department.description,
        is_active=department.is_active,
    )


@router.put("/{department_id}", response_model=DepartmentResponse, dependencies=[RequireAdmin])
async def update_department(
    department_id: UUID,
    data: DepartmentUpdate,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Update department."""
    result = await db.execute(
        select(Department)
        .options(selectinload(Department.hospital))
        .where(Department.id == department_id, Department.is_deleted == False)
    )
    department = result.scalar_one_or_none()
    
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    
    # If hospital_id is being updated, check if new hospital exists
    if data.hospital_id and data.hospital_id != department.hospital_id:
        hospital_result = await db.execute(
            select(Hospital).where(Hospital.id == data.hospital_id, Hospital.is_deleted == False)
        )
        if not hospital_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hospital not found"
            )
    
    # Check slug uniqueness if being updated
    if data.slug and data.slug != department.slug:
        existing = await db.execute(
            select(Department).where(
                Department.hospital_id == (data.hospital_id or department.hospital_id),
                Department.slug == data.slug,
                Department.id != department_id
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Department with slug '{data.slug}' already exists in this hospital"
            )
    
    # Update fields
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(department, field, value)
    
    department.updated_by = current_user.id
    await db.commit()
    await db.refresh(department, ["hospital"])
    
    return DepartmentResponse(
        id=department.id,
        hospital_id=department.hospital_id,
        hospital_name=department.hospital.name if department.hospital else "Unknown",
        name=department.name,
        slug=department.slug,
        description=department.description,
        is_active=department.is_active,
    )


@router.delete("/{department_id}", response_model=MessageResponse, dependencies=[RequireAdmin])
async def delete_department(department_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Soft delete department."""
    result = await db.execute(
        select(Department).where(Department.id == department_id, Department.is_deleted == False)
    )
    department = result.scalar_one_or_none()
    
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    
    department.is_deleted = True
    department.deleted_by = current_user.id
    await db.commit()
    
    return MessageResponse(message="Department deleted successfully")
