"""Endpoints for doctor-patient document sharing.

Supports:
  - Send document to another user (patient→doctor, doctor→patient)
  - List sent / received documents (tabs)
  - View document detail with comments
  - Mark document as viewed
  - Add comments on documents
  - Stats (sent count, received count, unviewed)
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DatabaseSession
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


@router.post(
    "/send",
    response_model=SharedDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send a document to another user",
    description="Patient sends to doctor or doctor sends to patient. Upload the file first, then pass the URL here.",
)
async def send_document(
    data: SendDocumentRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    if data.receiver_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot send a document to yourself")

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
