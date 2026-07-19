"""Doctor endpoints."""

from datetime import date, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select, cast, Date

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin, RequireDoctor
from app.models.consultation import Consultation
from app.models.doctor import Doctor
from app.models.user import User
from app.schemas.common import BasicResponse, PaginatedResponse, PaginationParams
from app.schemas.doctor import (
    DoctorAvailabilityCreate,
    DoctorAvailabilityResponse,
    DoctorCreate,
    DoctorHospitalCreate,
    DoctorHospitalResponse,
    DoctorHospitalUpdate,
    DoctorListResponse,
    DoctorResponse,
    DoctorUpdate,
)
from app.services.doctor_service import DoctorService

router = APIRouter()

@router.get("/basic", response_model=list[BasicResponse])
async def list_doctors_basic(db: DatabaseSession):
    """List basic doctor details (ID and Name) for dropdowns."""
    query = select(Doctor.id, User.full_name.label("name")).join(Doctor.user).where(Doctor.is_deleted == False).order_by(User.full_name)
    result = await db.execute(query)
    
    return [BasicResponse(id=row.id, name=row.name) for row in result.all()]


class DoctorCategoryResponse(BaseModel):
    """Doctor specialty/category filter item."""

    id: str
    name: str
    count: int = 0


@router.get("/category", response_model=list[DoctorCategoryResponse], tags=["Doctors"])
@router.get("/categories", response_model=list[DoctorCategoryResponse], include_in_schema=False)
async def list_doctor_categories(db: DatabaseSession):
    """
    List distinct doctor specialty categories (used by public doctor pages).

    Must be registered before `/{doctor_id}` so paths like `/doctors/category`
    are not treated as a doctor UUID.
    """
    from app.models.doctor import DoctorSpecialization

    # Prefer specialization rows; also include primary_specialty when present
    spec_rows = (
        await db.execute(
            select(
                DoctorSpecialization.specialization,
                func.count(func.distinct(Doctor.id)).label("count"),
            )
            .join(Doctor, Doctor.id == DoctorSpecialization.doctor_id)
            .where(
                Doctor.is_deleted == False,
                Doctor.is_verified == True,
                DoctorSpecialization.is_deleted == False,
            )
            .group_by(DoctorSpecialization.specialization)
            .order_by(DoctorSpecialization.specialization)
        )
    ).all()

    primary_rows = (
        await db.execute(
            select(
                Doctor.primary_specialty,
                func.count(Doctor.id).label("count"),
            )
            .where(
                Doctor.is_deleted == False,
                Doctor.is_verified == True,
                Doctor.primary_specialty.isnot(None),
                Doctor.primary_specialty != "",
            )
            .group_by(Doctor.primary_specialty)
        )
    ).all()

    counts: dict[str, int] = {}
    for name, count in [*spec_rows, *primary_rows]:
        if not name:
            continue
        counts[name] = max(counts.get(name, 0), int(count or 0))

    return [
        DoctorCategoryResponse(id=name, name=name, count=counts[name])
        for name in sorted(counts.keys(), key=str.lower)
    ]


@router.get("", response_model=PaginatedResponse[DoctorListResponse])
async def list_doctors(
    db: DatabaseSession, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    specialization: Optional[str] = None, hospital_id: Optional[UUID] = None, search: Optional[str] = None,
):
    """List doctors with filters."""
    service = DoctorService(db)
    doctors, total = await service.get_list(PaginationParams(page=page, page_size=page_size), specialization, hospital_id, search=search)
    return PaginatedResponse.create(doctors, total, page, page_size)


@router.get("/me", response_model=DoctorResponse)
async def get_my_doctor_profile(current_user: CurrentUser, db: DatabaseSession):
    """Get current user's doctor profile."""
    service = DoctorService(db)
    doctor = await service.get_by_user_id(current_user.id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    return doctor


@router.get("/me/stats", summary="Doctor dashboard stats")
async def get_my_doctor_stats(current_user: CurrentUser, db: DatabaseSession):
    """
    Returns key statistics for the doctor's own dashboard matching the design:

    Top row:
    - today:          consultations scheduled for today
    - pending:        consultations in pending / scheduled / waiting status
    - done:           completed consultations (lifetime)

    Bottom cards:
    - today_schedule: same as `today` (today's appointment count)
    - pending_review: completed consultations with no diagnosis written yet
    - video_sessions: currently in-progress video consultations
    - completed:      lifetime completed count
    - completion_rate: completed / total * 100  (0-100 float)

    Legacy fields (kept for backward compatibility):
    - total_consultations, total_patients, rating, total_reviews,
      consultation_fee, years_of_experience, is_verified
    """
    service = DoctorService(db)
    doctor = await service.get_by_user_id(current_user.id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")

    base = (Consultation.doctor_id == doctor.id, Consultation.is_deleted == False)
    today_date = date.today()

    # ── total (lifetime) ──────────────────────────────────────────────
    total_consultations = (
        await db.execute(select(func.count()).where(*base))
    ).scalar() or 0

    total_patients = (
        await db.execute(
            select(func.count(func.distinct(Consultation.patient_id))).where(*base)
        )
    ).scalar() or 0

    # ── top-row stats ─────────────────────────────────────────────────
    today = (
        await db.execute(
            select(func.count()).where(
                *base,
                cast(Consultation.scheduled_at, Date) == today_date,
            )
        )
    ).scalar() or 0

    pending = (
        await db.execute(
            select(func.count()).where(
                *base,
                Consultation.status.in_(["pending", "scheduled", "waiting"]),
            )
        )
    ).scalar() or 0

    done = (
        await db.execute(
            select(func.count()).where(
                *base,
                Consultation.status == "completed",
            )
        )
    ).scalar() or 0

    # ── bottom-card stats ─────────────────────────────────────────────
    # Pending Review: completed but doctor hasn't written diagnosis yet
    pending_review = (
        await db.execute(
            select(func.count()).where(
                *base,
                Consultation.status == "completed",
                Consultation.diagnosis == None,
            )
        )
    ).scalar() or 0

    # Video Sessions: currently in-progress video consultations
    video_sessions = (
        await db.execute(
            select(func.count()).where(
                *base,
                Consultation.status == "in_progress",
                Consultation.consultation_type == "video",
            )
        )
    ).scalar() or 0

    completion_rate = round((done / total_consultations * 100), 1) if total_consultations > 0 else 0.0

    return {
        # Top row
        "today": today,
        "pending": pending,
        "done": done,
        # Bottom cards
        "today_schedule": today,
        "pending_review": pending_review,
        "video_sessions": video_sessions,
        "completed": done,
        "completion_rate": completion_rate,
        # Legacy / profile fields
        "doctor_id": doctor.id,
        "total_consultations": total_consultations,
        "total_patients": total_patients,
        "rating": doctor.rating,
        "total_reviews": doctor.total_reviews,
        "consultation_fee": doctor.consultation_fee,
        "years_of_experience": doctor.years_of_experience,
        "is_verified": doctor.is_verified,
    }


@router.put("/me", response_model=DoctorResponse)
async def update_my_doctor_profile(data: DoctorUpdate, current_user: CurrentUser, db: DatabaseSession):
    """Update current user's doctor profile."""
    service = DoctorService(db)
    doctor = await service.get_by_user_id(current_user.id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    return await service.update(doctor, data, current_user.id)


@router.put("/me/availability", response_model=list[DoctorAvailabilityResponse])
async def set_my_availability(data: list[DoctorAvailabilityCreate], current_user: CurrentUser, db: DatabaseSession):
    """Set doctor availability schedule."""
    service = DoctorService(db)
    doctor = await service.get_by_user_id(current_user.id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    return await service.set_availability(doctor, data)


# Hospital management endpoints
@router.get("/me/hospital", response_model=DoctorHospitalResponse)
async def get_my_hospital(current_user: CurrentUser, db: DatabaseSession):
    """Get current doctor's hospital information."""
    service = DoctorService(db)
    doctor = await service.get_by_user_id(current_user.id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    
    hospital = await service.get_doctor_hospital(doctor)
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found. Please add hospital information first.")
    return hospital


@router.get("/{doctor_id}/hospital", response_model=DoctorHospitalResponse)
async def get_doctor_hospital(doctor_id: UUID, db: DatabaseSession):
    """Get hospital information for a specific doctor by doctor_id."""
    service = DoctorService(db)
    doctor = await service.get_by_id(doctor_id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    
    hospital = await service.get_doctor_hospital(doctor)
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found. Please add hospital information first.")
    return hospital


@router.post("/me/hospital", response_model=DoctorHospitalResponse, status_code=201)
async def add_my_hospital(data: DoctorHospitalCreate, current_user: CurrentUser, db: DatabaseSession):
    """Add hospital information to current doctor's profile."""
    service = DoctorService(db)
    doctor = await service.get_by_user_id(current_user.id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    
    # Override doctor_id from token
    data.doctor_id = doctor.id
    
    try:
        hospital = await service.add_doctor_hospital(doctor, data, current_user.id)
        return hospital
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{doctor_id}/hospital", response_model=DoctorHospitalResponse, status_code=201)
async def add_doctor_hospital(
    doctor_id: UUID,
    data: DoctorHospitalCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
    require_admin: bool = Query(False, description="If true, requires admin privileges")
):
    """Add hospital information to a doctor's profile by doctor_id."""
    # Verify doctor exists
    service = DoctorService(db)
    doctor = await service.get_by_id(doctor_id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    
    # Ensure doctor_id in request matches the URL parameter
    data.doctor_id = doctor_id
    
    try:
        hospital = await service.add_doctor_hospital(doctor, data, current_user.id)
        return hospital
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/me/hospital", response_model=DoctorHospitalResponse)
async def update_my_hospital(data: DoctorHospitalUpdate, current_user: CurrentUser, db: DatabaseSession):
    """Update current doctor's hospital information."""
    service = DoctorService(db)
    doctor = await service.get_by_user_id(current_user.id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    
    # Override doctor_id from token
    data.doctor_id = doctor.id
    
    try:
        hospital = await service.update_doctor_hospital(doctor, data, current_user.id)
        return hospital
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{doctor_id}/hospital", response_model=DoctorHospitalResponse)
async def update_doctor_hospital(
    doctor_id: UUID,
    data: DoctorHospitalUpdate,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Update a doctor's hospital information by doctor_id."""
    service = DoctorService(db)
    doctor = await service.get_by_id(doctor_id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    
    # Ensure doctor_id in request matches the URL parameter
    data.doctor_id = doctor_id
    
    try:
        hospital = await service.update_doctor_hospital(doctor, data, current_user.id)
        return hospital
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/me/hospital", status_code=204)
async def delete_my_hospital(
    current_user: CurrentUser, 
    db: DatabaseSession,
    delete_hospital: bool = Query(False, description="If true, also soft-delete the hospital record")
):
    """Remove hospital from current doctor's profile."""
    service = DoctorService(db)
    doctor = await service.get_by_user_id(current_user.id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    
    try:
        await service.delete_doctor_hospital(doctor, current_user.id, delete_hospital)
        return None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{doctor_id}/hospital", status_code=204)
async def delete_doctor_hospital(
    doctor_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
    delete_hospital: bool = Query(False, description="If true, also soft-delete the hospital record")
):
    """Remove hospital from a doctor's profile by doctor_id."""
    service = DoctorService(db)
    doctor = await service.get_by_id(doctor_id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    
    try:
        await service.delete_doctor_hospital(doctor, current_user.id, delete_hospital)
        return None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{doctor_id}", response_model=DoctorResponse)
async def get_doctor(doctor_id: UUID, db: DatabaseSession):
    """Get doctor by ID."""
    service = DoctorService(db)
    doctor = await service.get_by_id(doctor_id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return doctor


@router.post("/{doctor_id}/verify", response_model=DoctorResponse, dependencies=[RequireAdmin])
async def verify_doctor(doctor_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Verify a doctor (admin only)."""
    service = DoctorService(db)
    doctor = await service.get_by_id(doctor_id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return await service.verify(doctor, current_user.id)
