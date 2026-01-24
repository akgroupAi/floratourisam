"""Doctor schemas."""

from datetime import date, datetime, time
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import BaseSchema


class DoctorSpecializationCreate(BaseModel):
    """Doctor specialization creation."""

    specialization: str = Field(..., max_length=100)
    is_primary: bool = False
    certification: Optional[str] = Field(default=None, max_length=255)


class DoctorSpecializationResponse(BaseSchema):
    """Doctor specialization response."""

    id: UUID
    specialization: str
    is_primary: bool
    certification: Optional[str] = None


class DoctorAvailabilityCreate(BaseModel):
    """Doctor availability creation."""

    day_of_week: int = Field(..., ge=0, le=6)  # 0=Monday, 6=Sunday
    start_time: time
    end_time: time
    is_available: bool = True
    slot_duration_minutes: int = Field(default=30, ge=15, le=120)
    max_appointments: Optional[int] = Field(default=None, ge=1)


class DoctorAvailabilityResponse(BaseSchema):
    """Doctor availability response."""

    id: UUID
    day_of_week: int
    start_time: time
    end_time: time
    is_available: bool
    slot_duration_minutes: int
    max_appointments: Optional[int] = None


class DoctorBase(BaseModel):
    """Base doctor schema."""

    title: Optional[str] = Field(default=None, max_length=50)
    license_number: str = Field(..., max_length=100)
    license_expiry: Optional[date] = None
    years_of_experience: Optional[int] = Field(default=None, ge=0, le=70)


class DoctorCreate(DoctorBase):
    """Doctor creation schema."""

    user_id: Optional[UUID] = None  # If not provided, uses current user
    hospital_id: Optional[UUID] = None
    qualifications: Optional[List[str]] = None
    bio: Optional[str] = None
    languages_spoken: Optional[List[str]] = None
    consultation_fee: Optional[float] = Field(default=None, ge=0)
    consultation_duration_minutes: int = Field(default=30, ge=15, le=120)
    video_consultation_enabled: bool = True
    chat_consultation_enabled: bool = True
    in_person_enabled: bool = True
    specializations: Optional[List[DoctorSpecializationCreate]] = None


class DoctorUpdate(BaseModel):
    """Doctor update schema."""

    title: Optional[str] = Field(default=None, max_length=50)
    hospital_id: Optional[UUID] = None
    license_expiry: Optional[date] = None
    years_of_experience: Optional[int] = Field(default=None, ge=0)
    qualifications: Optional[List[str]] = None
    education: Optional[dict] = None
    certifications: Optional[dict] = None
    bio: Optional[str] = None
    languages_spoken: Optional[List[str]] = None
    consultation_fee: Optional[float] = Field(default=None, ge=0)
    consultation_duration_minutes: Optional[int] = Field(default=None, ge=15, le=120)
    video_consultation_enabled: Optional[bool] = None
    chat_consultation_enabled: Optional[bool] = None
    in_person_enabled: Optional[bool] = None


class DoctorListResponse(BaseSchema):
    """Doctor list response schema."""

    id: UUID
    user_id: UUID
    full_name: str
    title: Optional[str] = None
    hospital_name: Optional[str] = None
    primary_specialization: Optional[str] = None
    years_of_experience: Optional[int] = None
    consultation_fee: Optional[float] = None
    rating: Optional[float] = None
    total_reviews: int = 0
    is_verified: bool = False
    avatar_url: Optional[str] = None
    video_consultation_enabled: bool = True
    chat_consultation_enabled: bool = True


class DoctorResponse(BaseSchema):
    """Doctor detail response schema."""

    id: UUID
    user_id: UUID
    hospital_id: Optional[UUID] = None
    title: Optional[str] = None
    license_number: str
    license_expiry: Optional[date] = None
    years_of_experience: Optional[int] = None
    qualifications: Optional[List[str]] = None
    education: Optional[dict] = None
    certifications: Optional[dict] = None
    bio: Optional[str] = None
    languages_spoken: Optional[List[str]] = None
    consultation_fee: Optional[float] = None
    consultation_duration_minutes: int = 30
    video_consultation_enabled: bool = True
    chat_consultation_enabled: bool = True
    in_person_enabled: bool = True
    rating: Optional[float] = None
    total_reviews: int = 0
    total_consultations: int = 0
    is_verified: bool = False
    verification_date: Optional[datetime] = None
    created_at: datetime

    # Related data
    specializations: List[DoctorSpecializationResponse] = []
    availability: List[DoctorAvailabilityResponse] = []

    # User info
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None

    # Hospital info
    hospital_name: Optional[str] = None


class DoctorSlotResponse(BaseModel):
    """Available appointment slot response."""

    date: date
    time: time
    is_available: bool
    doctor_id: UUID


class DoctorSearchParams(BaseModel):
    """Doctor search parameters."""

    specialization: Optional[str] = None
    hospital_id: Optional[UUID] = None
    city: Optional[str] = None
    min_rating: Optional[float] = Field(default=None, ge=0, le=5)
    max_fee: Optional[float] = Field(default=None, ge=0)
    video_enabled: Optional[bool] = None
    available_on: Optional[date] = None
    language: Optional[str] = None
