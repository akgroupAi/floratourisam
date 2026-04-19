"""Consultation schemas."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import BaseSchema
from app.utils.enums import ConsultationStatus, ConsultationType


class ConsultationCreate(BaseModel):
    """Consultation creation schema."""

    doctor_id: UUID
    consultation_type: ConsultationType = ConsultationType.VIDEO
    scheduled_at: datetime
    duration_minutes: int = Field(default=30, ge=15, le=120)
    reason: Optional[str] = Field(default=None, max_length=1000)
    symptoms: Optional[str] = Field(default=None, max_length=2000)
    symptom_duration: Optional[str] = Field(default=None, max_length=100)


class ConsultationUpdate(BaseModel):
    """Consultation update by patient."""

    scheduled_at: Optional[datetime] = None
    reason: Optional[str] = Field(default=None, max_length=1000)
    symptoms: Optional[str] = Field(default=None, max_length=2000)


class ConsultationDoctorUpdate(BaseModel):
    """Consultation update by doctor."""

    diagnosis: Optional[str] = None
    prescription: Optional[str] = None
    notes: Optional[str] = None
    recommendations: Optional[str] = None
    follow_up_required: Optional[bool] = None
    follow_up_date: Optional[datetime] = None


class ConsultationStatusUpdate(BaseModel):
    """Consultation status update."""

    status: ConsultationStatus
    notes: Optional[str] = None


class ConsultationCancelRequest(BaseModel):
    """Consultation cancellation request."""

    cancellation_reason: str = Field(..., max_length=500)


class ConsultationRatingRequest(BaseModel):
    """Consultation rating request."""

    rating: int = Field(..., ge=1, le=5)
    review: Optional[str] = Field(default=None, max_length=2000)


class ConsultationListResponse(BaseSchema):
    """Consultation list response."""

    id: UUID
    reference_number: str
    patient_id: UUID
    doctor_id: UUID
    consultation_type: str
    status: str
    scheduled_at: datetime
    duration_minutes: int
    fee: float
    is_paid: bool

    # Session
    meet_link: Optional[str] = None

    # Summary info
    patient_name: Optional[str] = None
    doctor_name: Optional[str] = None
    doctor_specialization: Optional[str] = None
    created_at: datetime

    @model_validator(mode="before")
    @classmethod
    def extract_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            obj = data
            data = {}
            for field in cls.model_fields:
                val = getattr(obj, field, None)
                if val is not None:
                    data[field] = val
            # Extract meet_link from session_data
            session_data = getattr(obj, "session_data", None)
            if session_data and isinstance(session_data, dict):
                data.setdefault("meet_link", session_data.get("meet_link"))
            # Extract names from relationships
            doctor = getattr(obj, "doctor", None)
            if doctor:
                user = getattr(doctor, "user", None)
                if user:
                    data.setdefault("doctor_name", getattr(user, "full_name", None))
                data.setdefault("doctor_specialization", getattr(doctor, "primary_specialty", None))
            patient = getattr(obj, "patient", None)
            if patient:
                user = getattr(patient, "user", None)
                if user:
                    data.setdefault("patient_name", getattr(user, "full_name", None))
        return data


class ConsultationResponse(BaseSchema):
    """Consultation detail response."""

    id: UUID
    reference_number: str
    patient_id: UUID
    doctor_id: UUID
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

    # Doctor notes
    diagnosis: Optional[str] = None
    prescription: Optional[str] = None
    notes: Optional[str] = None
    recommendations: Optional[str] = None
    follow_up_required: bool = False
    follow_up_date: Optional[datetime] = None

    # Session
    meet_link: Optional[str] = None
    session_id: Optional[str] = None
    recording_url: Optional[str] = None

    # Payment
    fee: float
    is_paid: bool
    payment_id: Optional[UUID] = None

    # Rating
    rating: Optional[int] = None
    review: Optional[str] = None

    # Cancellation
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None

    # Timestamps
    created_at: datetime
    updated_at: datetime

    # Related info
    patient_name: Optional[str] = None
    patient_email: Optional[str] = None
    doctor_name: Optional[str] = None
    doctor_email: Optional[str] = None
    doctor_specialization: Optional[str] = None
    hospital_name: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def extract_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            obj = data
            data = {}
            for field in cls.model_fields:
                val = getattr(obj, field, None)
                if val is not None:
                    data[field] = val
            # Extract meet_link from session_data
            session_data = getattr(obj, "session_data", None)
            if session_data and isinstance(session_data, dict):
                data.setdefault("meet_link", session_data.get("meet_link"))
            # Extract from relationships
            doctor = getattr(obj, "doctor", None)
            if doctor:
                user = getattr(doctor, "user", None)
                if user:
                    data.setdefault("doctor_name", getattr(user, "full_name", None))
                    data.setdefault("doctor_email", getattr(user, "email", None))
                data.setdefault("doctor_specialization", getattr(doctor, "primary_specialty", None))
                hospital = getattr(doctor, "hospital", None)
                if hospital:
                    data.setdefault("hospital_name", getattr(hospital, "name", None))
            patient = getattr(obj, "patient", None)
            if patient:
                user = getattr(patient, "user", None)
                if user:
                    data.setdefault("patient_name", getattr(user, "full_name", None))
                    data.setdefault("patient_email", getattr(user, "email", None))
        return data


class ConsultationSessionResponse(BaseModel):
    """Video/chat session details for joining."""

    consultation_id: UUID
    session_id: str
    session_type: str
    session_url: str
    session_token: Optional[str] = None
    expires_at: datetime


class ConsultationStatsResponse(BaseModel):
    """Consultation statistics."""

    total_consultations: int
    completed_consultations: int
    cancelled_consultations: int
    pending_consultations: int
    average_rating: Optional[float] = None
    total_revenue: float
    consultations_by_type: dict[str, int]
    consultations_by_status: dict[str, int]
