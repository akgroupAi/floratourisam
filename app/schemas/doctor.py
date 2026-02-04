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
    break_start_time: Optional[time] = None
    break_end_time: Optional[time] = None


class DoctorAvailabilityResponse(BaseSchema):
    """Doctor availability response."""

    id: UUID
    day_of_week: int
    start_time: time
    end_time: time
    is_available: bool
    slot_duration_minutes: int
    max_appointments: Optional[int] = None
    break_start_time: Optional[time] = None
    break_end_time: Optional[time] = None


class DoctorBase(BaseModel):
    """Base doctor schema."""

    title: Optional[str] = Field(default=None, max_length=50)
    license_number: Optional[str] = Field(default=None, max_length=100)
    license_expiry: Optional[date] = None
    years_of_experience: Optional[int] = Field(default=None, ge=0, le=70)
    education: Optional[List[dict]] = None
    certifications: Optional[List[dict]] = None

    # Address
    address_line1: Optional[str] = Field(default=None, max_length=255)
    address_line2: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    country: Optional[str] = Field(default=None, max_length=100)
    postal_code: Optional[str] = Field(default=None, max_length=20)


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
    education: Optional[List[dict]] = None
    certifications: Optional[List[dict]] = None
    bio: Optional[str] = None
    languages_spoken: Optional[List[str]] = None
    consultation_fee: Optional[float] = Field(default=None, ge=0)
    consultation_duration_minutes: Optional[int] = Field(default=None, ge=15, le=120)
    video_consultation_enabled: Optional[bool] = None
    chat_consultation_enabled: Optional[bool] = None
    in_person_enabled: Optional[bool] = None

    # Address
    address_line1: Optional[str] = Field(default=None, max_length=255)
    address_line2: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    country: Optional[str] = Field(default=None, max_length=100)
    postal_code: Optional[str] = Field(default=None, max_length=20)


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
    education: Optional[List[dict]] = None
    certifications: Optional[List[dict]] = None
    bio: Optional[str] = None
    languages_spoken: Optional[List[str]] = None
    consultation_fee: Optional[float] = None
    consultation_duration_minutes: int = 30
    video_consultation_enabled: bool = True
    chat_consultation_enabled: bool = True
    in_person_enabled: bool = True

    # Address
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
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
                'address_line1': obj.address_line1,
                'address_line2': obj.address_line2,
                'city': obj.city,
                'state': obj.state,
                'country': obj.country,
                'postal_code': obj.postal_code,
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


# Hospital schemas for doctor hospital management
class DoctorHospitalCreate(BaseModel):
    """Schema for creating/adding hospital to doctor's profile."""

    doctor_id: UUID = Field(..., description="The doctor's ID")
    hospital_id: Optional[UUID] = Field(default=None, description="If provided, links to existing hospital instead of creating new one")
    
    name: Optional[str] = Field(default=None, max_length=255, description="Required if hospital_id is not provided")
    slug: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    short_description: Optional[str] = Field(default=None, max_length=500)
    
    # Contact information
    email: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=20)
    website: Optional[str] = Field(default=None, max_length=500)
    
    # Location
    address_line1: str = Field(..., max_length=255)
    address_line2: Optional[str] = Field(default=None, max_length=255)
    city: str = Field(..., max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    country: str = Field(..., max_length=100)
    postal_code: Optional[str] = Field(default=None, max_length=20)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    # Media
    logo_url: Optional[str] = Field(default=None, max_length=500)
    cover_image_url: Optional[str] = Field(default=None, max_length=500)
    gallery: Optional[List[str]] = None
    
    # Accreditation and facilities
    accreditations: Optional[List[str]] = None
    specialties: Optional[List[str]] = None
    languages_supported: Optional[List[str]] = None
    facilities: Optional[dict] = None
    
    # SEO
    meta_title: Optional[str] = Field(default=None, max_length=255)
    meta_description: Optional[str] = Field(default=None, max_length=500)


class DoctorHospitalUpdate(BaseModel):
    """Schema for updating doctor's hospital information."""

    doctor_id: UUID = Field(..., description="The doctor's ID")
    hospital_id: Optional[UUID] = Field(default=None, description="Hospital ID to link to (optional if already linked)")
    
    name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    short_description: Optional[str] = Field(default=None, max_length=500)
    
    # Contact information
    email: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=20)
    website: Optional[str] = Field(default=None, max_length=500)
    
    # Location
    address_line1: Optional[str] = Field(default=None, max_length=255)
    address_line2: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    country: Optional[str] = Field(default=None, max_length=100)
    postal_code: Optional[str] = Field(default=None, max_length=20)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    # Media
    logo_url: Optional[str] = Field(default=None, max_length=500)
    cover_image_url: Optional[str] = Field(default=None, max_length=500)
    gallery: Optional[List[str]] = None
    
    # Accreditation and facilities
    accreditations: Optional[List[str]] = None
    specialties: Optional[List[str]] = None
    languages_supported: Optional[List[str]] = None
    facilities: Optional[dict] = None
    
    # SEO
    meta_title: Optional[str] = Field(default=None, max_length=255)
    meta_description: Optional[str] = Field(default=None, max_length=500)


class DoctorHospitalResponse(BaseSchema):
    """Response schema for doctor's hospital information."""

    id: UUID
    name: str
    slug: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    
    # Contact information
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    
    # Location
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: Optional[str] = None
    country: str
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    # Media
    logo_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    gallery: Optional[List[str]] = None
    
    # Accreditation and ratings
    accreditations: Optional[List[str]] = None
    rating: Optional[float] = None
    total_reviews: int = 0
    
    # Facilities
    facilities: Optional[dict] = None
    specialties: Optional[List[str]] = None
    languages_supported: Optional[List[str]] = None
    
    # Status
    is_active: bool = True
    is_verified: bool = False
    is_featured: bool = False
    
    # Statistics
    total_doctors: int = 0
    total_patients_served: int = 0
    
    # SEO
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    
    created_at: datetime

