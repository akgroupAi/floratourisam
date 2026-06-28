"""Pydantic schemas for Reviews & Ratings."""

from datetime import datetime
from typing import Literal, Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import BaseSchema

# Supported entity types
EntityType = Literal["doctor", "hospital", "hotel", "apartment", "restaurant"]


# ---------------------------------------------------------------------------
# Input schemas
# ---------------------------------------------------------------------------

class ReviewCreate(BaseModel):
    """Submit a new review. Patient can only review entities they have used."""

    entity_type: EntityType = Field(..., description="Type of entity being reviewed")
    entity_id: UUID = Field(..., description="ID of the entity being reviewed")
    rating: int = Field(..., ge=1, le=5, description="Star rating from 1 (poor) to 5 (excellent)")
    title: Optional[str] = Field(None, max_length=255, description="Short headline")
    body: Optional[str] = Field(None, min_length=10, max_length=5000, description="Full review text (min 10 chars if provided)")

    # Optional proof of visit — service will also auto-detect these
    booking_id: Optional[UUID] = Field(None, description="Booking ID to verify hotel/apartment/restaurant visit")
    consultation_id: Optional[UUID] = Field(None, description="Consultation ID to verify doctor visit")

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError("Rating must be between 1 and 5")
        return v

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v

    @field_validator("body")
    @classmethod
    def strip_body(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v


class SimpleReviewCreate(BaseModel):
    """Simplified review input — entity info comes from the URL."""

    rating: int = Field(..., ge=1, le=5, description="Star rating from 1 (poor) to 5 (excellent)")
    title: Optional[str] = Field(None, max_length=255, description="Short headline")
    body: Optional[str] = Field(None, min_length=10, max_length=5000, description="Full review text")

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v

    @field_validator("body")
    @classmethod
    def strip_body(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v


class ReviewUpdate(BaseModel):
    """Update own review. Only allowed while review is pending approval."""

    rating: Optional[int] = Field(None, ge=1, le=5)
    title: Optional[str] = Field(None, max_length=255)
    body: Optional[str] = Field(None, min_length=10, max_length=5000)

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not 1 <= v <= 5:
            raise ValueError("Rating must be between 1 and 5")
        return v


class ReviewHelpfulRequest(BaseModel):
    """Mark a review as helpful."""
    helpful: bool = Field(True, description="True to mark helpful, False to unmark")


class AdminReviewResponse(BaseModel):
    """Admin response to a review (official reply from the entity)."""
    response_text: str = Field(..., min_length=10, max_length=3000)


class AdminReviewApprove(BaseModel):
    """Admin approval / rejection action."""
    approve: bool = Field(..., description="True to approve, False to reject")
    rejection_reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Required when approve=False",
    )

    @model_validator(mode="after")
    def reason_required_on_reject(self) -> "AdminReviewApprove":
        if not self.approve and not self.rejection_reason:
            self.rejection_reason = "Rejected by administrator"
        return self


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class ReviewResponse(BaseSchema):
    """Full review detail — returned to the reviewer or admin."""

    id: UUID
    entity_type: str
    entity_id: UUID
    entity_name: Optional[str] = None
    patient_id: UUID
    rating: int
    title: Optional[str] = None
    body: Optional[str] = None

    is_verified: bool
    is_approved: bool
    is_featured: bool
    helpful_count: int

    response_text: Optional[str] = None
    response_date: Optional[datetime] = None

    booking_id: Optional[UUID] = None
    consultation_id: Optional[UUID] = None

    # Reviewer display info (populated by service join)
    reviewer_name: Optional[str] = None
    reviewer_email: Optional[str] = None
    reviewer_avatar: Optional[str] = None

    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ReviewActionResponse(ReviewResponse):
    """Review response with an action message (approve/reject)."""

    message: Optional[str] = None


class ReviewPublicResponse(BaseSchema):
    """Public review — shown on entity detail pages. No private fields."""

    id: UUID
    rating: int
    title: Optional[str] = None
    body: Optional[str] = None

    is_verified: bool
    is_featured: bool
    helpful_count: int

    response_text: Optional[str] = None
    response_date: Optional[datetime] = None

    reviewer_name: Optional[str] = None
    reviewer_email: Optional[str] = None
    reviewer_avatar: Optional[str] = None

    created_at: datetime


class ReviewListItem(BaseSchema):
    """Compact item for list views."""

    id: UUID
    entity_type: str
    entity_id: UUID
    rating: int
    title: Optional[str] = None
    body: Optional[str] = None
    is_verified: bool
    is_approved: bool
    helpful_count: int
    entity_name: Optional[str] = None
    reviewer_name: Optional[str] = None
    reviewer_email: Optional[str] = None
    created_at: datetime


class ReviewSummary(BaseModel):
    """Aggregate stats for an entity's reviews."""

    entity_type: str
    entity_id: UUID
    average_rating: float
    total_reviews: int
    rating_breakdown: dict  # {1: N, 2: N, 3: N, 4: N, 5: N}
    verified_count: int
    has_response_count: int


class ReviewPaginatedResponse(BaseModel):
    """Paginated reviews with average rating."""

    items: List[ReviewPublicResponse]
    total: int
    page: int
    page_size: int
    pages: int
    average_rating: float

    @classmethod
    def create(
        cls,
        items: list,
        total: int,
        page: int,
        page_size: int,
        average_rating: float,
    ) -> "ReviewPaginatedResponse":
        pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
            average_rating=average_rating,
        )


class AllReviewItem(BaseSchema):
    """Public review item across all entity types, with the reviewed entity's name."""

    id: UUID
    entity_type: str
    entity_id: UUID
    entity_name: Optional[str] = None

    rating: int
    title: Optional[str] = None
    body: Optional[str] = None

    is_verified: bool
    is_approved: bool
    is_featured: bool
    helpful_count: int

    response_text: Optional[str] = None
    response_date: Optional[datetime] = None

    reviewer_name: Optional[str] = None
    reviewer_email: Optional[str] = None
    reviewer_avatar: Optional[str] = None

    created_at: datetime


class AllReviewsPaginatedResponse(BaseModel):
    """Paginated reviews spanning every entity type, with the overall average rating."""

    items: List[AllReviewItem]
    total: int
    page: int
    page_size: int
    pages: int
    average_rating: float

    @classmethod
    def create(
        cls,
        items: list,
        total: int,
        page: int,
        page_size: int,
        average_rating: float,
    ) -> "AllReviewsPaginatedResponse":
        pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
            average_rating=average_rating,
        )


class AdminReviewListResponse(BaseModel):
    """Admin list reviews with summary stats."""
    
    # Summary stats
    average_rating: float
    total_reviews: int
    rating_breakdown: dict  # {1: N, 2: N, 3: N, 4: N, 5: N}
    verified_count: int
    
    # Paginated items
    items: List[ReviewListItem]
    total: int
    page: int
    page_size: int