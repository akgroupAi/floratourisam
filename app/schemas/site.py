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
    gallery: List[str] = []
    success_rate: Optional[float] = Field(None, ge=0, le=100)
    patient_count: int = 0
    savings_percent: Optional[int] = Field(None, ge=0, le=100)
    average_rating: Optional[float] = Field(None, ge=0, le=5)
    badge_text: Optional[str] = Field(None, max_length=100)
    price_from: Optional[float] = Field(None, ge=0)
    price_to: Optional[float] = Field(None, ge=0)
    currency: str = "USD"
    duration_days_min: Optional[int] = Field(None, ge=0)
    duration_days_max: Optional[int] = Field(None, ge=0)
    recovery_days: Optional[int] = Field(None, ge=0)
    recovery_text: Optional[str] = Field(None, max_length=100)
    procedures: List[str] = []
    related_treatments: List[str] = []
    why_choose: Optional[list] = None
    available_treatments: Optional[list] = None
    faqs: Optional[dict] = None
    meta_title: Optional[str] = Field(None, max_length=255)
    meta_description: Optional[str] = Field(None, max_length=500)
    is_featured: bool = False
    display_order: int = 0


class TreatmentUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    category: Optional[str] = None
    short_description: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    image_url: Optional[str] = None
    gallery: Optional[List[str]] = None
    success_rate: Optional[float] = None
    patient_count: Optional[int] = None
    savings_percent: Optional[int] = None
    average_rating: Optional[float] = None
    badge_text: Optional[str] = None
    price_from: Optional[float] = None
    price_to: Optional[float] = None
    currency: Optional[str] = None
    duration_days_min: Optional[int] = None
    duration_days_max: Optional[int] = None
    recovery_days: Optional[int] = None
    recovery_text: Optional[str] = None
    procedures: Optional[List[str]] = None
    related_treatments: Optional[List[str]] = None
    why_choose: Optional[list] = None
    available_treatments: Optional[list] = None
    faqs: Optional[dict] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None
    display_order: Optional[int] = None


class TreatmentListResponse(BaseSchema):
    id: UUID
    name: str
    slug: str
    category: str
    icon: Optional[str] = None
    image_url: Optional[str] = None
    success_rate: Optional[float] = None
    patient_count: int = 0
    savings_percent: Optional[int] = None
    average_rating: Optional[float] = None
    badge_text: Optional[str] = None
    price_from: Optional[float] = None
    price_to: Optional[float] = None
    duration_days_min: Optional[int] = None
    duration_days_max: Optional[int] = None
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
    badge_text: Optional[str] = None
    price_from: Optional[float] = None
    price_to: Optional[float] = None
    currency: str = "USD"
    duration_days_min: Optional[int] = None
    duration_days_max: Optional[int] = None
    recovery_days: Optional[int] = None
    recovery_text: Optional[str] = None
    procedures: List[str] = []
    related_treatments: List[str] = []
    why_choose: Optional[list] = None
    available_treatments: Optional[list] = None
    faqs: Optional[dict] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
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
    comment_count: int = 0
    related_posts: Optional[List[str]] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    created_at: datetime


# ============== Blog Comment Schemas ==============

class BlogCommentCreate(BaseModel):
    """Submit a new comment on a blog post."""

    content: str = Field(..., min_length=2, max_length=2000)
    parent_id: Optional[UUID] = None  # Set to reply to an existing comment
    # Required only for guest (unauthenticated) submissions
    guest_name: Optional[str] = Field(default=None, max_length=255)
    guest_email: Optional[str] = Field(default=None, max_length=255)


class BlogCommentUpdate(BaseModel):
    """Edit the content of an existing comment (author or admin only)."""

    content: str = Field(..., min_length=2, max_length=2000)


class BlogCommentResponse(BaseSchema):
    """A single comment, optionally nested with replies."""

    id: UUID
    post_id: UUID
    parent_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    author_name: Optional[str] = None
    author_avatar: Optional[str] = None
    content: str
    is_approved: bool
    replies: List["BlogCommentResponse"] = []
    created_at: datetime
    updated_at: datetime


# Allow self-referential schema
BlogCommentResponse.model_rebuild()




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
    video_thumbnail: Optional[str] = None
    video_duration: Optional[str] = Field(None, max_length=20)
    is_verified: bool = False
    is_featured: bool = False


class TestimonialListResponse(BaseSchema):
    id: UUID
    patient_name: str
    patient_country: Optional[str] = None
    patient_avatar: Optional[str] = None
    treatment_name: Optional[str] = None
    hospital_name: Optional[str] = None
    title: Optional[str] = None
    video_url: Optional[str] = None
    video_thumbnail: Optional[str] = None
    video_duration: Optional[str] = None
    is_verified: bool = False
    rating: int
    content: str
    is_featured: bool = False
    is_approved: bool = False
    created_at: Optional[datetime] = None


class TestimonialResponse(TestimonialListResponse):
    pass


class TestimonialUpdate(BaseModel):
    patient_name: Optional[str] = None
    patient_country: Optional[str] = None
    treatment_name: Optional[str] = None
    hospital_name: Optional[str] = None
    rating: Optional[int] = Field(None, ge=1, le=5)
    title: Optional[str] = None
    content: Optional[str] = None
    video_url: Optional[str] = None
    video_thumbnail: Optional[str] = None
    video_duration: Optional[str] = None
    is_verified: Optional[bool] = None
    is_featured: Optional[bool] = None
    is_approved: Optional[bool] = None


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
    email: Optional[EmailStr] = None
    role: str = Field(..., max_length=255)
    department: Optional[str] = None
    image_url: Optional[str] = None
    bio: Optional[str] = None
    linkedin_url: Optional[str] = None
    twitter_url: Optional[str] = None
    is_leadership: bool = False


class TeamMemberUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
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
    email: Optional[str] = None
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


# ============== Hero Slider Schemas ==============

class HeroSliderCreate(BaseModel):
    title: str = Field(..., max_length=255)
    subtitle: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    highlight_text: Optional[str] = Field(None, max_length=255)
    features: Optional[list] = None
    background_image: Optional[str] = Field(None, max_length=500)
    badge_text: Optional[str] = Field(None, max_length=100)
    primary_cta_text: Optional[str] = Field(None, max_length=100)
    primary_cta_url: Optional[str] = Field(None, max_length=500)
    secondary_cta_text: Optional[str] = Field(None, max_length=100)
    secondary_cta_url: Optional[str] = Field(None, max_length=500)
    link_url: Optional[str] = Field(None, max_length=500)
    featured_service_title: Optional[str] = Field(None, max_length=255)
    featured_service_description: Optional[str] = Field(None, max_length=500)
    featured_service_image: Optional[str] = Field(None, max_length=500)
    featured_service_url: Optional[str] = Field(None, max_length=500)
    display_order: int = 0
    is_active: bool = True


class HeroSliderUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    subtitle: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    highlight_text: Optional[str] = Field(None, max_length=255)
    features: Optional[list] = None
    background_image: Optional[str] = Field(None, max_length=500)
    badge_text: Optional[str] = Field(None, max_length=100)
    primary_cta_text: Optional[str] = Field(None, max_length=100)
    primary_cta_url: Optional[str] = Field(None, max_length=500)
    secondary_cta_text: Optional[str] = Field(None, max_length=100)
    secondary_cta_url: Optional[str] = Field(None, max_length=500)
    link_url: Optional[str] = Field(None, max_length=500)
    featured_service_title: Optional[str] = Field(None, max_length=255)
    featured_service_description: Optional[str] = Field(None, max_length=500)
    featured_service_image: Optional[str] = Field(None, max_length=500)
    featured_service_url: Optional[str] = Field(None, max_length=500)
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


class HeroSliderResponse(BaseSchema):
    id: UUID
    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    highlight_text: Optional[str] = None
    features: Optional[list] = None
    background_image: Optional[str] = None
    badge_text: Optional[str] = None
    primary_cta_text: Optional[str] = None
    primary_cta_url: Optional[str] = None
    secondary_cta_text: Optional[str] = None
    secondary_cta_url: Optional[str] = None
    link_url: Optional[str] = None
    featured_service_title: Optional[str] = None
    featured_service_description: Optional[str] = None
    featured_service_image: Optional[str] = None
    featured_service_url: Optional[str] = None
    display_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class HeroSliderReorder(BaseModel):
    id: UUID
    display_order: int

