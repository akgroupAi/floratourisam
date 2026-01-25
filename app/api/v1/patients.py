"""Patient endpoints."""

from uuid import UUID
from fastapi import APIRouter, HTTPException, Query
from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin, RequirePatient
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.patient import PatientCreate, PatientDetailResponse, PatientResponse, PatientUpdate
from app.services.patient_service import PatientService

router = APIRouter()


@router.get("/me", response_model=PatientDetailResponse)
async def get_my_profile(db: DatabaseSession, current_user = RequirePatient):
    """Get current user's patient profile."""
    service = PatientService(db)
    patient = await service.get_or_create(current_user.id)
    return patient


@router.put("/me", response_model=PatientResponse)
async def update_my_profile(data: PatientUpdate, db: DatabaseSession, current_user = RequirePatient):
    """Update current user's patient profile."""
    service = PatientService(db)
    patient = await service.get_or_create(current_user.id)
    return await service.update(patient, data, current_user.id)


@router.get("", response_model=PaginatedResponse[PatientResponse], dependencies=[RequireAdmin])
async def list_patients(db: DatabaseSession, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), search: str = None):
    """List patients (admin only)."""
    service = PatientService(db)
    patients, total = await service.get_list(PaginationParams(page=page, page_size=page_size), search)
    return PaginatedResponse.create(patients, total, page, page_size)


@router.get("/{patient_id}", response_model=PatientDetailResponse, dependencies=[RequireAdmin])
async def get_patient(patient_id: UUID, db: DatabaseSession):
    """Get patient by ID (admin only)."""
    service = PatientService(db)
    patient = await service.get_by_id(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient
