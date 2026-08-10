"""Treatment Proposal endpoints.

Doctor-facing:
  POST  /treatment-proposals                         — create proposal for patient
  PUT   /treatment-proposals/{id}                    — update a pending proposal
  GET   /treatment-proposals/doctor/me               — list proposals I sent

Patient-facing:
  GET   /treatment-proposals/me                      — list proposals I received
  GET   /treatment-proposals/{id}                    — view proposal detail
  POST  /treatment-proposals/{id}/respond            — approve / reject / request revision

Consultation-scoped:
  GET   /treatment-proposals/consultation/{id}       — proposals for a consultation

Admin:
  GET   /treatment-proposals/admin/all               — list all proposals

Proposals do not require admin approval. The patient's response is the only decision;
admins have read access for oversight via /admin/treatment-proposals.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import (
    CurrentUser,
    DatabaseSession,
    RequireAdmin,
    RequireDoctor,
    RequirePatient,
)
from app.schemas.common import PaginatedResponse
from app.schemas.treatment_proposal import (
    ProposalPatientResponse,
    TreatmentProposalCreate,
    TreatmentProposalListResponse,
    TreatmentProposalResponse,
    TreatmentProposalUpdate,
)
from app.services.treatment_proposal_service import TreatmentProposalService

router = APIRouter()


# ---------------------------------------------------------------------------
# Helper to build response dict from model
# ---------------------------------------------------------------------------

def _build_response(proposal) -> dict:
    """Build a response dict from a TreatmentProposal model with related names."""
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

    hospital_name = None
    if proposal.hospital:
        hospital_name = proposal.hospital.name

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
        "hospital_name": hospital_name,
        "treatment_name": proposal.treatment_name,
        "description": proposal.description,
        "estimated_duration": proposal.estimated_duration,
        "proposed_visit_date": proposal.proposed_visit_date,
        "proposed_visit_time": proposal.proposed_visit_time,
        "currency": proposal.currency,
        "consultation_fee": proposal.consultation_fee,
        "surgery_fee": proposal.surgery_fee,
        "hospital_stay_fee": proposal.hospital_stay_fee,
        "medications_fee": proposal.medications_fee,
        "other_fees": proposal.other_fees,
        "other_fees_description": proposal.other_fees_description,
        "total_amount": proposal.total_amount,
        "doctor_notes": proposal.doctor_notes,
        "status": proposal.status,
        "patient_response_notes": proposal.patient_response_notes,
        "responded_at": proposal.responded_at,
        "created_at": proposal.created_at,
        "updated_at": proposal.updated_at,
    }


def _build_list_item(proposal) -> dict:
    """Build a lightweight list response dict."""
    doctor_name = None
    if proposal.doctor:
        user = getattr(proposal.doctor, "user", None)
        doctor_name = user.full_name if user else None

    patient_name = None
    if proposal.patient:
        user = getattr(proposal.patient, "user", None)
        patient_name = user.full_name if user else None

    hospital_name = None
    if proposal.hospital:
        hospital_name = proposal.hospital.name

    return {
        "id": proposal.id,
        "reference_number": proposal.reference_number,
        "consultation_id": proposal.consultation_id,
        "doctor_id": proposal.doctor_id,
        "doctor_name": doctor_name,
        "patient_id": proposal.patient_id,
        "patient_name": patient_name,
        "hospital_name": hospital_name,
        "treatment_name": proposal.treatment_name,
        "currency": proposal.currency,
        "total_amount": proposal.total_amount,
        "status": proposal.status,
        "proposed_visit_date": proposal.proposed_visit_date,
        "created_at": proposal.created_at,
    }


# ---------------------------------------------------------------------------
# Doctor: create proposal
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=TreatmentProposalResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[RequireDoctor],
    summary="Send treatment proposal to patient",
)
async def create_proposal(
    data: TreatmentProposalCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    service = TreatmentProposalService(db)
    try:
        proposal = await service.create_proposal(
            doctor_user_id=current_user.id,
            data=data,
            created_by=current_user.id,
        )
        return _build_response(proposal)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# Doctor: update proposal
# ---------------------------------------------------------------------------

@router.put(
    "/{proposal_id}",
    response_model=TreatmentProposalResponse,
    dependencies=[RequireDoctor],
    summary="Update a pending treatment proposal",
)
async def update_proposal(
    proposal_id: UUID,
    data: TreatmentProposalUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    service = TreatmentProposalService(db)
    try:
        proposal = await service.update_proposal(
            proposal_id=proposal_id,
            doctor_user_id=current_user.id,
            data=data,
        )
        return _build_response(proposal)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# Doctor: list my sent proposals
# ---------------------------------------------------------------------------

@router.get(
    "/doctor/me",
    response_model=PaginatedResponse[TreatmentProposalListResponse],
    dependencies=[RequireDoctor],
    summary="List proposals sent by me",
)
async def list_doctor_proposals(
    current_user: CurrentUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    proposal_status: Optional[str] = Query(default=None, alias="status"),
):
    service = TreatmentProposalService(db)
    proposals, total = await service.list_doctor_proposals(
        doctor_user_id=current_user.id,
        page=page,
        page_size=page_size,
        status=proposal_status,
    )
    items = [_build_list_item(p) for p in proposals]
    return PaginatedResponse.create(items, total, page, page_size)


# ---------------------------------------------------------------------------
# Patient: list my received proposals
# ---------------------------------------------------------------------------

@router.get(
    "/me",
    response_model=PaginatedResponse[TreatmentProposalListResponse],
    summary="List proposals I received",
)
async def list_patient_proposals(
    current_user: CurrentUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    proposal_status: Optional[str] = Query(default=None, alias="status"),
):
    service = TreatmentProposalService(db)
    proposals, total = await service.list_patient_proposals(
        patient_user_id=current_user.id,
        page=page,
        page_size=page_size,
        status=proposal_status,
    )
    items = [_build_list_item(p) for p in proposals]
    return PaginatedResponse.create(items, total, page, page_size)


# ---------------------------------------------------------------------------
# Get proposal detail
# ---------------------------------------------------------------------------

@router.get(
    "/{proposal_id}",
    response_model=TreatmentProposalResponse,
    summary="Get treatment proposal detail",
)
async def get_proposal(
    proposal_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Get a proposal.

    Restricted to the doctor who sent it, the patient who received it, and admins —
    a proposal carries a diagnosis and a full cost breakdown.
    """
    service = TreatmentProposalService(db)
    proposal = await service.get_proposal(proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if not await service.can_view_proposal(proposal, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this proposal",
        )
    return _build_response(proposal)


# ---------------------------------------------------------------------------
# Consultation-scoped list
# ---------------------------------------------------------------------------

@router.get(
    "/consultation/{consultation_id}",
    response_model=list[TreatmentProposalListResponse],
    summary="List proposals for a consultation",
)
async def list_consultation_proposals(
    consultation_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    service = TreatmentProposalService(db)
    proposals = await service.list_consultation_proposals(consultation_id)
    return [_build_list_item(p) for p in proposals]


# ---------------------------------------------------------------------------
# Patient: respond to proposal
# ---------------------------------------------------------------------------

@router.post(
    "/{proposal_id}/respond",
    response_model=TreatmentProposalResponse,
    summary="Approve, reject, or request revision",
)
async def patient_respond(
    proposal_id: UUID,
    body: ProposalPatientResponse,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    service = TreatmentProposalService(db)
    try:
        proposal = await service.patient_respond(
            proposal_id=proposal_id,
            patient_user_id=current_user.id,
            action=body.action,
            notes=body.notes,
        )
        return _build_response(proposal)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# Admin: list all proposals
# ---------------------------------------------------------------------------

@router.get(
    "/admin/all",
    response_model=PaginatedResponse[TreatmentProposalListResponse],
    dependencies=[RequireAdmin],
    summary="Admin: list all proposals",
)
async def admin_list_proposals(
    current_user: CurrentUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    proposal_status: Optional[str] = Query(default=None, alias="status"),
):
    service = TreatmentProposalService(db)
    proposals, total = await service.list_all_proposals(
        page=page,
        page_size=page_size,
        status=proposal_status,
    )
    items = [_build_list_item(p) for p in proposals]
    return PaginatedResponse.create(items, total, page, page_size)


