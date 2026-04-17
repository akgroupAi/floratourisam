"""Consultation endpoints.

Patient-facing:
  GET   /consultations                       — list my consultations
  GET   /consultations/{id}                  — get consultation details
  POST  /consultations/{id}/join             — get session/meet link to join
  POST  /consultations/{id}/complete         — mark as completed
  POST  /consultations/{id}/cancel           — cancel (delegates to appointment_service)
  POST  /consultations/{id}/rate             — rate a completed consultation

Doctor-facing:
  GET   /consultations/doctor/me             — list my patient consultations
  POST  /consultations/{id}/start            — start consultation (set in_progress)
  POST  /consultations/{id}/complete         — mark as completed with notes
  PUT   /consultations/{id}/notes            — update diagnosis/prescription/notes
  POST  /consultations/{id}/confirm          — confirm a pending appointment
  POST  /consultations/{id}/reject           — reject a pending appointment
"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DatabaseSession, RequireDoctor, RequirePatient
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.consultation import (
    ConsultationCreate,
    ConsultationDoctorUpdate,
    ConsultationListResponse,
    ConsultationRatingRequest,
    ConsultationResponse,
    ConsultationStatusUpdate,
)
from app.services.consultation_service import ConsultationService
from app.services.patient_service import PatientService

router = APIRouter()


# ---------------------------------------------------------------------------
# List consultations
# ---------------------------------------------------------------------------

@router.get("", response_model=PaginatedResponse[ConsultationListResponse])
async def list_consultations(
    current_user: CurrentUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    consultation_status: Optional[str] = Query(default=None, alias="status"),
):
    """List user's consultations (patients see theirs, doctors see theirs)."""
    service = ConsultationService(db)

    if current_user.role == "doctor":
        consultations, total = await service.list_doctor_consultations(
            doctor_user_id=current_user.id,
            page=page,
            page_size=page_size,
            status=consultation_status,
        )
    else:
        patient_service = PatientService(db)
        patient = await patient_service.get_by_user_id(current_user.id)
        if not patient:
            return PaginatedResponse.create([], 0, page, page_size)
        consultations, total = await service.get_list(
            PaginationParams(page=page, page_size=page_size),
            patient_id=patient.id,
        )

    return PaginatedResponse.create(consultations, total, page, page_size)


# ---------------------------------------------------------------------------
# Doctor: list my consultations
# ---------------------------------------------------------------------------

@router.get(
    "/doctor/me",
    response_model=PaginatedResponse[ConsultationListResponse],
    dependencies=[RequireDoctor],
    summary="List doctor's consultations",
)
async def list_doctor_consultations(
    current_user: CurrentUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    consultation_status: Optional[str] = Query(default=None, alias="status"),
):
    """List all consultations assigned to the authenticated doctor."""
    service = ConsultationService(db)
    try:
        consultations, total = await service.list_doctor_consultations(
            doctor_user_id=current_user.id,
            page=page,
            page_size=page_size,
            status=consultation_status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return PaginatedResponse.create(consultations, total, page, page_size)


# ---------------------------------------------------------------------------
# Get consultation detail
# ---------------------------------------------------------------------------

@router.get("/{consultation_id}", response_model=ConsultationResponse)
async def get_consultation(
    consultation_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Get consultation by ID."""
    service = ConsultationService(db)
    consultation = await service.get_by_id(consultation_id)
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
    return consultation


# ---------------------------------------------------------------------------
# Join consultation (get meet link / session info)
# ---------------------------------------------------------------------------

@router.post(
    "/{consultation_id}/join",
    summary="Join consultation — get meet link and session details",
)
async def join_consultation(
    consultation_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Returns the Google Meet link and session details so the user can join."""
    service = ConsultationService(db)
    try:
        return await service.join_consultation(consultation_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# Start consultation (doctor: scheduled → in_progress)
# ---------------------------------------------------------------------------

@router.post(
    "/{consultation_id}/start",
    response_model=ConsultationResponse,
    dependencies=[RequireDoctor],
    summary="Start a consultation",
)
async def start_consultation(
    consultation_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Transition consultation to in_progress. Sets started_at timestamp."""
    service = ConsultationService(db)
    try:
        return await service.start_consultation(consultation_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# Complete consultation (patient or doctor)
# ---------------------------------------------------------------------------

@router.post(
    "/{consultation_id}/complete",
    response_model=ConsultationResponse,
    summary="Mark consultation as completed",
)
async def complete_consultation(
    consultation_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
    body: Optional[ConsultationDoctorUpdate] = None,
):
    """Mark a consultation as completed. Doctor can include notes/diagnosis."""
    service = ConsultationService(db)
    try:
        return await service.complete_consultation(
            consultation_id=consultation_id,
            completed_by=current_user.id,
            doctor_notes=body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# Update doctor notes
# ---------------------------------------------------------------------------

@router.put(
    "/{consultation_id}/notes",
    response_model=ConsultationResponse,
    dependencies=[RequireDoctor],
    summary="Update consultation notes (doctor only)",
)
async def update_doctor_notes(
    consultation_id: UUID,
    body: ConsultationDoctorUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Update diagnosis, prescription, notes, recommendations, follow-up."""
    service = ConsultationService(db)
    try:
        return await service.update_doctor_notes(
            consultation_id=consultation_id,
            doctor_user_id=current_user.id,
            data=body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# Update consultation status (doctor: generic)
# ---------------------------------------------------------------------------

@router.patch(
    "/{consultation_id}/status",
    response_model=ConsultationResponse,
    dependencies=[RequireDoctor],
    summary="Update consultation status (doctor)",
)
async def update_consultation_status(
    consultation_id: UUID,
    body: ConsultationStatusUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Generic status update for doctors.

    Allowed transitions:
    - scheduled  → waiting, in_progress, cancelled, missed
    - waiting    → in_progress, cancelled, missed
    - in_progress → completed, cancelled
    """
    service = ConsultationService(db)
    try:
        return await service.update_status(
            consultation_id=consultation_id,
            new_status=body.status,
            updated_by=current_user.id,
            notes=body.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# Confirm appointment (doctor: pending → scheduled)
# ---------------------------------------------------------------------------

@router.post(
    "/{consultation_id}/confirm",
    response_model=ConsultationResponse,
    dependencies=[RequireDoctor],
    summary="Confirm a pending appointment",
)
async def confirm_appointment(
    consultation_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Doctor accepts a pending appointment. Transitions to scheduled/confirmed."""
    service = ConsultationService(db)
    try:
        return await service.confirm_appointment(consultation_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# Reject appointment (doctor: pending → cancelled)
# ---------------------------------------------------------------------------

class RejectRequest(BaseModel):
    """Rejection reason."""
    reason: Optional[str] = Field(default=None, max_length=500)


@router.post(
    "/{consultation_id}/reject",
    response_model=ConsultationResponse,
    dependencies=[RequireDoctor],
    summary="Reject a pending appointment",
)
async def reject_appointment(
    consultation_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
    body: Optional[RejectRequest] = None,
):
    """Doctor rejects a pending appointment. Transitions to cancelled."""
    service = ConsultationService(db)
    try:
        return await service.reject_appointment(
            consultation_id=consultation_id,
            rejected_by=current_user.id,
            reason=body.reason if body else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# Cancel consultation
# ---------------------------------------------------------------------------

@router.post("/{consultation_id}/cancel")
async def cancel_consultation(
    consultation_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Cancel a consultation. Delegates to appointment service."""
    from app.schemas.consultation import ConsultationCancelRequest
    from app.services.appointment_service import AppointmentService

    # For now, use a default reason since body was not originally required
    service = AppointmentService(db)
    try:
        consultation = await service.cancel_appointment(
            consultation_id=consultation_id,
            reason="Cancelled by user",
            cancelled_by=current_user.id,
        )
        return consultation
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# Rate consultation
# ---------------------------------------------------------------------------

@router.post(
    "/{consultation_id}/rate",
    response_model=ConsultationResponse,
    summary="Rate a completed consultation",
)
async def rate_consultation(
    consultation_id: UUID,
    body: ConsultationRatingRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Submit a rating (1-5) and optional review for a completed consultation."""
    service = ConsultationService(db)
    try:
        return await service.rate_consultation(
            consultation_id=consultation_id,
            patient_user_id=current_user.id,
            rating=body.rating,
            review=body.review,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
