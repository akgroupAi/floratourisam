"""Contact form schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import BaseSchema
from app.utils.enums import ContactStatus


class ContactCreate(BaseModel):
    """Public contact form submission."""

    full_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    phone: str = Field(..., min_length=5, max_length=20)
    country: str = Field(..., min_length=2, max_length=100)
    treatment_of_interest: Optional[str] = Field(None, max_length=255)
    message: str = Field(..., min_length=10, max_length=5000)


class ContactSubmitResponse(BaseModel):
    """Response after submitting the contact form."""

    success: bool = True
    message: str
    reference_id: UUID


class ContactStatusUpdate(BaseModel):
    """Admin status update for a contact submission."""

    status: ContactStatus
    notes: Optional[str] = Field(None, max_length=2000)


class ContactListItem(BaseSchema):
    """Contact item for admin list view."""

    id: UUID
    full_name: Optional[str] = None
    email: str
    phone: Optional[str] = None
    country: Optional[str] = None
    treatment_of_interest: Optional[str] = None
    message: Optional[str] = None
    status: str
    status_label: str
    is_new: bool
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ContactDetailResponse(ContactListItem):
    """Full contact detail for admin."""

    assigned_to: Optional[UUID] = None


class ContactStatsResponse(BaseModel):
    """Summary counts for admin contact dashboard."""

    total: int
    pending: int
    in_process: int
    completed: int
    new_count: int
