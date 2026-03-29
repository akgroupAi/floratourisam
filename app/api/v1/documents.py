"""Document management endpoints."""

import os
import uuid as uuid_lib
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID
import hashlib

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.models.system import Document, DocumentShare
from app.schemas.common import PaginatedResponse
from app.schemas.system import (
    DocumentUpload, DocumentUpdate, DocumentResponse,
    DocumentShareCreate, DocumentShareResponse, DocumentStatsResponse,
)
from app.core.config import settings

router = APIRouter()

# Upload directory
UPLOAD_DIR = "uploads/documents"


def get_file_hash(file_content: bytes) -> str:
    """Calculate SHA-256 hash of file."""
    return hashlib.sha256(file_content).hexdigest()


def get_mime_type(filename: str) -> str:
    """Get MIME type from filename."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    mime_types = {
        "pdf": "application/pdf",
        "doc": "application/msword",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "txt": "text/plain",
        "csv": "text/csv",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xls": "application/vnd.ms-excel",
    }
    return mime_types.get(ext, "application/octet-stream")


# ============== DOCUMENT UPLOAD & MANAGEMENT ==============

@router.get("", response_model=PaginatedResponse[DocumentResponse])
async def list_documents(
    current_user: CurrentUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20),
    category: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[UUID] = None,
):
    """List user's documents."""
    query = select(Document).where(
        Document.user_id == current_user.id,
        Document.is_deleted == False
    )
    
    if category:
        query = query.where(Document.category == category)
    if entity_type:
        query = query.where(Document.entity_type == entity_type)
    if entity_id:
        query = query.where(Document.entity_id == entity_id)
    
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    
    query = query.order_by(Document.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    documents = result.scalars().all()
    
    return PaginatedResponse.create(documents, total, page, page_size)


@router.get("/stats", response_model=DocumentStatsResponse)
async def get_document_stats(current_user: CurrentUser, db: DatabaseSession):
    """Get document statistics for user."""
    # Total documents
    total_result = await db.execute(
        select(func.count()).select_from(Document)
        .where(Document.user_id == current_user.id, Document.is_deleted == False)
    )
    total_documents = total_result.scalar() or 0
    
    # Total size
    size_result = await db.execute(
        select(func.sum(Document.file_size))
        .where(Document.user_id == current_user.id, Document.is_deleted == False)
    )
    total_size = size_result.scalar() or 0
    
    # By category
    category_result = await db.execute(
        select(Document.category, func.count(Document.id))
        .where(Document.user_id == current_user.id, Document.is_deleted == False)
        .group_by(Document.category)
    )
    by_category = {cat: count for cat, count in category_result.all()}
    
    # Recent uploads
    recent_result = await db.execute(
        select(Document)
        .where(Document.user_id == current_user.id, Document.is_deleted == False)
        .order_by(Document.created_at.desc())
        .limit(5)
    )
    recent = recent_result.scalars().all()
    
    return DocumentStatsResponse(
        total_documents=total_documents,
        total_size_bytes=total_size,
        documents_by_category=by_category,
        recent_uploads=[DocumentResponse.model_validate(d) for d in recent],
    )


@router.post("", response_model=DocumentResponse)
async def upload_document(
    current_user: CurrentUser,
    db: DatabaseSession,
    file: UploadFile = File(...),
    category: str = Form(...),
    document_type: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    entity_type: Optional[str] = Form(None),
    entity_id: Optional[str] = Form(None),
):
    """Upload a document."""
    # Validate file size (max 50MB)
    content = await file.read()
    file_size = len(content)
    
    if file_size > 50 * 1024 * 1024:  # 50MB
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 50MB")
    
    # Generate unique filename
    original_filename = file.filename or "uploaded_document"
    ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else ""
    unique_filename = f"{uuid_lib.uuid4()}.{ext}" if ext else str(uuid_lib.uuid4())
    
    # Create user directory
    user_dir = os.path.join(UPLOAD_DIR, str(current_user.id))
    os.makedirs(user_dir, exist_ok=True)
    
    # Save file
    file_path = os.path.join(user_dir, unique_filename)
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Create document record
    document = Document(
        user_id=current_user.id,
        filename=unique_filename,
        original_filename=original_filename,
        file_path=file_path,
        file_url=f"/api/v1/documents/{unique_filename}/download",
        file_type=get_mime_type(original_filename),
        file_extension=ext,
        file_size=file_size,
        category=category,
        document_type=document_type,
        title=title or original_filename,
        description=description,
        entity_type=entity_type,
        entity_id=UUID(entity_id) if entity_id else None,
        checksum=get_file_hash(content),
        storage_provider="local",
        created_by=current_user.id,
    )
    
    db.add(document)
    await db.commit()
    await db.refresh(document)
    
    return document


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Get document by ID."""
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.id,
            Document.is_deleted == False,
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.get("/{document_id}/download")
async def download_document(document_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Download a document."""
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.id,
            Document.is_deleted == False,
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if not os.path.exists(document.file_path):
        raise HTTPException(status_code=404, detail="File not found on server")
    
    return FileResponse(
        path=document.file_path,
        filename=document.original_filename,
        media_type=document.file_type,
    )


@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: UUID,
    data: DocumentUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Update document metadata."""
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.id,
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(document, field, value)
    document.updated_by = current_user.id
    await db.commit()
    return document


@router.delete("/{document_id}")
async def delete_document(document_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Delete a document."""
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.id,
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Soft delete (keep file for recovery)
    document.soft_delete(current_user.id)
    await db.commit()
    return {"message": "Document deleted"}


# ============== DOCUMENT SHARING ==============

@router.get("/{document_id}/shares", response_model=List[DocumentShareResponse])
async def list_document_shares(document_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """List shares for a document."""
    # Verify ownership
    doc_result = await db.execute(
        select(Document).where(Document.id == document_id, Document.user_id == current_user.id)
    )
    if not doc_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Document not found")
    
    result = await db.execute(
        select(DocumentShare).where(
            DocumentShare.document_id == document_id,
            DocumentShare.is_active == True,
        )
    )
    return result.scalars().all()


@router.post("/{document_id}/share", response_model=DocumentShareResponse)
async def share_document(
    document_id: UUID,
    data: DocumentShareCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Share a document."""
    # Verify ownership
    doc_result = await db.execute(
        select(Document).where(Document.id == document_id, Document.user_id == current_user.id)
    )
    if not doc_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Generate share token
    share_token = str(uuid_lib.uuid4())
    
    share = DocumentShare(
        document_id=document_id,
        shared_with_user_id=data.shared_with_user_id,
        shared_with_email=data.shared_with_email,
        permission=data.permission,
        expires_at=data.expires_at,
        share_token=share_token,
        password_protected=bool(data.password),
        created_by=current_user.id,
    )
    
    if data.password:
        from app.core.security import get_password_hash
        share.password_hash = get_password_hash(data.password)
    
    db.add(share)
    await db.commit()
    await db.refresh(share)
    
    return share


@router.delete("/{document_id}/shares/{share_id}")
async def revoke_share(
    document_id: UUID,
    share_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Revoke a document share."""
    result = await db.execute(
        select(DocumentShare)
        .join(Document)
        .where(
            DocumentShare.id == share_id,
            DocumentShare.document_id == document_id,
            Document.user_id == current_user.id,
        )
    )
    share = result.scalar_one_or_none()
    if not share:
        raise HTTPException(status_code=404, detail="Share not found")
    
    share.is_active = False
    share.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    return {"message": "Share revoked"}


# ============== SHARED DOCUMENT ACCESS ==============

@router.get("/shared/{share_token}")
async def access_shared_document(
    share_token: str,
    db: DatabaseSession,
    password: Optional[str] = None,
):
    """Access a shared document via token."""
    result = await db.execute(
        select(DocumentShare)
        .where(DocumentShare.share_token == share_token, DocumentShare.is_active == True)
    )
    share = result.scalar_one_or_none()
    
    if not share:
        raise HTTPException(status_code=404, detail="Share not found or expired")
    
    # Check expiry
    if share.expires_at and share.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Share link has expired")
    
    # Check password
    if share.password_protected:
        if not password:
            return {"requires_password": True}
        from app.core.security import verify_password
        if not verify_password(password, share.password_hash):
            raise HTTPException(status_code=401, detail="Invalid password")
    
    # Get document
    doc_result = await db.execute(select(Document).where(Document.id == share.document_id))
    document = doc_result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Update access tracking
    share.accessed_at = datetime.now(timezone.utc)
    share.access_count += 1
    await db.commit()
    
    return {
        "document": DocumentResponse.model_validate(document),
        "permission": share.permission,
        "download_url": f"/api/v1/documents/shared/{share_token}/download" if share.permission in ["download", "edit"] else None,
    }


@router.get("/shared/{share_token}/download")
async def download_shared_document(share_token: str, db: DatabaseSession, password: Optional[str] = None):
    """Download a shared document."""
    result = await db.execute(
        select(DocumentShare)
        .where(DocumentShare.share_token == share_token, DocumentShare.is_active == True)
    )
    share = result.scalar_one_or_none()
    
    if not share or share.permission not in ["download", "edit"]:
        raise HTTPException(status_code=403, detail="Download not permitted")
    
    # Check expiry and password (same as access)
    if share.expires_at and share.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Share link has expired")
    
    if share.password_protected:
        if not password:
            raise HTTPException(status_code=401, detail="Password required")
        from app.core.security import verify_password
        if not verify_password(password, share.password_hash):
            raise HTTPException(status_code=401, detail="Invalid password")
    
    # Get document
    doc_result = await db.execute(select(Document).where(Document.id == share.document_id))
    document = doc_result.scalar_one_or_none()
    
    if not document or not os.path.exists(document.file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=document.file_path,
        filename=document.original_filename,
        media_type=document.file_type,
    )


# ============== ADMIN ENDPOINTS ==============

@router.get("/admin/all", response_model=PaginatedResponse[DocumentResponse], dependencies=[RequireAdmin])
async def admin_list_all_documents(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20),
    user_id: Optional[UUID] = None,
    category: Optional[str] = None,
):
    """List all documents (admin)."""
    query = select(Document).where(Document.is_deleted == False)
    
    if user_id:
        query = query.where(Document.user_id == user_id)
    if category:
        query = query.where(Document.category == category)
    
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    
    query = query.order_by(Document.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    documents = result.scalars().all()
    
    return PaginatedResponse.create(documents, total, page, page_size)


@router.get("/admin/stats", dependencies=[RequireAdmin])
async def admin_document_stats(db: DatabaseSession):
    """Get system-wide document statistics (admin)."""
    # Total documents
    total_result = await db.execute(
        select(func.count()).select_from(Document).where(Document.is_deleted == False)
    )
    total_documents = total_result.scalar() or 0
    
    # Total size
    size_result = await db.execute(
        select(func.sum(Document.file_size)).where(Document.is_deleted == False)
    )
    total_size = size_result.scalar() or 0
    
    # By category
    category_result = await db.execute(
        select(Document.category, func.count(Document.id))
        .where(Document.is_deleted == False)
        .group_by(Document.category)
    )
    by_category = {cat: count for cat, count in category_result.all()}
    
    # Unique users
    users_result = await db.execute(
        select(func.count(func.distinct(Document.user_id))).where(Document.is_deleted == False)
    )
    unique_users = users_result.scalar() or 0
    
    return {
        "total_documents": total_documents,
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "documents_by_category": by_category,
        "unique_users_with_documents": unique_users,
    }
