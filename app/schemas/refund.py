"""Cancellation policy and refund queue schemas."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RefundLine(BaseModel):
    """One line of a refund breakdown. Negative amounts are deductions."""

    label: str
    amount: float


class RefundPreviewResponse(BaseModel):
    """What cancelling a booking right now would return. Nothing is changed."""

    booking_id: str
    reference_number: str
    total_price: float
    currency: Optional[str] = None

    refund_amount: float
    cancellation_charge: float
    platform_fee_retained: float
    refundable_subtotal: float

    hours_before_start: Optional[float] = Field(
        None, description="Hours until the booking starts; null if it has no start time"
    )
    within_free_window: bool
    is_refundable: bool
    reason: str
    lines: List[RefundLine] = []


class CancellationPolicyResponse(BaseModel):
    """The active policy, for a booking page or terms section."""

    free_window_hours: int
    cancellation_charge_percent: float
    platform_fee_refundable: bool
    summary: str


class PendingRefundItem(BaseModel):
    """A refund waiting to be released."""

    booking_id: UUID
    reference_number: str
    booking_type: Optional[str] = None
    patient_name: Optional[str] = None
    patient_email: Optional[str] = None
    total_price: float
    platform_fee: Optional[float] = None
    cancellation_charge: Optional[float] = None
    refund_amount: Optional[float] = None
    currency: Optional[str] = None
    refund_status: str
    refund_requested_at: Optional[datetime] = None
    waiting_hours: Optional[float] = Field(
        None, description="How long the customer has been waiting"
    )
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    refund_note: Optional[str] = Field(
        None, description="Gateway failure, or the rejection reason"
    )
    payment_id: Optional[UUID] = None


class RefundApproveRequest(BaseModel):
    """Release a queued refund.

    `amount` overrides the computed figure — for a goodwill exception or a partial
    settlement. Leave it out to pay exactly what the policy calculated.
    """

    amount: Optional[float] = Field(
        None, gt=0, description="Override the computed amount. Omit to use the policy figure."
    )


class RefundRejectRequest(BaseModel):
    """Decline a queued refund. The reason is kept — the customer will ask."""

    reason: str = Field(..., min_length=3, max_length=500)


class RefundApproveResponse(BaseModel):
    """Result of releasing a refund to the gateway."""

    booking_id: str
    refund_amount: float
    refund_reference: Optional[str] = Field(None, description="Razorpay refund id")
    status: str


class RefundStatsResponse(BaseModel):
    """Queue health — what is owed, and how long people have waited."""

    pending: int
    failed: int
    processed: int
    rejected: int
    pending_value: float = Field(..., description="Money owed but not yet paid out")
    processed_value: float
    oldest_waiting_hours: Optional[float] = Field(
        None, description="Longest a customer has been waiting for a refund"
    )


class PatientRefundStatus(BaseModel):
    """The refund position on the patient's own booking.

    Written for display: `status_label` and `message` are ready to render, so the
    frontend does not reinvent the wording per screen.
    """

    booking_id: str
    reference_number: str
    currency: Optional[str] = None

    refund_status: str = Field(..., description="none | pending | processed | rejected | failed")
    status_label: str = Field(..., description="Human-readable, ready to display")
    refund_amount: float = 0.0
    cancellation_charge: float = 0.0

    is_refund_due: bool = Field(..., description="True when money is coming back")
    message: str = Field(..., description="What to tell the patient right now")
    expected_days: Optional[str] = Field(
        None, description="How long the money takes to arrive, once released"
    )

    requested_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    reference: Optional[str] = Field(None, description="Gateway refund id, once issued")
