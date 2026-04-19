"""Schemas for doctor-patient document sharing."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import BaseSchema


# ── Request schemas ────────────────────────────────────────────


class SendDocumentRequest(BaseModel):
    """Send a document to another user (patient→doctor or doctor→patient)."""

    receiver_id: UUID = Field(..., description="User ID of the recipient")
    title: str = Field(..., max_length=255)
    file_url: str = Field(..., max_length=500, description="URL of the uploaded file")
    file_name: str = Field(..., max_length=255)
    file_type: Optional[str] = Field(default=None, max_length=100, description="MIME type")
    file_size: Optional[int] = Field(default=None, description="File size in bytes")
    document_type: Optional[str] = Field(
        default=None,
        max_length=50,
        description="lab_report, prescription, xray, mri_scan, ct_scan, blood_test, medical_certificate, discharge_summary, other",
    )
    description: Optional[str] = Field(default=None, max_length=2000)
    consultation_id: Optional[UUID] = Field(default=None, description="Link to a consultation")
    document_id: Optional[UUID] = Field(default=None, description="Link to existing document record")


class DocumentCommentCreate(BaseModel):
    """Add a comment to a shared document."""

    content: str = Field(..., max_length=2000)


# ── Response schemas ───────────────────────────────────────────


class DocumentCommentResponse(BaseSchema):
    """Comment on a shared document."""

    id: UUID
    shared_document_id: UUID
    user_id: UUID
    content: str
    created_at: datetime

    # Populated by service
    user_name: Optional[str] = None


class SharedDocumentResponse(BaseSchema):
    """Shared document detail."""

    id: UUID
    sender_id: UUID
    receiver_id: UUID
    document_id: Optional[UUID] = None
    consultation_id: Optional[UUID] = None
    title: str
    file_name: str
    file_url: str
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    document_type: Optional[str] = None
    description: Optional[str] = None
    is_viewed: bool
    viewed_at: Optional[datetime] = None
    created_at: datetime

    # Populated by service
    sender_name: Optional[str] = None
    receiver_name: Optional[str] = None
    comment_count: int = 0
    comments: List[DocumentCommentResponse] = []


class SharedDocumentListItem(BaseSchema):
    """Shared document in a list (without full comments)."""

    id: UUID
    sender_id: UUID
    receiver_id: UUID
    title: str
    file_name: str
    file_url: str
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    document_type: Optional[str] = None
    is_viewed: bool
    viewed_at: Optional[datetime] = None
    created_at: datetime

    # Populated by service
    sender_name: Optional[str] = None
    receiver_name: Optional[str] = None
    comment_count: int = 0
    latest_comment: Optional[str] = None


class SharedDocumentStatsResponse(BaseModel):
    """Stats for the documents tab."""

    sent_count: int
    received_count: int
    unviewed_count: int
