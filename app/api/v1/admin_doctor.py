"""Admin doctor management endpoints."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload, joinedload

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin, RequireSuperAdmin
from app.core.security import get_password_hash
from app.models.doctor import (
    Doctor,
    DoctorAvailability,
    DoctorSpecialization,
    DoctorAssignment,
)
from app.models.hospital import Hospital, Department
from app.models.user import User
from app.schemas.common import PaginatedResponse, MessageResponse
from app.schemas.doctor import (
    AdminDoctorCreate,
    AdminDoctorUpdate,
    DoctorResponse,
)
from app.services.doctor_service import DoctorService
from app.utils.enums import DoctorApprovalStatus, UserRole
from pydantic import BaseModel, Field

router = APIRouter()


class DoctorRejectRequest(BaseModel):
    """Payload for rejecting a doctor registration."""

    reason: str = Field(..., min_length=5, max_length=2000)


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


async def _get_doctor_or_404(db: DatabaseSession, doctor_id: UUID) -> Doctor:
    """Load doctor with relations or raise 404."""
    result = await db.execute(
        select(Doctor).options(
            joinedload(Doctor.user),
            joinedload(Doctor.hospital),
            selectinload(Doctor.specializations),
            selectinload(Doctor.availability),
        ).where(Doctor.id == doctor_id, Doctor.is_deleted == False)
    )
    doctor = result.scalar_one_or_none()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return doctor


@router.get("", response_model=PaginatedResponse[DoctorResponse], dependencies=[RequireAdmin])
async def list_doctors(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    hospital_id: Optional[UUID] = None,
    specialization: Optional[str] = None,
    status: Optional[str] = Query(
        default=None,
        description="Filter by approval_status: pending | approved | rejected | suspended",
    ),
    is_verified: Optional[bool] = Query(default=None),
):
    """List all doctors with filtering. Pending doctors sort first when no status filter."""

    query = select(Doctor).options(
        joinedload(Doctor.user),
        joinedload(Doctor.hospital),
        selectinload(Doctor.specializations),
        selectinload(Doctor.availability),
    ).where(Doctor.is_deleted == False)

    if search:
        query = query.join(Doctor.user).where(
            or_(
                User.full_name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
            )
        )

    if hospital_id:
        query = query.where(Doctor.hospital_id == hospital_id)

    if specialization:
        query = query.join(Doctor.specializations).where(
            DoctorSpecialization.specialization.ilike(f"%{specialization}%")
        )

    if status:
        allowed = {s.value for s in DoctorApprovalStatus}
        if status not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Allowed: {', '.join(sorted(allowed))}",
            )
        query = query.where(Doctor.approval_status == status)

    if is_verified is not None:
        query = query.where(Doctor.is_verified == is_verified)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    # Pending first, then newest
    query = query.order_by(
        (Doctor.approval_status == DoctorApprovalStatus.PENDING.value).desc(),
        Doctor.created_at.desc(),
    ).offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    doctors = result.scalars().unique().all()

    return PaginatedResponse.create(doctors, total, page, page_size)


@router.get("/pending", response_model=PaginatedResponse[DoctorResponse], dependencies=[RequireAdmin])
async def list_pending_doctors(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List doctors awaiting super-admin approval."""
    return await list_doctors(
        db=db,
        page=page,
        page_size=page_size,
        search=None,
        hospital_id=None,
        specialization=None,
        status=DoctorApprovalStatus.PENDING.value,
        is_verified=None,
    )


@router.get("/pending/count", dependencies=[RequireAdmin])
async def get_pending_doctors_count(db: DatabaseSession):
    """Badge count of pending doctor registrations."""
    result = await db.execute(
        select(func.count(Doctor.id)).where(
            Doctor.is_deleted == False,
            Doctor.approval_status == DoctorApprovalStatus.PENDING.value,
        )
    )
    return {"pending_count": result.scalar() or 0}


@router.post("", response_model=DoctorResponse, status_code=status.HTTP_201_CREATED, dependencies=[RequireAdmin])
async def create_doctor(data: AdminDoctorCreate, current_user: CurrentUser, db: DatabaseSession):
    """
    Register a doctor from admin (user + profile in one call).

    - Creates the user with role=doctor
    - Skips email verification (user is marked verified immediately)
    - Creates the full doctor profile matching GET /doctors/me fields
    - Optionally sets specializations and availability
    """

    # Email uniqueness
    existing_user = await db.execute(
        select(User).where(User.email == data.email, User.is_deleted == False)
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # License uniqueness (when provided)
    if data.license_number:
        existing_license = await db.execute(
            select(Doctor).where(
                Doctor.license_number == data.license_number,
                Doctor.is_deleted == False,
            )
        )
        if existing_license.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="License number already registered",
            )

    if data.hospital_id:
        hospital_result = await db.execute(
            select(Hospital).where(
                Hospital.id == data.hospital_id,
                Hospital.is_deleted == False,
            )
        )
        if not hospital_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Hospital not found")

    # Create verified user — no verification email
    user = User(
        email=data.email,
        hashed_password=get_password_hash(data.password),
        full_name=data.full_name,
        phone=data.phone,
        role=UserRole.DOCTOR.value,
        is_active=True,
        is_verified=True,
        verification_token=None,
        created_by=current_user.id,
    )
    db.add(user)
    await db.flush()

    doctor = Doctor(
        user_id=user.id,
        hospital_id=data.hospital_id,
        title=data.title,
        license_number=data.license_number,
        license_expiry=data.license_expiry,
        primary_specialty=data.primary_specialty,
        years_of_experience=data.years_of_experience,
        qualifications=data.qualifications,
        education=data.education,
        certifications=data.certifications,
        bio=data.bio,
        languages_spoken=data.languages_spoken,
        consultation_fee=data.consultation_fee,
        consultation_duration_minutes=data.consultation_duration_minutes,
        video_consultation_enabled=data.video_consultation_enabled,
        chat_consultation_enabled=data.chat_consultation_enabled,
        in_person_enabled=data.in_person_enabled,
        address_line1=data.address_line1,
        address_line2=data.address_line2,
        city=data.city,
        state=data.state,
        country=data.country,
        postal_code=data.postal_code,
        is_verified=data.is_verified,
        verification_date=datetime.now(timezone.utc) if data.is_verified else None,
        approval_status=(
            DoctorApprovalStatus.APPROVED.value
            if data.is_verified
            else DoctorApprovalStatus.PENDING.value
        ),
        reviewed_at=datetime.now(timezone.utc) if data.is_verified else None,
        reviewed_by=current_user.id if data.is_verified else None,
        created_by=current_user.id,
    )
    db.add(doctor)
    await db.flush()

    if data.specializations:
        for spec_data in data.specializations:
            db.add(
                DoctorSpecialization(
                    doctor_id=doctor.id,
                    **spec_data.model_dump(),
                    created_by=current_user.id,
                )
            )

    if data.availability:
        for avail_data in data.availability:
            db.add(
                DoctorAvailability(
                    doctor_id=doctor.id,
                    **avail_data.model_dump(),
                    created_by=current_user.id,
                )
            )

    await db.commit()
    return await _get_doctor_or_404(db, doctor.id)


@router.get("/{doctor_id}", response_model=DoctorResponse, dependencies=[RequireAdmin])
async def get_doctor(doctor_id: UUID, db: DatabaseSession):
    """Get doctor details."""
    return await _get_doctor_or_404(db, doctor_id)


@router.post(
    "/{doctor_id}/approve",
    response_model=DoctorResponse,
    dependencies=[RequireSuperAdmin],
)
async def approve_doctor(
    doctor_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Approve a doctor (super_admin only). Makes the profile visible on the public frontend."""
    doctor = await _get_doctor_or_404(db, doctor_id)
    if doctor.approval_status == DoctorApprovalStatus.APPROVED.value and doctor.is_verified:
        return doctor
    service = DoctorService(db)
    return await service.approve(doctor, current_user.id)


@router.post(
    "/{doctor_id}/reject",
    response_model=DoctorResponse,
    dependencies=[RequireSuperAdmin],
)
async def reject_doctor(
    doctor_id: UUID,
    data: DoctorRejectRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Reject a doctor registration (super_admin only). Profile stays hidden from public frontend."""
    doctor = await _get_doctor_or_404(db, doctor_id)
    if doctor.approval_status == DoctorApprovalStatus.APPROVED.value and doctor.is_verified:
        raise HTTPException(
            status_code=400,
            detail="Doctor is already approved. Suspend or unverify via update instead.",
        )
    service = DoctorService(db)
    return await service.reject(doctor, current_user.id, data.reason.strip())


@router.put("/{doctor_id}", response_model=DoctorResponse, dependencies=[RequireAdmin])
async def update_doctor(
    doctor_id: UUID,
    data: AdminDoctorUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Update doctor profile, account contact fields, specializations, and availability."""

    doctor = await _get_doctor_or_404(db, doctor_id)

    if data.hospital_id:
        hospital_result = await db.execute(
            select(Hospital).where(
                Hospital.id == data.hospital_id,
                Hospital.is_deleted == False,
            )
        )
        if not hospital_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Hospital not found")

    update_data = data.model_dump(
        exclude_unset=True,
        exclude={"full_name", "email", "phone", "specializations", "availability"},
    )

    if "is_verified" in update_data:
        if update_data["is_verified"] and not doctor.is_verified:
            update_data["verification_date"] = datetime.now(timezone.utc)
            update_data["approval_status"] = DoctorApprovalStatus.APPROVED.value
            update_data["reviewed_at"] = datetime.now(timezone.utc)
            update_data["reviewed_by"] = current_user.id
            update_data["rejection_reason"] = None
        elif not update_data["is_verified"]:
            update_data["verification_date"] = None
            # Only force pending if not already rejected/suspended
            if doctor.approval_status == DoctorApprovalStatus.APPROVED.value:
                update_data["approval_status"] = DoctorApprovalStatus.PENDING.value
            update_data["reviewed_at"] = datetime.now(timezone.utc)
            update_data["reviewed_by"] = current_user.id

    if "license_number" in update_data and update_data["license_number"]:
        existing_license = await db.execute(
            select(Doctor).where(
                Doctor.license_number == update_data["license_number"],
                Doctor.id != doctor_id,
                Doctor.is_deleted == False,
            )
        )
        if existing_license.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="License number already registered",
            )

    for field, value in update_data.items():
        setattr(doctor, field, value)

    # Update linked user account fields
    if doctor.user:
        if data.full_name is not None:
            doctor.user.full_name = data.full_name
        if data.phone is not None:
            doctor.user.phone = data.phone
        if data.email is not None:
            email_check = await db.execute(
                select(User).where(
                    User.email == data.email,
                    User.id != doctor.user_id,
                    User.is_deleted == False,
                )
            )
            if email_check.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered",
                )
            doctor.user.email = data.email
        doctor.user.updated_by = current_user.id

    if data.specializations is not None:
        await db.execute(
            DoctorSpecialization.__table__.delete().where(
                DoctorSpecialization.doctor_id == doctor.id
            )
        )
        for spec_data in data.specializations:
            db.add(
                DoctorSpecialization(
                    doctor_id=doctor.id,
                    **spec_data.model_dump(),
                    created_by=current_user.id,
                )
            )

    if data.availability is not None:
        await db.execute(
            DoctorAvailability.__table__.delete().where(
                DoctorAvailability.doctor_id == doctor.id
            )
        )
        for avail_data in data.availability:
            db.add(
                DoctorAvailability(
                    doctor_id=doctor.id,
                    **avail_data.model_dump(),
                    created_by=current_user.id,
                )
            )

    doctor.updated_by = current_user.id
    await db.commit()
    return await _get_doctor_or_404(db, doctor.id)


@router.delete("/{doctor_id}", response_model=MessageResponse, dependencies=[RequireAdmin])
async def delete_doctor(doctor_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Soft delete doctor (and deactivate linked user account)."""

    result = await db.execute(
        select(Doctor).options(joinedload(Doctor.user)).where(
            Doctor.id == doctor_id,
            Doctor.is_deleted == False,
        )
    )
    doctor = result.scalar_one_or_none()

    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    doctor.is_deleted = True
    doctor.deleted_by = current_user.id

    if doctor.user:
        doctor.user.is_active = False
        doctor.user.updated_by = current_user.id

    await db.commit()

    return MessageResponse(message="Doctor deleted successfully")
