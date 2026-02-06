"""Site-specific schemas for Flora Medical platform."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import BaseSchema


# ============== Destination Schemas ==============

class DestinationCreate(BaseModel):
    name: str = Field(..., max_length=255)
    slug: str = Field(..., max_length=255, pattern="^[a-z0-9-]+$")
    country: str = Field(..., max_length=100)
    region: Optional[str] = None
    tagline: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    hero_image: Optional[str] = None
    highlights: List[str] = []
    is_featured: bool = False


class DestinationUpdate(BaseModel):
    name: Optional[str] = None
    tagline: Optional[str] = None
    description: Optional[str] = None
    hero_image: Optional[str] = None
    highlights: Optional[List[str]] = None
    is_featured: Optional[bool] = None
    is_active: Optional[bool] = None


class DestinationListResponse(BaseSchema):
    id: UUID
    name: str
    slug: str
    country: str
    hero_image: Optional[str] = None
    hospital_count: int = 0
    doctor_count: int = 0
    is_featured: bool = False


class DestinationResponse(BaseSchema):
    id: UUID
    name: str
    slug: str
    country: str
    region: Optional[str] = None
    tagline: Optional[str] = None
    description: Optional[str] = None
    hero_image: Optional[str] = None
    gallery: List[str] = []
    hospital_count: int = 0
    doctor_count: int = 0
    accommodation_count: int = 0
    highlights: List[str] = []
    why_choose: Optional[dict] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    is_active: bool = True
    is_featured: bool = False


# ============== Treatment Schemas ==============

class TreatmentCreate(BaseModel):
    name: str = Field(..., max_length=255)
    slug: str = Field(..., max_length=255, pattern="^[a-z0-9-]+$")
    category: str = Field(..., max_length=100)
    short_description: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    icon: Optional[str] = None
    image_url: Optional[str] = None
    success_rate: Optional[float] = Field(None, ge=0, le=100)
    price_from: Optional[float] = Field(None, ge=0)
    price_to: Optional[float] = Field(None, ge=0)
    procedures: List[str] = []
    is_featured: bool = False


class TreatmentUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    short_description: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    image_url: Optional[str] = None
    success_rate: Optional[float] = None
    price_from: Optional[float] = None
    price_to: Optional[float] = None
    procedures: Optional[List[str]] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None


class TreatmentListResponse(BaseSchema):
    id: UUID
    name: str
    slug: str
    category: str
    icon: Optional[str] = None
    image_url: Optional[str] = None
    success_rate: Optional[float] = None
    patient_count: int = 0
    settings_percent: Optional[int] = None
    price_from: Optional[float] = None
    price_to: Optional[float] = None
    average_rating: Optional[float] = None
    procedures: List[str] = []
    short_description: Optional[str] = None
    is_featured: bool = False


class TreatmentResponse(BaseSchema):
    id: UUID
    name: str
    slug: str
    category: str
    short_description: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    image_url: Optional[str] = None
    gallery: List[str] = []
    success_rate: Optional[float] = None
    patient_count: int = 0
    savings_percent: Optional[int] = None
    average_rating: Optional[float] = None
    price_from: Optional[float] = None
    price_to: Optional[float] = None
    currency: str = "USD"
    duration_days_min: Optional[int] = None
    duration_days_max: Optional[int] = None
    recovery_days: Optional[int] = None
    procedures: List[str] = []
    faqs: Optional[dict] = None
    is_active: bool = True
    is_featured: bool = False


# ============== Blog Schemas ==============

class BlogPostCreate(BaseModel):
    title: str = Field(..., max_length=255)
    slug: str = Field(..., max_length=255, pattern="^[a-z0-9-]+$")
    excerpt: Optional[str] = Field(None, max_length=500)
    content: str
    category: str = Field(..., max_length=100)
    tags: List[str] = []
    featured_image: Optional[str] = None
    status: str = Field(default="draft", pattern="^(draft|published|archived)$")


class BlogPostUpdate(BaseModel):
    title: Optional[str] = None
    excerpt: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    featured_image: Optional[str] = None
    status: Optional[str] = None


class BlogPostListResponse(BaseSchema):
    id: UUID
    title: str
    slug: str
    excerpt: Optional[str] = None
    featured_image: Optional[str] = None
    category: str
    author_name: Optional[str] = None
    published_at: Optional[datetime] = None
    read_time_minutes: int = 5
    view_count: int = 0


class BlogPostResponse(BaseSchema):
    id: UUID
    title: str
    slug: str
    excerpt: Optional[str] = None
    content: str
    category: str
    tags: List[str] = []
    featured_image: Optional[str] = None
    author_id: UUID
    author_name: Optional[str] = None
    author_avatar: Optional[str] = None
    status: str
    published_at: Optional[datetime] = None
    read_time_minutes: int = 5
    view_count: int = 0
    like_count: int = 0
    related_posts: List[str] = []
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    created_at: datetime


# ============== Testimonial Schemas ==============

class TestimonialCreate(BaseModel):
    patient_name: str = Field(..., max_length=255)
    patient_country: Optional[str] = None
    patient_avatar: Optional[str] = None
    treatment_name: Optional[str] = None
    hospital_name: Optional[str] = None
    rating: int = Field(default=5, ge=1, le=5)
    title: Optional[str] = None
    content: str
    video_url: Optional[str] = None
    is_featured: bool = False


class TestimonialListResponse(BaseSchema):
    id: UUID
    patient_name: str
    patient_country: Optional[str] = None
    patient_avatar: Optional[str] = None
    treatment_name: Optional[str] = None
    rating: int
    content: str
    is_featured: bool = False


class TestimonialResponse(TestimonialListResponse):
    hospital_name: Optional[str] = None
    title: Optional[str] = None
    video_url: Optional[str] = None
    is_approved: bool = False
    created_at: datetime


# ============== FAQ Schemas ==============

class FAQCreate(BaseModel):
    question: str = Field(..., max_length=500)
    answer: str
    category: str = Field(..., max_length=100)
    is_featured: bool = False
    display_order: int = 0


class FAQUpdate(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None
    display_order: Optional[int] = None


class FAQResponse(BaseSchema):
    id: UUID
    question: str
    answer: str
    category: str
    is_active: bool = True
    is_featured: bool = False
    display_order: int = 0


# ============== Team Schemas ==============

class TeamMemberCreate(BaseModel):
    name: str = Field(..., max_length=255)
    role: str = Field(..., max_length=255)
    department: Optional[str] = None
    image_url: Optional[str] = None
    bio: Optional[str] = None
    linkedin_url: Optional[str] = None
    twitter_url: Optional[str] = None
    is_leadership: bool = False


class TeamMemberUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    image_url: Optional[str] = None
    bio: Optional[str] = None
    linkedin_url: Optional[str] = None
    twitter_url: Optional[str] = None
    is_leadership: Optional[bool] = None
    is_active: Optional[bool] = None
    display_order: Optional[int] = None


class TeamMemberResponse(BaseSchema):
    id: UUID
    name: str
    role: str
    department: Optional[str] = None
    image_url: Optional[str] = None
    bio: Optional[str] = None
    linkedin_url: Optional[str] = None
    twitter_url: Optional[str] = None
    is_active: bool = True
    is_leadership: bool = False
    display_order: int = 0


# ============== Doctor Public Schemas ==============

class DoctorPublicListResponse(BaseSchema):
    """Public-facing doctor list response for /doctors page."""
    id: UUID
    name: str
    title: Optional[str] = None  # e.g., "Chief Surgeon"
    specializations: List[str] = []
    rating: Optional[float] = None
    years_of_experience: Optional[int] = None
    hospital_name: Optional[str] = None
    location: Optional[str] = None  # City
    image_url: Optional[str] = None
    consultation_fee: Optional[float] = None


class DoctorPublicDetailResponse(BaseSchema):
    """Public-facing doctor detail response for /doctors/{id} page."""
    id: UUID
    name: str
    title: Optional[str] = None
    specializations: List[str] = []
    rating: Optional[float] = None
    years_of_experience: Optional[int] = None
    hospital_name: Optional[str] = None
    location: Optional[str] = None
    image_url: Optional[str] = None
    bio: Optional[str] = None
    consultation_fee: Optional[float] = None
    languages_spoken: List[str] = []
    qualifications: List[str] = []


# ============== Lead Schemas ==============

class LeadSubmissionCreate(BaseModel):
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=20)
    name: Optional[str] = Field(None, max_length=255)
    country: Optional[str] = Field(None, max_length=100)
    medical_condition: Optional[str] = None
    treatment_interest: Optional[str] = None
    preferred_destination: Optional[str] = None
    message: Optional[str] = None
    form_source: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None


class LeadSubmissionResponse(BaseSchema):
    id: UUID
    email: str
    phone: Optional[str] = None
    name: Optional[str] = None
    country: Optional[str] = None
    medical_condition: Optional[str] = None
    treatment_interest: Optional[str] = None
    status: str
    form_source: Optional[str] = None
    created_at: datetime


# ============== Settings Schemas ==============

class SiteSettingUpdate(BaseModel):
    value: dict


class SiteSettingResponse(BaseSchema):
    key: str
    value: dict
    category: str


class ContactSubmission(BaseModel):
    name: str = Field(..., max_length=255)
    email: EmailStr
    phone: Optional[str] = None
    subject: str = Field(..., max_length=255)
    message: str
