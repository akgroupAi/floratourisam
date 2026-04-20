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
    patient_user_id: Optional[UUID] = None
    doctor_user_id: Optional[UUID] = None
    consultation_type: str
    status: str
    scheduled_at: datetime
    duration_minutes: int
    fee: float
    is_paid: bool

    # Session
    meet_link: Optional[str] = None

    # Patient info
    patient_name: Optional[str] = None
    patient_avatar_url: Optional[str] = None

    # Doctor info
    doctor_name: Optional[str] = None
    doctor_avatar_url: Optional[str] = None
    doctor_title: Optional[str] = None
    doctor_specialization: Optional[str] = None

    # Hospital info
    hospital_name: Optional[str] = None

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
            # Extract from relationships
            doctor = getattr(obj, "doctor", None)
            if doctor:
                data.setdefault("doctor_user_id", getattr(doctor, "user_id", None))
                user = getattr(doctor, "user", None)
                if user:
                    data.setdefault("doctor_name", getattr(user, "full_name", None))
                    data.setdefault("doctor_avatar_url", getattr(user, "avatar_url", None))
                data.setdefault("doctor_title", getattr(doctor, "title", None))
                data.setdefault("doctor_specialization", getattr(doctor, "primary_specialty", None))
                hospital = getattr(doctor, "hospital", None)
                if hospital:
                    data.setdefault("hospital_name", getattr(hospital, "name", None))
            patient = getattr(obj, "patient", None)
            if patient:
                data.setdefault("patient_user_id", getattr(patient, "user_id", None))
                user = getattr(patient, "user", None)
                if user:
                    data.setdefault("patient_name", getattr(user, "full_name", None))
                    data.setdefault("patient_avatar_url", getattr(user, "avatar_url", None))
        return data


class ConsultationResponse(BaseSchema):
    """Consultation detail response."""

    id: UUID
    reference_number: str
    patient_id: UUID
    doctor_id: UUID
    patient_user_id: Optional[UUID] = None
    doctor_user_id: Optional[UUID] = None
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

    # Patient info
    patient_name: Optional[str] = None
    patient_email: Optional[str] = None
    patient_phone: Optional[str] = None
    patient_avatar_url: Optional[str] = None
    patient_gender: Optional[str] = None
    patient_blood_group: Optional[str] = None

    # Doctor info
    doctor_name: Optional[str] = None
    doctor_email: Optional[str] = None
    doctor_phone: Optional[str] = None
    doctor_avatar_url: Optional[str] = None
    doctor_title: Optional[str] = None
    doctor_specialization: Optional[str] = None
    doctor_qualifications: Optional[list] = None
    doctor_years_of_experience: Optional[int] = None
    doctor_consultation_fee: Optional[float] = None
    doctor_languages_spoken: Optional[list] = None

    # Hospital info
    hospital_name: Optional[str] = None
    hospital_logo_url: Optional[str] = None
    hospital_city: Optional[str] = None
    hospital_country: Optional[str] = None

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
            # Extract from doctor relationship
            doctor = getattr(obj, "doctor", None)
            if doctor:
                data.setdefault("doctor_user_id", getattr(doctor, "user_id", None))
                user = getattr(doctor, "user", None)
                if user:
                    data.setdefault("doctor_name", getattr(user, "full_name", None))
                    data.setdefault("doctor_email", getattr(user, "email", None))
                    data.setdefault("doctor_phone", getattr(user, "phone", None))
                    data.setdefault("doctor_avatar_url", getattr(user, "avatar_url", None))
                data.setdefault("doctor_title", getattr(doctor, "title", None))
                data.setdefault("doctor_specialization", getattr(doctor, "primary_specialty", None))
                data.setdefault("doctor_qualifications", getattr(doctor, "qualifications", None))
                data.setdefault("doctor_years_of_experience", getattr(doctor, "years_of_experience", None))
                data.setdefault("doctor_consultation_fee", getattr(doctor, "consultation_fee", None))
                data.setdefault("doctor_languages_spoken", getattr(doctor, "languages_spoken", None))
                hospital = getattr(doctor, "hospital", None)
                if hospital:
                    data.setdefault("hospital_name", getattr(hospital, "name", None))
                    data.setdefault("hospital_logo_url", getattr(hospital, "logo_url", None))
                    data.setdefault("hospital_city", getattr(hospital, "city", None))
                    data.setdefault("hospital_country", getattr(hospital, "country", None))
            # Extract from patient relationship
            patient = getattr(obj, "patient", None)
            if patient:
                data.setdefault("patient_user_id", getattr(patient, "user_id", None))
                user = getattr(patient, "user", None)
                if user:
                    data.setdefault("patient_name", getattr(user, "full_name", None))
                    data.setdefault("patient_email", getattr(user, "email", None))
                    data.setdefault("patient_phone", getattr(user, "phone", None))
                    data.setdefault("patient_avatar_url", getattr(user, "avatar_url", None))
                data.setdefault("patient_gender", getattr(patient, "gender", None))
                data.setdefault("patient_blood_group", getattr(patient, "blood_group", None))
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
