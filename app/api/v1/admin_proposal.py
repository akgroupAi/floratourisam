"""Admin treatment proposal oversight.

Who sent each proposal, the money involved, and the full detail behind it.

Read-only: proposals go from doctor to patient without admin approval, so there is no
review action here.
"""

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DatabaseSession, RequireAdmin
from app.schemas.common import PaginatedResponse
from app.schemas.treatment_proposal import (
    AdminProposalListResponse,
    AdminProposalStatsResponse,
    TreatmentProposalResponse,
)
from app.services.treatment_proposal_service import TreatmentProposalService

router = APIRouter()


def _admin_list_item(proposal) -> dict:
    """List row including the approval fields a dashboard needs."""
    doctor_name = None
    doctor_specialization = None
    if proposal.doctor:
        user = getattr(proposal.doctor, "user", None)
        doctor_name = user.full_name if user else None
        doctor_specialization = proposal.doctor.primary_specialty

    patient_name = None
    patient_email = None
    if proposal.patient:
        user = getattr(proposal.patient, "user", None)
        patient_name = user.full_name if user else None
        patient_email = user.email if user else None

    return {
        "id": proposal.id,
        "reference_number": proposal.reference_number,
        "consultation_id": proposal.consultation_id,
        "doctor_id": proposal.doctor_id,
        "doctor_name": doctor_name,
        "doctor_specialization": doctor_specialization,
        "patient_id": proposal.patient_id,
        "patient_name": patient_name,
        "patient_email": patient_email,
        "hospital_id": proposal.hospital_id,
        "hospital_name": proposal.hospital.name if proposal.hospital else None,
        "treatment_name": proposal.treatment_name,
        "currency": proposal.currency,
        "total_amount": proposal.total_amount,
        "status": proposal.status,
        "responded_at": proposal.responded_at,
        "proposed_visit_date": proposal.proposed_visit_date,
        "created_at": proposal.created_at,
        "updated_at": proposal.updated_at,
    }


@router.get(
    "/stats",
    response_model=AdminProposalStatsResponse,
    dependencies=[RequireAdmin],
    summary="Proposal dashboard statistics",
)
async def get_proposal_stats(
    db: DatabaseSession,
    top_doctors: int = Query(5, ge=1, le=20, description="How many top senders to return"),
):
    """
    Everything the proposal dashboard needs in one call: the funnel by status, how many
    await admin review, budget totals (proposed, accepted, and sitting unreviewed), and
    which doctors are sending the most.
    """
    return await TreatmentProposalService(db).admin_stats(top_doctors=top_doctors)


@router.get(
    "",
    response_model=PaginatedResponse[AdminProposalListResponse],
    dependencies=[RequireAdmin],
    summary="List treatment proposals",
)
async def list_proposals(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="pending, approved, rejected, revision_requested"),
    doctor_id: Optional[UUID] = Query(None, description="Proposals sent by one doctor"),
    patient_id: Optional[UUID] = Query(None, description="Proposals received by one patient"),
    hospital_id: Optional[UUID] = Query(None),
    search: Optional[str] = Query(None, description="Reference, treatment, doctor or patient name/email"),
    min_amount: Optional[float] = Query(None, ge=0),
    max_amount: Optional[float] = Query(None, ge=0),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    sort_by: str = Query("created_at", pattern="^(created_at|amount|amount_asc|visit_date)$"),
):
    """
    Proposals across every doctor and patient, newest first.

    Each row carries the sender (`doctor_name`), the recipient (`patient_name`), the
    budget (`total_amount` + `currency`), and the patient's decision (`status`).

    Read-only oversight: proposals go straight from doctor to patient and need no
    admin approval.
    """
    proposals, total = await TreatmentProposalService(db).admin_list_proposals(
        page=page,
        page_size=page_size,
        status=status,
        doctor_id=doctor_id,
        patient_id=patient_id,
        hospital_id=hospital_id,
        search=search,
        min_amount=min_amount,
        max_amount=max_amount,
        from_date=from_date,
        to_date=to_date,
        sort_by=sort_by,
    )
    return PaginatedResponse.create(
        [_admin_list_item(p) for p in proposals], total, page, page_size
    )


@router.get(
    "/{proposal_id}",
    response_model=TreatmentProposalResponse,
    dependencies=[RequireAdmin],
    summary="Get proposal detail",
)
async def get_proposal_detail(proposal_id: UUID, db: DatabaseSession):
    """
    Full proposal: the itemised cost breakdown (consultation, surgery, hospital stay,
    medications, other), the doctor's notes and description, the proposed visit date,
    and the patient's response.
    """
    from app.api.v1.treatment_proposals import _build_response

    proposal = await TreatmentProposalService(db).get_proposal(proposal_id)
    if not proposal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")
    return _build_response(proposal)
