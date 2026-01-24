"""Doctor endpoints."""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query
from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin, RequireDoctor
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.doctor import DoctorCreate, DoctorListResponse, DoctorResponse, DoctorUpdate, DoctorAvailabilityCreate
from app.services.doctor_service import DoctorService

router = APIRouter()


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


@router.put("/me", response_model=DoctorResponse)
async def update_my_doctor_profile(data: DoctorUpdate, current_user: CurrentUser, db: DatabaseSession):
    """Update current user's doctor profile."""
    service = DoctorService(db)
    doctor = await service.get_by_user_id(current_user.id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    return await service.update(doctor, data, current_user.id)


@router.put("/me/availability", response_model=list)
async def set_my_availability(data: list[DoctorAvailabilityCreate], current_user: CurrentUser, db: DatabaseSession):
    """Set doctor availability schedule."""
    service = DoctorService(db)
    doctor = await service.get_by_user_id(current_user.id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    return await service.set_availability(doctor, data)


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
