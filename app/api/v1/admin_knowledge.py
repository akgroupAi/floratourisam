"""Admin — Knowledge Document management for RAG chatbot."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.schemas.common import PaginatedResponse
from app.schemas.knowledge_document import (
    KnowledgeDocumentCreate,
    KnowledgeDocumentListResponse,
    KnowledgeDocumentResponse,
    KnowledgeDocumentUpdate,
)
from app.services.knowledge_document_service import KnowledgeDocumentService

router = APIRouter()


@router.post(
    "",
    response_model=KnowledgeDocumentResponse,
    status_code=201,
    dependencies=[RequireAdmin],
)
async def create_knowledge_document(
    data: KnowledgeDocumentCreate,
    db: DatabaseSession,
    current_user: CurrentUser,
):
    """Create a new knowledge document for the RAG chatbot."""
    service = KnowledgeDocumentService(db)
    return await service.create(data, created_by=current_user.id)


@router.get(
    "",
    response_model=PaginatedResponse[KnowledgeDocumentListResponse],
    dependencies=[RequireAdmin],
)
async def list_knowledge_documents(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    active_only: bool = False,
    search: Optional[str] = None,
):
    """List knowledge documents with filtering and pagination."""
    service = KnowledgeDocumentService(db)
    items, total = await service.list_docs(
        page=page,
        page_size=page_size,
        category=category,
        active_only=active_only,
        search=search,
    )
    return PaginatedResponse.create(items, total, page, page_size)


@router.get(
    "/categories",
    response_model=list[str],
    dependencies=[RequireAdmin],
)
async def list_categories(db: DatabaseSession):
    """Get all distinct active categories."""
    service = KnowledgeDocumentService(db)
    return await service.get_categories()


@router.get(
    "/{doc_id}",
    response_model=KnowledgeDocumentResponse,
    dependencies=[RequireAdmin],
)
async def get_knowledge_document(doc_id: UUID, db: DatabaseSession):
    """Get a single knowledge document by ID."""
    service = KnowledgeDocumentService(db)
    doc = await service.get(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Knowledge document not found")
    return doc


@router.put(
    "/{doc_id}",
    response_model=KnowledgeDocumentResponse,
    dependencies=[RequireAdmin],
)
async def update_knowledge_document(
    doc_id: UUID,
    data: KnowledgeDocumentUpdate,
    db: DatabaseSession,
    current_user: CurrentUser,
):
    """Update a knowledge document."""
    service = KnowledgeDocumentService(db)
    try:
        return await service.update(doc_id, data, updated_by=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete(
    "/{doc_id}",
    status_code=204,
    dependencies=[RequireAdmin],
)
async def delete_knowledge_document(
    doc_id: UUID,
    db: DatabaseSession,
    current_user: CurrentUser,
):
    """Soft-delete a knowledge document."""
    service = KnowledgeDocumentService(db)
    try:
        await service.delete(doc_id, deleted_by=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
