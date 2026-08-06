"""Hospital schemas."""

from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.common import BaseSchema


def _none_to_list(value: Any) -> list:
    """Coerce NULL DB array columns to empty lists for response schemas."""
    return [] if value is None else value


class HospitalCreate(BaseModel):
    """Hospital creation schema."""

    # Basic information
    name: str = Field(..., max_length=255, example="Apollo Hospital")
    slug: str = Field(..., max_length=255, pattern="^[a-z0-9-]+$", example="apollo-hospital-delhi")
    description: Optional[str] = None
    short_description: Optional[str] = Field(None, max_length=500)

    # Contact information
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    website: Optional[str] = Field(None, max_length=500)

    # Location
    address_line1: str = Field(..., max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: str = Field(..., max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: str = Field(..., max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Media
    logo_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    gallery: List[str] = []

    # Features
    facilities: Optional[dict] = None
    specialties: List[str] = []
    languages_supported: List[str] = []
    accreditations: List[str] = []


class HospitalUpdate(BaseModel):
    """Hospital update schema."""

    name: Optional[str] = None
    description: Optional[str] = None
    short_description: Optional[str] = None
    
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    logo_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    gallery: Optional[List[str]] = None
    
    facilities: Optional[dict] = None
    specialties: Optional[List[str]] = None
    languages_supported: Optional[List[str]] = None
    accreditations: Optional[List[str]] = None
    
    is_active: Optional[bool] = None


class HospitalListResponse(BaseSchema):
    """Hospital list response schema."""

    id: UUID
    name: str
    slug: str
    city: str
    country: str
    logo_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    gallery: List[str] = []
    phone: Optional[str] = None
    rating: Optional[float] = None
    total_reviews: int = 0
    is_verified: bool = False

    @field_validator("gallery", mode="before")
    @classmethod
    def coerce_gallery(cls, value: Any) -> list:
        return _none_to_list(value)


class HospitalResponse(BaseSchema):
    """Hospital detail response schema."""

    id: UUID
    name: str
    slug: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: Optional[str] = None
    country: str
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    logo_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    gallery: List[str] = []
    
    facilities: Optional[dict] = None
    specialties: List[str] = []
    languages_supported: List[str] = []
    accreditations: List[str] = []
    
    rating: Optional[float] = None
    total_reviews: int = 0
    is_active: bool = True
    is_verified: bool = False
    is_featured: bool = False
    
    total_doctors: int = 0
    total_patients_served: int = 0

    meta_title: Optional[str] = None
    meta_description: Optional[str] = None

    @field_validator(
        "gallery",
        "specialties",
        "languages_supported",
        "accreditations",
        mode="before",
    )
    @classmethod
    def coerce_null_lists(cls, value: Any) -> list:
        return _none_to_list(value)
