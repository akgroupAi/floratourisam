"""Treatment Proposal schemas."""

from datetime import date, datetime, time
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import BaseSchema


# ---------------------------------------------------------------------------
# Enums / Constants
# ---------------------------------------------------------------------------

PROPOSAL_STATUSES = {"pending", "approved", "rejected", "revision_requested"}


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class CostBreakdown(BaseModel):
    """Cost breakdown for a treatment proposal."""
    consultation_fee: float = Field(default=0.0, ge=0)
    surgery_fee: float = Field(default=0.0, ge=0)
    hospital_stay_fee: float = Field(default=0.0, ge=0)
    medications_fee: float = Field(default=0.0, ge=0)
    other_fees: float = Field(default=0.0, ge=0)
    other_fees_description: Optional[str] = Field(default=None, max_length=500)


class TreatmentProposalCreate(BaseModel):
    """Request body for doctor to create a treatment proposal."""

    # Required
    patient_id: UUID
    treatment_name: str = Field(..., min_length=1, max_length=500)

    # Optional context
    consultation_id: Optional[UUID] = None
    hospital_id: Optional[UUID] = None
    description: Optional[str] = Field(default=None, max_length=5000)
    estimated_duration: Optional[str] = Field(default=None, max_length=200)

    # Visit schedule
    proposed_visit_date: Optional[date] = None
    proposed_visit_time: Optional[time] = None

    # Cost
    currency: str = Field(default="USD", max_length=10)
    consultation_fee: float = Field(default=0.0, ge=0)
    surgery_fee: float = Field(default=0.0, ge=0)
    hospital_stay_fee: float = Field(default=0.0, ge=0)
    medications_fee: float = Field(default=0.0, ge=0)
    other_fees: float = Field(default=0.0, ge=0)
    other_fees_description: Optional[str] = Field(default=None, max_length=500)

    # Doctor notes
    doctor_notes: Optional[str] = Field(default=None, max_length=5000)


class TreatmentProposalUpdate(BaseModel):
    """Doctor can update a pending proposal."""
    treatment_name: Optional[str] = Field(default=None, max_length=500)
    description: Optional[str] = Field(default=None, max_length=5000)
    estimated_duration: Optional[str] = Field(default=None, max_length=200)
    proposed_visit_date: Optional[date] = None
    proposed_visit_time: Optional[time] = None
    currency: Optional[str] = Field(default=None, max_length=10)
    consultation_fee: Optional[float] = Field(default=None, ge=0)
    surgery_fee: Optional[float] = Field(default=None, ge=0)
    hospital_stay_fee: Optional[float] = Field(default=None, ge=0)
    medications_fee: Optional[float] = Field(default=None, ge=0)
    other_fees: Optional[float] = Field(default=None, ge=0)
    other_fees_description: Optional[str] = Field(default=None, max_length=500)
    doctor_notes: Optional[str] = Field(default=None, max_length=5000)


class ProposalPatientResponse(BaseModel):
    """Patient approves / rejects / requests revision."""
    action: str = Field(..., description="approve | reject | request_revision")
    notes: Optional[str] = Field(default=None, max_length=2000)


class ProposalAdminReview(BaseModel):
    """Admin approves or rejects a proposal."""
    approved: bool
    notes: Optional[str] = Field(default=None, max_length=2000)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class TreatmentProposalListResponse(BaseSchema):
    """Lightweight proposal for list views."""
    id: UUID
    reference_number: str
    consultation_id: Optional[UUID] = None
    doctor_id: UUID
    doctor_name: Optional[str] = None
    patient_id: UUID
    patient_name: Optional[str] = None
    hospital_name: Optional[str] = None
    treatment_name: str
    currency: str
    total_amount: float
    status: str
    proposed_visit_date: Optional[date] = None
    created_at: datetime


class TreatmentProposalResponse(BaseSchema):
    """Full proposal detail."""
    id: UUID
    reference_number: str

    # Context
    consultation_id: Optional[UUID] = None
    doctor_id: UUID
    doctor_name: Optional[str] = None
    doctor_specialization: Optional[str] = None
    patient_id: UUID
    patient_name: Optional[str] = None
    patient_email: Optional[str] = None
    hospital_id: Optional[UUID] = None
    hospital_name: Optional[str] = None

    # Treatment details
    treatment_name: str
    description: Optional[str] = None
    estimated_duration: Optional[str] = None
    proposed_visit_date: Optional[date] = None
    proposed_visit_time: Optional[time] = None

    # Cost breakdown
    currency: str
    consultation_fee: float
    surgery_fee: float
    hospital_stay_fee: float
    medications_fee: float
    other_fees: float
    other_fees_description: Optional[str] = None
    total_amount: float

    # Notes
    doctor_notes: Optional[str] = None

    # Status & response
    status: str
    patient_response_notes: Optional[str] = None
    responded_at: Optional[datetime] = None

    # Admin review
    admin_approved: Optional[bool] = None
    admin_notes: Optional[str] = None
    admin_reviewed_at: Optional[datetime] = None

    created_at: datetime
    updated_at: datetime
