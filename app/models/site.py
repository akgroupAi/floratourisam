"""Site-specific models for Flora Medical platform."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from app.models.user import User

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Destination(BaseModel):
    """Medical tourism destination (city/region)."""

    __tablename__ = "destinations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Content
    tagline: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Media
    hero_image: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    gallery: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    
    # Stats
    hospital_count: Mapped[int] = mapped_column(Integer, default=0)
    doctor_count: Mapped[int] = mapped_column(Integer, default=0)
    accommodation_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Features
    highlights: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    why_choose: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # Location
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    timezone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # SEO
    meta_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    meta_description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0)


class Treatment(BaseModel):
    """Medical treatment/service."""

    __tablename__ = "treatments"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)  # Surgery, Dental, etc.
    
    # Content
    short_description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Media
    icon: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    gallery: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    
    # Stats
    success_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    patient_count: Mapped[int] = mapped_column(Integer, default=0)
    savings_percent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    average_rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    badge_text: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g. "Most Popular"
    
    # Pricing
    price_from: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_to: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    
    # Duration
    duration_days_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration_days_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    recovery_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    recovery_text: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g. "30% Faster"
    
    # Related
    procedures: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    related_treatments: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    
    # Detail page content
    why_choose: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)  # ["Internationally trained surgeons", ...]
    available_treatments: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)  # [{name, description, duration_text, price_min, price_max}, ...]
    
    # FAQ
    faqs: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # SEO
    meta_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    meta_description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    @property
    def ratings(self) -> Optional[float]:
        return self.average_rating

    @property
    def stay_days(self) -> Optional[int]:
        return self.duration_days_max or self.duration_days_min

    @property
    def total_patient(self) -> int:
        return self.patient_count


class BlogPost(BaseModel):
    """Blog article."""

    __tablename__ = "blog_posts"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    
    # Author
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    author: Mapped[Optional["User"]] = relationship("User", foreign_keys=[author_id])

    author_title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g. "Medical Director"

    @property
    def author_name(self) -> Optional[str]:
        return self.author.full_name if self.author else None

    @property
    def author_avatar(self) -> Optional[str]:
        return self.author.avatar_url if self.author else None
    
    # Content
    excerpt: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Categorization
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    tags: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    
    # Media
    featured_image: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Reading
    read_time_minutes: Mapped[int] = mapped_column(Integer, default=5)
    
    # Status
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft, published, archived
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Engagement
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # SEO
    meta_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    meta_description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Related
    related_posts: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)

    # Comments relationship (top-level only; replies loaded per comment)
    comments: Mapped[List["BlogComment"]] = relationship(
        "BlogComment",
        primaryjoin="and_(BlogComment.post_id == BlogPost.id, BlogComment.parent_id == None, BlogComment.is_deleted == False)",
        order_by="BlogComment.created_at.asc()",
        lazy="selectin",
        viewonly=True,
    )

    @property
    def comment_count(self) -> int:
        """Total approved top-level comments loaded via relationship."""
        return len([c for c in self.comments if c.is_approved])


class BlogComment(BaseModel):
    """Comment on a blog post, with optional threading (one level of replies)."""

    __tablename__ = "blog_comments"

    # Post link
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("blog_posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Author — authenticated user (nullable to support guest comments)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Guest commenter info (used when user_id is None)
    guest_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    guest_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Threading — parent_id is None for top-level comments
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("blog_comments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Moderation
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id], lazy="select")
    replies: Mapped[List["BlogComment"]] = relationship(
        "BlogComment",
        primaryjoin="and_(remote(BlogComment.parent_id) == BlogComment.id, BlogComment.is_deleted == False)",
        foreign_keys="BlogComment.parent_id",
        order_by="BlogComment.created_at.asc()",
        lazy="selectin",
        viewonly=True,
    )

    def __repr__(self) -> str:
        return f"BlogComment(id={self.id}, post={self.post_id}, approved={self.is_approved})"

    @property
    def author_name(self) -> Optional[str]:
        if self.user:
            return self.user.full_name
        return self.guest_name

    @property
    def author_avatar(self) -> Optional[str]:
        if self.user:
            return getattr(self.user, "avatar_url", None)
        return None


class Testimonial(BaseModel):
    """Patient testimonial."""

    __tablename__ = "testimonials"

    # Patient info
    patient_name: Mapped[str] = mapped_column(String(255), nullable=False)
    patient_country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    patient_avatar: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Treatment info
    treatment_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("treatments.id"), nullable=True)
    hospital_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=True)
    treatment_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    hospital_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Content
    rating: Mapped[int] = mapped_column(Integer, default=5)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Media
    video_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    video_thumbnail: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    video_duration: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # e.g. "2:45"
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)  # "VERIFIED PATIENT" badge
    
    # Status
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0)


class FAQ(BaseModel):
    """Frequently asked question."""

    __tablename__ = "faqs"

    question: Mapped[str] = mapped_column(String(500), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)  # General, Medical, Travel, Payment
    
    # Related entity (optional)
    treatment_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    destination_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0)


class TeamMember(BaseModel):
    """Team member profile."""

    __tablename__ = "team_members"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)
    role: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Media
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Content
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Social
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    twitter_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_leadership: Mapped[bool] = mapped_column(Boolean, default=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0)


class LeadSubmission(BaseModel):
    """Lead form submission for quote requests."""

    __tablename__ = "lead_submissions"

    # Contact
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Medical
    medical_condition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    treatment_interest: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    preferred_destination: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Documents
    documents: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    
    # Additional
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    form_source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # homepage, service page, etc.
    
    # Status
    status: Mapped[str] = mapped_column(String(20), default="new")  # new, contacted, qualified, converted
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Tracking
    utm_source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    utm_medium: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    utm_campaign: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)


class SiteSettings(BaseModel):
    """Global site settings."""

    __tablename__ = "site_settings"

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # general, contact, social, seo
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class Navigation(BaseModel):
    """Navigation menu structure."""

    __tablename__ = "navigation"

    name: Mapped[str] = mapped_column(String(100), nullable=False)  # main, footer, mobile
    structure: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class HeroSlider(BaseModel):
    """Hero section slider slide — managed by admin, rendered on homepage."""

    __tablename__ = "hero_sliders"

    # Slide content
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    subtitle: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    highlight_text: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # e.g. "AI-Powered Healthcare Journey"
    features: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)  # e.g. ["AI-Matched Specialists", "Transparent Pricing"]

    # Media
    background_image: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    badge_text: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g. "Featured Service"
    icon: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # icon name or URL, e.g. "stethoscope"

    # Primary CTA button
    primary_cta_text: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    primary_cta_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Secondary CTA button
    secondary_cta_text: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    secondary_cta_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Optional whole-slide link
    link_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Featured service card (right-side overlay)
    featured_service_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    featured_service_description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    featured_service_image: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    featured_service_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Display control
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"HeroSlider(id={self.id}, title={self.title!r}, order={self.display_order})"
