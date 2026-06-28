"""Patient schemas."""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import BaseSchema
from app.utils.enums import BloodGroup, Gender


def _empty_date_to_none(value: object) -> Optional[date]:
    """Convert empty strings to None for optional date fields."""
    if value == "" or value is None:
        return None
    return value  # type: ignore[return-value]


class PatientBase(BaseModel):
    """Base patient schema."""

    date_of_birth: Optional[date] = None

    @field_validator("date_of_birth", "passport_expiry", mode="before")
    @classmethod
    def normalize_optional_dates(cls, value: object) -> Optional[date]:
        return _empty_date_to_none(value)
    gender: Optional[Gender] = None
    nationality: Optional[str] = Field(default=None, max_length=100)
    passport_number: Optional[str] = Field(default=None, max_length=50)
    passport_expiry: Optional[date] = None


class PatientCreate(PatientBase):
    """Patient creation schema."""

    user_id: Optional[UUID] = None  # If not provided, uses current user


class PatientUpdate(PatientBase):
    """Patient update schema."""

    # Address
    address_line1: Optional[str] = Field(default=None, max_length=255)
    address_line2: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    country: Optional[str] = Field(default=None, max_length=100)
    postal_code: Optional[str] = Field(default=None, max_length=20)

    # Medical information
    blood_group: Optional[BloodGroup] = None
    height_cm: Optional[float] = Field(default=None, gt=0, le=300)
    weight_kg: Optional[float] = Field(default=None, gt=0, le=500)
    allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None
    current_medications: Optional[str] = None
    medical_history: Optional[dict] = None

    # Emergency contact
    emergency_contact_name: Optional[str] = Field(default=None, max_length=255)
    emergency_contact_phone: Optional[str] = Field(default=None, max_length=20)
    emergency_contact_relation: Optional[str] = Field(default=None, max_length=100)

    # Insurance
    insurance_provider: Optional[str] = Field(default=None, max_length=255)
    insurance_policy_number: Optional[str] = Field(default=None, max_length=100)
    insurance_details: Optional[dict] = None

    # Preferences
    preferred_language: Optional[str] = Field(default="en", max_length=10)
    preferences: Optional[dict] = None


class PatientResponse(BaseSchema):
    """Patient response schema."""

    id: UUID
    user_id: UUID
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    nationality: Optional[str] = None
    blood_group: Optional[str] = None
    age: Optional[int] = None
    bmi: Optional[float] = None

    # Address
    city: Optional[str] = None
    country: Optional[str] = None

    # Emergency contact
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

    # Insurance
    insurance_provider: Optional[str] = None

    created_at: datetime


class PatientDetailResponse(PatientResponse):
    """Detailed patient response schema."""

    passport_number: Optional[str] = None
    passport_expiry: Optional[date] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None
    current_medications: Optional[str] = None
    medical_history: Optional[dict] = None
    emergency_contact_relation: Optional[str] = None
    insurance_policy_number: Optional[str] = None
    insurance_details: Optional[dict] = None
    preferred_language: Optional[str] = None
    preferences: Optional[dict] = None

    # User info
    user_email: Optional[str] = None
    user_full_name: Optional[str] = None
    user_phone: Optional[str] = None


class PatientMedicalSummary(BaseModel):
    """Patient medical summary for doctors."""

    patient_id: UUID
    age: Optional[int] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    bmi: Optional[float] = None
    allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None
    current_medications: Optional[str] = None
    total_consultations: int = 0
    last_consultation_date: Optional[datetime] = None
