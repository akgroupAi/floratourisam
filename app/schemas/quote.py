"""Quote request ('Get a Free Medical Plan Quote') schemas."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import BaseSchema
from app.utils.enums import QuoteStatus


class QuoteStatusUpdate(BaseModel):
    """Admin status update for a quote submission."""

    status: QuoteStatus
    notes: Optional[str] = Field(None, max_length=2000)


class QuoteAssignUpdate(BaseModel):
    """Assign a quote to a team member."""

    assigned_to: UUID


class QuoteListItem(BaseSchema):
    """Quote item for admin list view."""

    id: UUID
    full_name: Optional[str] = None
    email: str
    phone: Optional[str] = None
    country: Optional[str] = None
    medical_condition: Optional[str] = None
    treatment_of_interest: Optional[str] = None
    preferred_destination: Optional[str] = None
    message: Optional[str] = None
    document_count: int = 0
    status: str
    status_label: str
    is_new: bool
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class QuoteDetailResponse(QuoteListItem):
    """Full quote detail for admin, including attachments and campaign tracking."""

    documents: List[str] = []
    assigned_to: Optional[UUID] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None


class QuoteStatsResponse(BaseModel):
    """Summary counts for the admin quote dashboard."""

    total: int
    new: int
    contacted: int
    qualified: int
    converted: int
    new_count: int
    conversion_rate: float
