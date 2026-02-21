"""Admin doctor management endpoints."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload, joinedload

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.models.doctor import Doctor, DoctorSpecialization, DoctorAssignment
from app.models.hospital import Hospital, Department
from app.models.user import User
from app.schemas.common import PaginatedResponse, MessageResponse
from app.schemas.doctor import DoctorCreate, DoctorUpdate, DoctorResponse
from pydantic import BaseModel, Field

router = APIRouter()


# ============== SCHEMAS ==============

class DoctorAssignmentCreate(BaseModel):
    """Schema for assigning doctor to hospital/department."""
    doctor_id: UUID
    hospital_id: UUID
    department_id: Optional[UUID] = None
    is_primary_department: bool = False


class DoctorAssignmentResponse(BaseModel):
    """Schema for doctor assignment response."""
    id: UUID
    doctor_id: UUID
    doctor_name: str
    hospital_id: UUID
    hospital_name: str
    department_id: Optional[UUID] = None
    department_name: Optional[str] = None
    is_primary_department: bool
    
    class Config:
        from_attributes = True


# ============== DOCTOR ASSIGNMENT KPIs ==============

@router.get("/assignments/totalassignment", dependencies=[RequireAdmin])
async def get_total_assignments(db: DatabaseSession):
    """Get total doctor assignments count."""
    
    result = await db.execute(
        select(func.count(DoctorAssignment.id)).where(DoctorAssignment.is_deleted == False)
    )
    total_assignments = result.scalar() or 0
    
    return {"total_assignments": total_assignments}


@router.get("/assignments/doctorsassigned", dependencies=[RequireAdmin])
async def get_doctors_assigned(db: DatabaseSession):
    """Get count of unique doctors with assignments."""
    
    result = await db.execute(
        select(func.count(func.distinct(DoctorAssignment.doctor_id))).where(
            DoctorAssignment.is_deleted == False
        )
    )
    doctors_assigned = result.scalar() or 0
    
    return {"doctors_assigned": doctors_assigned}


@router.get("/assignments/departments", dependencies=[RequireAdmin])
async def get_assignment_departments(db: DatabaseSession):
    """Get count of unique departments in assignments."""
    
    result = await db.execute(
        select(func.count(func.distinct(DoctorAssignment.department_id))).where(
            DoctorAssignment.is_deleted == False,
            DoctorAssignment.department_id.isnot(None)
        )
    )
    total_departments = result.scalar() or 0
    
    return {"total_departments": total_departments}


@router.get("/assignments/hospitals", dependencies=[RequireAdmin])
async def get_assignment_hospitals(db: DatabaseSession):
    """Get count of unique hospitals in assignments."""
    
    result = await db.execute(
        select(func.count(func.distinct(DoctorAssignment.hospital_id))).where(
            DoctorAssignment.is_deleted == False
        )
    )
    total_hospitals = result.scalar() or 0
    
    return {"total_hospitals": total_hospitals}


# ============== DOCTOR ASSIGNMENT CRUD ==============

@router.get("/assignments", dependencies=[RequireAdmin])
async def list_doctor_assignments(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    doctor_id: Optional[UUID] = None,
    hospital_id: Optional[UUID] = None,
    department_id: Optional[UUID] = None,
):
    """List all doctor assignments with filtering."""
    
    query = select(DoctorAssignment).options(
        joinedload(DoctorAssignment.doctor).joinedload(Doctor.user),
        joinedload(DoctorAssignment.hospital),
        joinedload(DoctorAssignment.department)
    ).where(DoctorAssignment.is_deleted == False)
    
    if doctor_id:
        query = query.where(DoctorAssignment.doctor_id == doctor_id)
    
    if hospital_id:
        query = query.where(DoctorAssignment.hospital_id == hospital_id)
    
    if department_id:
        query = query.where(DoctorAssignment.department_id == department_id)
    
    # Count
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    
    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    assignments = result.scalars().all()
    
    # Transform to response
    items = [
        DoctorAssignmentResponse(
            id=assignment.id,
            doctor_id=assignment.doctor_id,
            doctor_name=assignment.doctor.user.full_name if assignment.doctor and assignment.doctor.user else "Unknown",
            hospital_id=assignment.hospital_id,
            hospital_name=assignment.hospital.name if assignment.hospital else "Unknown",
            department_id=assignment.department_id,
            department_name=assignment.department.name if assignment.department else None,
            is_primary_department=assignment.is_primary_department,
        )
        for assignment in assignments
    ]
    
    return PaginatedResponse.create(items, total, page, page_size)


@router.post("/assignments", response_model=DoctorAssignmentResponse, dependencies=[RequireAdmin])
async def assign_doctor(data: DoctorAssignmentCreate, current_user: CurrentUser, db: DatabaseSession):
    """Assign doctor to hospital and department."""
    
    # Verify doctor exists
    doctor_result = await db.execute(
        select(Doctor).options(joinedload(Doctor.user)).where(
            Doctor.id == data.doctor_id,
            Doctor.is_deleted == False
        )
    )
    doctor = doctor_result.scalar_one_or_none()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    # Verify hospital exists
    hospital_result = await db.execute(
        select(Hospital).where(
            Hospital.id == data.hospital_id,
            Hospital.is_deleted == False
        )
    )
    hospital = hospital_result.scalar_one_or_none()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
    
    # Verify department exists if provided
    department = None
    if data.department_id:
        department_result = await db.execute(
            select(Department).where(
                Department.id == data.department_id,
                Department.is_deleted == False
            )
        )
        department = department_result.scalar_one_or_none()
        if not department:
            raise HTTPException(status_code=404, detail="Department not found")
        
        # Verify department belongs to hospital
        if department.hospital_id != data.hospital_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Department does not belong to the specified hospital"
            )
    
    # Check if assignment already exists
    existing_result = await db.execute(
        select(DoctorAssignment).where(
            DoctorAssignment.doctor_id == data.doctor_id,
            DoctorAssignment.hospital_id == data.hospital_id,
            DoctorAssignment.department_id == data.department_id,
            DoctorAssignment.is_deleted == False
        )
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This assignment already exists"
        )
    
    # Create assignment
    assignment = DoctorAssignment(
        doctor_id=data.doctor_id,
        hospital_id=data.hospital_id,
        department_id=data.department_id,
        is_primary_department=data.is_primary_department,
        created_by=current_user.id,
    )
    
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)
    
    return DoctorAssignmentResponse(
        id=assignment.id,
        doctor_id=assignment.doctor_id,
        doctor_name=doctor.user.full_name if doctor.user else "Unknown",
        hospital_id=assignment.hospital_id,
        hospital_name=hospital.name,
        department_id=assignment.department_id,
        department_name=department.name if department else None,
        is_primary_department=assignment.is_primary_department,
    )


@router.delete("/assignments/{assignment_id}", response_model=MessageResponse, dependencies=[RequireAdmin])
async def unassign_doctor(assignment_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Remove doctor assignment from hospital/department."""
    
    result = await db.execute(
        select(DoctorAssignment).where(
            DoctorAssignment.id == assignment_id,
            DoctorAssignment.is_deleted == False
        )
    )
    assignment = result.scalar_one_or_none()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    assignment.is_deleted = True
    assignment.deleted_by = current_user.id
    await db.commit()
    
    return MessageResponse(message="Doctor assignment removed successfully")


# ============== DOCTOR CRUD ==============

@router.get("", response_model=PaginatedResponse[DoctorResponse], dependencies=[RequireAdmin])
async def list_doctors(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    hospital_id: Optional[UUID] = None,
    specialization: Optional[str] = None,
):
    """List all doctors with filtering."""
    
    query = select(Doctor).options(
        joinedload(Doctor.user),
        joinedload(Doctor.hospital),
        selectinload(Doctor.specializations)
    ).where(Doctor.is_deleted == False)
    
    if search:
        query = query.join(Doctor.user).where(
            or_(
                User.full_name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%")
            )
        )
    
    if hospital_id:
        query = query.where(Doctor.hospital_id == hospital_id)
    
    if specialization:
        query = query.join(Doctor.specializations).where(
            DoctorSpecialization.specialization.ilike(f"%{specialization}%")
        )
    
    # Count
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    
    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    doctors = result.scalars().unique().all()
    
    return PaginatedResponse.create(doctors, total, page, page_size)


@router.post("", response_model=DoctorResponse, dependencies=[RequireAdmin])
async def create_doctor(data: DoctorCreate, current_user: CurrentUser, db: DatabaseSession):
    """Create a new doctor (admin only)."""
    
    # Verify user_id if provided
    if data.user_id:
        user_result = await db.execute(
            select(User).where(User.id == data.user_id, User.is_deleted == False)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check if doctor profile already exists for this user
        existing_result = await db.execute(
            select(Doctor).where(Doctor.user_id == data.user_id)
        )
        if existing_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Doctor profile already exists for this user"
            )
        
        user_id = data.user_id
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id is required for admin doctor creation"
        )
    
    # Verify hospital if provided
    if data.hospital_id:
        hospital_result = await db.execute(
            select(Hospital).where(
                Hospital.id == data.hospital_id,
                Hospital.is_deleted == False
            )
        )
        if not hospital_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Hospital not found")
    
    # Create doctor
    doctor_data = data.model_dump(exclude={"specializations"})
    doctor_data["user_id"] = user_id
    doctor = Doctor(**doctor_data, created_by=current_user.id)
    
    db.add(doctor)
    await db.flush()
    
    # Add specializations if provided
    if data.specializations:
        for spec_data in data.specializations:
            specialization = DoctorSpecialization(
                doctor_id=doctor.id,
                **spec_data.model_dump(),
                created_by=current_user.id
            )
            db.add(specialization)
    
    await db.commit()
    await db.refresh(doctor)
    
    return doctor


@router.get("/{doctor_id}", response_model=DoctorResponse, dependencies=[RequireAdmin])
async def get_doctor(doctor_id: UUID, db: DatabaseSession):
    """Get doctor details."""
    
    result = await db.execute(
        select(Doctor).options(
            joinedload(Doctor.user),
            joinedload(Doctor.hospital),
            selectinload(Doctor.specializations)
        ).where(Doctor.id == doctor_id, Doctor.is_deleted == False)
    )
    doctor = result.scalar_one_or_none()
    
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    return doctor


@router.put("/{doctor_id}", response_model=DoctorResponse, dependencies=[RequireAdmin])
async def update_doctor(
    doctor_id: UUID,
    data: DoctorUpdate,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Update doctor."""
    
    result = await db.execute(
        select(Doctor).options(
            joinedload(Doctor.user),
            joinedload(Doctor.hospital),
            selectinload(Doctor.specializations)
        ).where(Doctor.id == doctor_id, Doctor.is_deleted == False)
    )
    doctor = result.scalar_one_or_none()
    
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    # Verify hospital if being updated
    if data.hospital_id:
        hospital_result = await db.execute(
            select(Hospital).where(
                Hospital.id == data.hospital_id,
                Hospital.is_deleted == False
            )
        )
        if not hospital_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Hospital not found")
    
    # Update fields
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(doctor, field, value)
    
    doctor.updated_by = current_user.id
    await db.commit()
    await db.refresh(doctor)
    
    return doctor


@router.delete("/{doctor_id}", response_model=MessageResponse, dependencies=[RequireAdmin])
async def delete_doctor(doctor_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Soft delete doctor."""
    
    result = await db.execute(
        select(Doctor).where(Doctor.id == doctor_id, Doctor.is_deleted == False)
    )
    doctor = result.scalar_one_or_none()
    
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    doctor.is_deleted = True
    doctor.deleted_by = current_user.id
    await db.commit()
    
    return MessageResponse(message="Doctor deleted successfully")
