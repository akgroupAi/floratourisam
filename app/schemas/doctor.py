"""Doctor schemas."""

from datetime import date, datetime, time
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

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
    license_number: Optional[str] = Field(default=None, max_length=100)
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

    @model_validator(mode='before')
    @classmethod
    def flatten_doctor_data(cls, obj: Any) -> Any:
        """Flatten doctor data from relationships."""
        if hasattr(obj, 'user') and obj.user:
            # We need to return an object that has attributes matching the schema
            # Or a dict. Since obj is likely an ORM object, let's create a proxy or modify it
            # But simpler is to return a dict if possible, but BaseSchema handles attributes.
            # Let's attach the missing attributes to the object or return a dict.
            
            # Since pydantic v2 from_attributes=True supports dicts too, let's try returning a dict
            return {
                'id': obj.id,
                'user_id': obj.user_id,
                'full_name': obj.user.full_name,
                'title': obj.title,
                'hospital_name': obj.hospital.name if obj.hospital else None,
                'primary_specialization': obj.specializations[0].specialization if obj.specializations else None,
                'years_of_experience': obj.years_of_experience,
                'consultation_fee': obj.consultation_fee,
                'rating': obj.rating,
                'total_reviews': obj.total_reviews,
                'is_verified': obj.is_verified,
                'avatar_url': obj.user.avatar_url,
                'video_consultation_enabled': obj.video_consultation_enabled,
                'chat_consultation_enabled': obj.chat_consultation_enabled,
            }
        return obj


class DoctorResponse(BaseSchema):
    """Doctor detail response schema."""

    id: UUID
    user_id: UUID
    hospital_id: Optional[UUID] = None
    title: Optional[str] = None
    license_number: Optional[str] = None
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

    @model_validator(mode='before')
    @classmethod
    def flatten_doctor_detail(cls, obj: Any) -> Any:
        """Flatten doctor detail data."""
        if hasattr(obj, 'user') and obj.user:
            return {
                'id': obj.id,
                'user_id': obj.user_id,
                'hospital_id': obj.hospital_id,
                'title': obj.title,
                'license_number': obj.license_number,
                'license_expiry': obj.license_expiry,
                'years_of_experience': obj.years_of_experience,
                'qualifications': obj.qualifications,
                'education': obj.education,
                'certifications': obj.certifications,
                'bio': obj.bio,
                'languages_spoken': obj.languages_spoken,
                'consultation_fee': obj.consultation_fee,
                'consultation_duration_minutes': obj.consultation_duration_minutes,
                'video_consultation_enabled': obj.video_consultation_enabled,
                'chat_consultation_enabled': obj.chat_consultation_enabled,
                'in_person_enabled': obj.in_person_enabled,
                'rating': obj.rating,
                'total_reviews': obj.total_reviews,
                'total_consultations': obj.total_consultations,
                'is_verified': obj.is_verified,
                'verification_date': obj.verification_date,
                'created_at': obj.created_at,
                'specializations': obj.specializations,
                'availability': obj.availability,
                'full_name': obj.user.full_name,
                'email': obj.user.email,
                'phone': obj.user.phone,
                'avatar_url': obj.user.avatar_url,
                'hospital_name': obj.hospital.name if obj.hospital else None,
            }
        return obj




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
