"""Notification, Email, Event, Config, and Document models."""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, BigInteger
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Notification(BaseModel):
    """User notification."""

    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Content
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)  # info, success, warning, error, booking, payment, consultation
    
    # Action
    action_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    action_text: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Related entity
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # booking, consultation, payment
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    
    # Status
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # Channels
    sent_push: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_email: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_sms: Mapped[bool] = mapped_column(Boolean, default=False)


class EmailTemplate(BaseModel):
    """Email template for transactional emails."""

    __tablename__ = "email_templates"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Content
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    body_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Variables
    variables: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)  # Available template variables
    
    # Category
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # auth, booking, consultation, notification, marketing
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Metadata
    from_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    from_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reply_to: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class EmailLog(BaseModel):
    """Email sending log."""

    __tablename__ = "email_logs"

    template_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("email_templates.id"), nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Recipients
    to_email: Mapped[str] = mapped_column(String(255), nullable=False)
    to_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cc: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    bcc: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    
    # Content
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Status
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, sent, delivered, failed, bounced
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    clicked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Error
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Provider
    provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # sendgrid, ses, smtp
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Metadata
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


class Event(BaseModel):
    """Scheduled event/appointment."""

    __tablename__ = "events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Event details
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # consultation, appointment, follow_up, reminder, travel, accommodation
    
    # Timing
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    
    # Location
    location: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    location_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # online, in_person
    meeting_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Related entity
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    
    # Recurrence
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    recurrence_rule: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # iCal RRULE format
    recurrence_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    parent_event_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=True)
    
    # Reminders
    reminders: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # [{"type": "email", "minutes_before": 60}]
    
    # Status
    status: Mapped[str] = mapped_column(String(20), default="scheduled")  # scheduled, confirmed, cancelled, completed
    
    # Attendees
    attendees: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # [{user_id, email, status}]
    
    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Color/Display
    color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    
    # Metadata
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


class AdminConfig(BaseModel):
    """System configuration values."""

    __tablename__ = "admin_configs"

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    
    # Categorization
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # general, email, payment, booking, notification, seo, integration
    
    # Metadata
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    value_type: Mapped[str] = mapped_column(String(20), default="string")  # string, number, boolean, json, array
    
    # Validation
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    default_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    validation_rules: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # Access
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)  # Visible to frontend
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)  # API keys, secrets
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Audit
    last_modified_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)


class Document(BaseModel):
    """User document storage."""

    __tablename__ = "documents"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # File info
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Type info
    file_type: Mapped[str] = mapped_column(String(100), nullable=False)  # MIME type
    file_extension: Mapped[str] = mapped_column(String(20), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)  # bytes
    
    # Categorization
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # medical_record, passport, insurance, prescription, report, invoice, other
    document_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # More specific type
    
    # Description
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    
    # Related entity
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # consultation, booking, patient
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    
    # Validity
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Security
    is_encrypted: Mapped[bool] = mapped_column(Boolean, default=False)
    encryption_key_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Access
    is_private: Mapped[bool] = mapped_column(Boolean, default=True)
    shared_with: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)  # User IDs
    access_level: Mapped[str] = mapped_column(String(20), default="owner")  # owner, shared, public
    
    # Processing
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    ocr_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_analysis: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # Storage
    storage_provider: Mapped[str] = mapped_column(String(50), default="local")  # local, s3, gcs
    storage_bucket: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Metadata
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # Checksum
    checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # SHA-256


class DocumentShare(BaseModel):
    """Document sharing record."""

    __tablename__ = "document_shares"

    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    shared_with_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    shared_with_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Access
    permission: Mapped[str] = mapped_column(String(20), default="view")  # view, download, edit
    
    # Validity
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Access tracking
    accessed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Security
    share_token: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True)
    password_protected: Mapped[bool] = mapped_column(Boolean, default=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
