"""Appointment scheduling schemas."""

from datetime import date, datetime, time
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import BaseSchema
from app.utils.enums import ConsultationStatus, ConsultationType


class AppointmentCreate(BaseModel):
    """Request body to schedule a new appointment."""

    doctor_id: UUID
    consultation_type: ConsultationType = ConsultationType.VIDEO
    scheduled_date: date
    scheduled_time: time  # Local time of the slot (e.g. 10:00)
    duration_minutes: int = Field(default=30, ge=15, le=120)
    reason: Optional[str] = Field(default=None, max_length=1000)
    symptoms: Optional[str] = Field(default=None, max_length=2000)
    symptom_duration: Optional[str] = Field(default=None, max_length=100)
    timezone: str = Field(default="UTC", max_length=50)


class AppointmentCancelRequest(BaseModel):
    """Request body to cancel an appointment."""

    cancellation_reason: str = Field(..., max_length=500)


class TimeSlot(BaseModel):
    """A single time slot for a doctor on a given day."""

    time: time
    formatted: str  # e.g. "10:00 AM"
    is_available: bool


class AvailableSlotsResponse(BaseModel):
    """Response listing available time slots for a doctor on a date."""

    doctor_id: UUID
    date: date
    consultation_type: Optional[str] = None
    slot_duration_minutes: int
    slots: List[TimeSlot]


class AppointmentSummary(BaseSchema):
    """Lightweight appointment summary for list views."""

    id: UUID
    reference_number: str
    booking_reference: Optional[str] = None
    doctor_id: UUID
    doctor_name: Optional[str] = None
    doctor_specialization: Optional[str] = None
    consultation_type: str
    status: str
    scheduled_at: datetime
    duration_minutes: int
    fee: float
    is_paid: bool
    meet_link: Optional[str] = None
    created_at: datetime


class AppointmentResponse(BaseSchema):
    """Full appointment detail response returned after booking."""

    id: UUID
    reference_number: str
    booking_reference: Optional[str] = None

    # Participants
    patient_id: UUID
    patient_name: Optional[str] = None
    patient_email: Optional[str] = None
    doctor_id: UUID
    doctor_name: Optional[str] = None
    doctor_email: Optional[str] = None
    doctor_specialization: Optional[str] = None
    hospital_name: Optional[str] = None

    # Scheduling
    consultation_type: str
    status: str
    scheduled_at: datetime
    duration_minutes: int
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

    # Patient input
    reason: Optional[str] = None
    symptoms: Optional[str] = None
    symptom_duration: Optional[str] = None

    # Doctor notes (populated after consultation)
    diagnosis: Optional[str] = None
    prescription: Optional[str] = None
    notes: Optional[str] = None
    recommendations: Optional[str] = None
    follow_up_required: bool = False
    follow_up_date: Optional[datetime] = None

    # Video meeting
    meet_link: Optional[str] = None  # Google Meet URL for VIDEO type
    session_id: Optional[str] = None

    # Payment
    fee: float
    is_paid: bool
    payment_id: Optional[UUID] = None

    # Cancellation
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None

    # Calendar events
    patient_event_id: Optional[UUID] = None
    doctor_event_id: Optional[UUID] = None

    created_at: datetime
    updated_at: datetime
