"""Endpoints for doctor-patient document sharing.

Supports:
  - Send document to another user (patient→doctor, doctor→patient)
  - List sent / received documents (tabs)
  - View document detail with comments
  - Mark document as viewed
  - Add comments on documents
  - Stats (sent count, received count, unviewed)
"""

from typing import Optional
from uuid import UUID
import uuid as uuid_mod
import os
from pathlib import Path

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


ALLOWED_EXTENSIONS = {
    ".pdf", ".jpg", ".jpeg", ".png", ".webp", ".gif",
    ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt",
    ".dicom", ".dcm", ".zip", ".rar",
}
MAX_FILE_SIZE_MB = 20


@router.post(
    "/send",
    response_model=SharedDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send a document to another user",
    description="Upload a file directly and send it to another user (patient↔doctor).",
)
async def send_document(
    current_user: CurrentUser,
    db: DatabaseSession,
    file: UploadFile = File(..., description="The document file to upload"),
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
    ext = Path(file.filename).suffix.lower() if file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type '{ext}' not allowed")

    # Validate file size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File too large. Max {MAX_FILE_SIZE_MB} MB")

    # Save file
    upload_dir = os.path.join(settings.UPLOAD_DIR, "shared_documents")
    os.makedirs(upload_dir, exist_ok=True)
    unique_name = f"{uuid_mod.uuid4().hex}{ext}"
    file_path = os.path.join(upload_dir, unique_name)
    with open(file_path, "wb") as f:
        f.write(contents)

    file_url = f"/static/uploads/shared_documents/{unique_name}"

    data = SendDocumentRequest(
        receiver_id=receiver_id,
        title=title,
        file_url=file_url,
        file_name=file.filename or unique_name,
        file_type=file.content_type,
        file_size=len(contents),
        document_type=document_type,
        description=description,
        consultation_id=consultation_id,
        document_id=document_id,
    )

    service = SharedDocumentService(db)
    try:
        doc = await service.send_document(current_user.id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    detail = await service.get_detail(doc.id)
    return detail


@router.get(
    "/sent",
    response_model=list[SharedDocumentListItem],
    summary="List documents I sent",
    description="Returns all documents the current user has sent to others, newest first.",
)
async def list_sent_documents(
    current_user: CurrentUser,
    db: DatabaseSession,
):
    service = SharedDocumentService(db)
    return await service.list_all_sent(current_user.id)


@router.get(
    "/received",
    response_model=list[SharedDocumentListItem],
    summary="List documents I received",
    description="Returns all documents sent to the current user, newest first.",
)
async def list_received_documents(
    current_user: CurrentUser,
    db: DatabaseSession,
):
    service = SharedDocumentService(db)
    return await service.list_all_received(current_user.id)


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
