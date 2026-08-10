"""Admin consultation and appointment monitoring.

The public `/consultations` router resolves the caller to a doctor or patient, so an
admin sees nothing there. Everything here spans the whole platform.
"""

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.consultation import (
    AdminConsultationStatsResponse,
    ConsultationCancelRequest,
    ConsultationListResponse,
    ConsultationResponse,
    ConsultationStatusUpdate,
)
from app.services.consultation_service import ConsultationService
from app.utils.enums import ConsultationStatus

router = APIRouter()


@router.get(
    "/stats",
    response_model=AdminConsultationStatsResponse,
    dependencies=[RequireAdmin],
    summary="Consultation statistics",
)
async def get_consultation_stats(db: DatabaseSession):
    """Counts by status and type, today's load, plus completion, cancellation, and no-show rates."""
    service = ConsultationService(db)
    return await service.get_admin_stats()


@router.get(
    "",
    response_model=PaginatedResponse[ConsultationListResponse],
    dependencies=[RequireAdmin],
    summary="List all consultations",
)
async def list_consultations(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="pending, scheduled, waiting, in_progress, completed, cancelled, missed"),
    consultation_type: Optional[str] = Query(None, description="video, chat, in_person"),
    doctor_id: Optional[UUID] = Query(None),
    patient_id: Optional[UUID] = Query(None),
    hospital_id: Optional[UUID] = Query(None, description="All consultations for a hospital's doctors"),
    is_paid: Optional[bool] = Query(None),
    search: Optional[str] = Query(None, description="Reference number, doctor or patient name/email"),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    today_only: bool = Query(False, description="Only consultations scheduled today"),
    active_only: bool = Query(False, description="Only waiting or in-progress right now"),
    unconfirmed_only: bool = Query(False, description="Only pending — the ones needing a nudge"),
):
    """List consultations across every doctor and patient, newest scheduled first."""
    service = ConsultationService(db)
    items, total = await service.get_admin_list(
        PaginationParams(page=page, page_size=page_size),
        status=status,
        consultation_type=consultation_type,
        doctor_id=doctor_id,
        patient_id=patient_id,
        hospital_id=hospital_id,
        is_paid=is_paid,
        search=search,
        from_date=from_date,
        to_date=to_date,
        today_only=today_only,
        active_only=active_only,
        unconfirmed_only=unconfirmed_only,
    )
    return PaginatedResponse.create(items, total, page, page_size)


@router.get(
    "/{consultation_id}",
    response_model=ConsultationResponse,
    dependencies=[RequireAdmin],
    summary="Get consultation detail",
)
async def get_consultation(consultation_id: UUID, db: DatabaseSession):
    """Full consultation record for any doctor or patient."""
    service = ConsultationService(db)
    consultation = await service.get_by_id(consultation_id)
    if not consultation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation not found")
    return consultation


@router.patch(
    "/{consultation_id}/status",
    response_model=ConsultationResponse,
    dependencies=[RequireAdmin],
    summary="Override consultation status",
)
async def update_consultation_status(
    consultation_id: UUID,
    data: ConsultationStatusUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """
    Move a consultation to a given status on the users' behalf.

    For unsticking a consultation the doctor or patient left stranded — a `pending`
    that was never confirmed, or an `in_progress` nobody closed.

    The normal state machine still applies: invalid transitions return `400` listing
    what is allowed. Admins can act on any consultation, but cannot put one into a
    state the workflow does not permit.
    """
    service = ConsultationService(db)
    consultation = await service.get_by_id(consultation_id)
    if not consultation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation not found")

    try:
        return await service.update_status(
            consultation_id, data.status, current_user.id, notes=data.notes
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/{consultation_id}/cancel",
    response_model=MessageResponse,
    dependencies=[RequireAdmin],
    summary="Cancel a consultation on a user's behalf",
)
async def cancel_consultation(
    consultation_id: UUID,
    data: ConsultationCancelRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Cancel a consultation for a patient or doctor who cannot do it themselves.

    Also cancels the linked booking, same as a user-initiated cancellation.
    """
    service = ConsultationService(db)
    consultation = await service.get_by_id(consultation_id)
    if not consultation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation not found")

    try:
        await service.update_status(
            consultation_id,
            ConsultationStatus.CANCELLED,
            current_user.id,
            notes=data.cancellation_reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return MessageResponse(message="Consultation cancelled")
