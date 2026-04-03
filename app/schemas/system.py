"""Schemas for notifications, email, events, config, and documents."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.common import BaseSchema


# ============== Notification Schemas ==============

class NotificationCreate(BaseModel):
    """Create notification (internal use)."""
    user_id: UUID
    title: str = Field(..., max_length=255)
    message: str
    notification_type: str = Field(default="info", pattern="^(info|success|warning|error|booking|payment|consultation)$")
    action_url: Optional[str] = None
    action_text: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    metadata: Optional[dict] = None


class NotificationResponse(BaseSchema):
    """Notification response."""
    id: UUID
    title: str
    message: str
    notification_type: str
    action_url: Optional[str] = None
    action_text: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime


class NotificationListResponse(BaseModel):
    """Notification list with unread count."""
    notifications: List[NotificationResponse]
    total: int
    unread_count: int


class NotificationMarkRead(BaseModel):
    """Mark notifications as read."""
    notification_ids: List[UUID] = Field(..., min_length=1, max_length=100)


class NotificationPreferences(BaseModel):
    """User notification preferences."""
    email_enabled: bool = True
    push_enabled: bool = True
    sms_enabled: bool = False
    booking_notifications: bool = True
    consultation_notifications: bool = True
    payment_notifications: bool = True
    marketing_notifications: bool = False


# ============== Email Template Schemas ==============

class EmailTemplateCreate(BaseModel):
    """Create email template."""
    name: str = Field(..., max_length=100)
    slug: str = Field(..., max_length=100, pattern="^[a-z0-9_-]+$")
    description: Optional[str] = None
    subject: str = Field(..., max_length=255)
    body_html: str
    body_text: Optional[str] = None
    variables: List[str] = []
    category: str = Field(..., pattern="^(auth|booking|consultation|notification|marketing)$")
    from_name: Optional[str] = None
    from_email: Optional[EmailStr] = None
    reply_to: Optional[EmailStr] = None


class EmailTemplateUpdate(BaseModel):
    """Update email template."""
    name: Optional[str] = None
    description: Optional[str] = None
    subject: Optional[str] = None
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    variables: Optional[List[str]] = None
    is_active: Optional[bool] = None
    from_name: Optional[str] = None
    from_email: Optional[EmailStr] = None
    reply_to: Optional[EmailStr] = None


class EmailTemplateResponse(BaseSchema):
    """Email template response."""
    id: UUID
    name: str
    slug: str
    description: Optional[str] = None
    subject: str
    body_html: str
    body_text: Optional[str] = None
    variables: List[str] = []
    category: str
    is_active: bool
    from_name: Optional[str] = None
    from_email: Optional[str] = None
    reply_to: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SendEmailRequest(BaseModel):
    """Send email request."""
    template_slug: Optional[str] = None  # Use template
    to_email: EmailStr
    to_name: Optional[str] = None
    cc: List[EmailStr] = []
    bcc: List[EmailStr] = []
    subject: Optional[str] = None  # Override template subject
    body_html: Optional[str] = None  # Custom body if no template
    variables: Dict[str, Any] = {}  # Template variables
    attachments: List[str] = []  # File URLs or IDs


class EmailLogResponse(BaseSchema):
    """Email log response."""
    id: UUID
    to_email: str
    to_name: Optional[str] = None
    subject: str
    status: str
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime


# ============== Event Schemas ==============

class EventCreate(BaseModel):
    """Create event."""
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    event_type: str = Field(..., pattern="^(consultation|appointment|follow_up|reminder|travel|accommodation)$")
    start_time: datetime
    end_time: Optional[datetime] = None
    all_day: bool = False
    timezone: str = "UTC"
    location: Optional[str] = None
    location_type: Optional[str] = Field(None, pattern="^(online|in_person)$")
    meeting_url: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    is_recurring: bool = False
    recurrence_rule: Optional[str] = None
    reminders: Optional[List[dict]] = None
    attendees: Optional[List[dict]] = None
    notes: Optional[str] = None
    color: Optional[str] = None


class EventUpdate(BaseModel):
    """Update event."""
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    all_day: Optional[bool] = None
    timezone: Optional[str] = None
    location: Optional[str] = None
    location_type: Optional[str] = None
    meeting_url: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(scheduled|confirmed|cancelled|completed)$")
    reminders: Optional[List[dict]] = None
    notes: Optional[str] = None
    color: Optional[str] = None


class EventResponse(BaseSchema):
    """Event response."""
    id: UUID
    user_id: UUID
    title: str
    description: Optional[str] = None
    event_type: str
    start_time: datetime
    end_time: Optional[datetime] = None
    all_day: bool
    timezone: str
    location: Optional[str] = None
    location_type: Optional[str] = None
    meeting_url: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    is_recurring: bool
    recurrence_rule: Optional[str] = None
    status: str
    reminders: Optional[List[dict]] = None
    attendees: Optional[List[dict]] = None
    notes: Optional[str] = None
    color: Optional[str] = None
    created_at: datetime


class CalendarView(BaseModel):
    """Calendar view parameters."""
    start_date: datetime
    end_date: datetime
    event_types: List[str] = []


# ============== Admin Config Schemas ==============

class AdminConfigCreate(BaseModel):
    """Create admin config."""
    key: str = Field(..., max_length=100, pattern="^[A-Z][A-Z0-9_]*$")
    value: Any
    category: str = Field(..., pattern="^(general|email|payment|booking|notification|seo|integration)$")
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    value_type: str = Field(default="string", pattern="^(string|number|boolean|json|array)$")
    is_required: bool = False
    default_value: Optional[Any] = None
    is_public: bool = False
    is_sensitive: bool = False


class AdminConfigUpdate(BaseModel):
    """Update admin config value."""
    value: Any
    description: Optional[str] = None


class AdminConfigResponse(BaseSchema):
    """Admin config response."""
    id: UUID
    key: str
    value: Any
    category: str
    name: str
    description: Optional[str] = None
    value_type: str
    is_required: bool
    default_value: Optional[Any] = None
    is_public: bool
    is_sensitive: bool
    is_active: bool
    updated_at: datetime


class AdminConfigPublicResponse(BaseModel):
    """Public config response (non-sensitive)."""
    key: str
    value: Any


class ConfigBulkUpdate(BaseModel):
    """Bulk update configs."""
    configs: Dict[str, Any]  # key: value pairs


# ============== Document Schemas ==============

class DocumentUpload(BaseModel):
    """Document upload metadata."""
    category: str = Field(..., pattern="^(medical_record|passport|insurance|prescription|report|invoice|other)$")
    document_type: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = []
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    is_private: bool = True


class DocumentUpdate(BaseModel):
    """Update document metadata."""
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    category: Optional[str] = None
    document_type: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None


class DocumentResponse(BaseSchema):
    """Document response."""
    id: UUID
    user_id: UUID
    filename: str
    original_filename: str
    file_url: Optional[str] = None
    file_type: str
    file_extension: str
    file_size: int
    category: str
    document_type: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = []
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    is_private: bool
    is_processed: bool
    created_at: datetime

    @field_validator("tags", mode="before")
    @classmethod
    def coerce_tags(cls, v):
        """Convert None to empty list."""
        return v if v is not None else []


class DocumentShareCreate(BaseModel):
    """Share document."""
    shared_with_user_id: Optional[UUID] = None
    shared_with_email: Optional[EmailStr] = None
    permission: str = Field(default="view", pattern="^(view|download|edit)$")
    expires_at: Optional[datetime] = None
    password: Optional[str] = None


class DocumentShareResponse(BaseSchema):
    """Document share response."""
    id: UUID
    document_id: UUID
    shared_with_user_id: Optional[UUID] = None
    shared_with_email: Optional[str] = None
    permission: str
    expires_at: Optional[datetime] = None
    share_token: Optional[str] = None
    share_url: Optional[str] = None
    is_active: bool
    access_count: int
    created_at: datetime


class DocumentStatsResponse(BaseModel):
    """User document statistics."""
    total_documents: int
    total_size_bytes: int
    documents_by_category: Dict[str, int]
    recent_uploads: List[DocumentResponse]
