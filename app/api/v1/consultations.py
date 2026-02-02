"""Consultation endpoints."""

from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, Depends
from app.api.deps import CurrentUser, DatabaseSession, RequirePatient, RequireDoctor
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.consultation import ConsultationCreate, ConsultationListResponse, ConsultationResponse
from app.services.consultation_service import ConsultationService
from app.services.patient_service import PatientService

router = APIRouter()


@router.get("", response_model=PaginatedResponse[ConsultationListResponse])
async def list_consultations(current_user: CurrentUser, db: DatabaseSession, page: int = Query(1, ge=1), page_size: int = Query(20)):
    """List user's consultations."""
    service = ConsultationService(db)
    
    # Check if user is patient or doctor
    patient_id = None
    doctor_id = None
    
    if current_user.role == "patient":
        patient_service = PatientService(db)
        patient = await patient_service.get_by_user_id(current_user.id)
        if patient:
            patient_id = patient.id
    elif current_user.role == "doctor":
        # Simplified - assume doctor logic exists or check user role
        # For now, just listing for patient primarily based on requirements
        pass
        
    consultations, total = await service.get_list(PaginationParams(page=page, page_size=page_size), patient_id=patient_id)
    return PaginatedResponse.create(consultations, total, page, page_size)


@router.post("", response_model=ConsultationResponse, dependencies=[RequirePatient])
async def create_consultation(data: ConsultationCreate, current_user: CurrentUser, db: DatabaseSession):
    """Create a new consultation booking."""
    service = ConsultationService(db)
    patient_service = PatientService(db)
    patient = await patient_service.get_or_create(current_user.id)
    
    return await service.create(patient.id, data, current_user.id)


@router.get("/{consultation_id}", response_model=ConsultationResponse)
async def get_consultation(consultation_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Get consultation by ID."""
    service = ConsultationService(db)
    consultation = await service.get_by_id(consultation_id)
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
    return consultation


@router.post("/{consultation_id}/cancel")
async def cancel_consultation(consultation_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Cancel a consultation."""
    # Simplified - endpoint stub
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/{consultation_id}/join")
async def join_consultation(consultation_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Get session details to join consultation."""
    # Simplified - endpoint stub
    raise HTTPException(status_code=501, detail="Not implemented")
