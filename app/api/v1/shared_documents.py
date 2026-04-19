"""Endpoints for doctor-patient document sharing.

Supports:
  - Send document to another user (patient→doctor, doctor→patient)
  - List sent / received documents (tabs)
  - View document detail with comments
  - Mark document as viewed
  - Add comments on documents
  - Stats (sent count, received count, unviewed)
"""

import os
import uuid as uuid_mod
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status

from app.api.deps import CurrentUser, DatabaseSession
from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.common import PaginatedResponse
from app.schemas.shared_document import (
    DocumentCommentCreate,
    DocumentCommentResponse,
    SendDocumentRequest,
    SharedDocumentListItem,
    SharedDocumentResponse,
    SharedDocumentStatsResponse,
)
from app.services.shared_document_service import SharedDocumentService

logger = get_logger(__name__)

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt", ".dicom", ".dcm"}


@router.post(
    "/send",
    response_model=SharedDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send a document to another user",
    description="Upload a file/image and send it to another user (patient→doctor or doctor→patient).",
)
async def send_document(
    current_user: CurrentUser,
    db: DatabaseSession,
    file: UploadFile = File(..., description="The file or image to upload"),
    receiver_id: UUID = Form(..., description="User ID of the recipient"),
    title: str = Form(..., max_length=255),
    document_type: Optional[str] = Form(
        default=None,
        max_length=50,
        description="lab_report, prescription, xray, mri_scan, ct_scan, blood_test, medical_certificate, discharge_summary, other",
    ),
    description: Optional[str] = Form(default=None, max_length=2000),
    consultation_id: Optional[UUID] = Form(default=None, description="Link to a consultation"),
    document_id: Optional[UUID] = Form(default=None, description="Link to existing document record"),
):
    if receiver_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot send a document to yourself")

    # Validate file extension
    original_name = file.filename or "unknown"
    ext = Path(original_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # Read file content and validate size
    content = await file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit.",
        )

    # Save to disk
    upload_dir = Path(settings.UPLOAD_DIR) / "shared_documents"
    upload_dir.mkdir(parents=True, exist_ok=True)
    unique_name = f"{uuid_mod.uuid4().hex}{ext}"
    file_path = upload_dir / unique_name

    with open(file_path, "wb") as f:
        f.write(content)

    file_url = f"/static/uploads/shared_documents/{unique_name}"

    data = SendDocumentRequest(
        receiver_id=receiver_id,
        title=title,
        file_url=file_url,
        file_name=original_name,
        file_type=file.content_type,
        file_size=len(content),
        document_type=document_type,
        description=description,
        consultation_id=consultation_id,
        document_id=document_id,
    )

    service = SharedDocumentService(db)
    doc = await service.send_document(current_user.id, data)
    detail = await service.get_detail(doc.id)
    return detail


@router.get(
    "/sent",
    response_model=PaginatedResponse[SharedDocumentListItem],
    summary="List documents I sent",
    description="Returns documents the current user has sent to others, newest first.",
)
async def list_sent_documents(
    current_user: CurrentUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    service = SharedDocumentService(db)
    items, total = await service.list_sent(current_user.id, page, page_size)
    return PaginatedResponse.create(items, total, page, page_size)


@router.get(
    "/received",
    response_model=PaginatedResponse[SharedDocumentListItem],
    summary="List documents I received",
    description="Returns documents sent to the current user, newest first.",
)
async def list_received_documents(
    current_user: CurrentUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    service = SharedDocumentService(db)
    items, total = await service.list_received(current_user.id, page, page_size)
    return PaginatedResponse.create(items, total, page, page_size)


@router.get(
    "/stats",
    response_model=SharedDocumentStatsResponse,
    summary="Get document sharing stats",
    description="Returns sent count, received count, and unviewed count for tabs/badges.",
)
async def get_document_stats(
    current_user: CurrentUser,
    db: DatabaseSession,
):
    service = SharedDocumentService(db)
    return await service.get_stats(current_user.id)


@router.get(
    "/{shared_doc_id}",
    response_model=SharedDocumentResponse,
    summary="Get shared document detail",
    description="Returns document with full comments. Auto-marks as viewed if you are the receiver.",
)
async def get_shared_document(
    shared_doc_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    service = SharedDocumentService(db)
    doc = await service.get_by_id(shared_doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Shared document not found")

    # Only sender or receiver can view
    if current_user.id not in (doc.sender_id, doc.receiver_id):
        raise HTTPException(status_code=403, detail="Not authorized to view this document")

    # Auto-mark as viewed if receiver opens it
    if current_user.id == doc.receiver_id and not doc.is_viewed:
        await service.mark_viewed(shared_doc_id)

    detail = await service.get_detail(shared_doc_id)
    return detail


@router.post(
    "/{shared_doc_id}/viewed",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark document as viewed",
    description="Explicitly mark a received document as viewed.",
)
async def mark_document_viewed(
    shared_doc_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    service = SharedDocumentService(db)
    doc = await service.get_by_id(shared_doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Shared document not found")
    if current_user.id != doc.receiver_id:
        raise HTTPException(status_code=403, detail="Only the receiver can mark as viewed")
    await service.mark_viewed(shared_doc_id)


@router.post(
    "/{shared_doc_id}/comments",
    response_model=DocumentCommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a comment on a shared document",
    description="Both sender and receiver can add comments.",
)
async def add_comment(
    shared_doc_id: UUID,
    data: DocumentCommentCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    service = SharedDocumentService(db)
    doc = await service.get_by_id(shared_doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Shared document not found")
    if current_user.id not in (doc.sender_id, doc.receiver_id):
        raise HTTPException(status_code=403, detail="Not authorized to comment on this document")

    return await service.add_comment(shared_doc_id, current_user.id, data)
