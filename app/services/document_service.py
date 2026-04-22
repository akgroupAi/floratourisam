"""Document service for medical document management."""

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.medical_report import MedicalReport
from app.schemas.medical_document import (
    DocumentDetailResponse,
    DocumentListItem,
    DocumentUploadResponse,
)

logger = get_logger(__name__)

# Allowed file extensions
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "dcm", "doc", "docx"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "application/dicom",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class DocumentService:
    """Service for managing patient medical documents."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.upload_dir = Path(settings.UPLOAD_DIR) / "medical_documents"
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def _validate_file(self, file: UploadFile) -> None:
        """Validate uploaded file."""
        # Check file extension
        if file.filename:
            ext = file.filename.split(".")[-1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}",
                )

        # Check MIME type
        if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type: {file.content_type}",
            )

    async def _save_file(
        self, file: UploadFile, patient_id: uuid.UUID, document_id: uuid.UUID
    ) -> tuple[str, int]:
        """Save uploaded file to disk."""
        # Create patient directory
        patient_dir = self.upload_dir / str(patient_id)
        patient_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename
        ext = file.filename.split(".")[-1].lower() if file.filename else "bin"
        file_name = f"{document_id}.{ext}"
        file_path = patient_dir / file_name

        # Save file
        content = await file.read()
        file_size = len(content)

        # Check file size
        max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Maximum size: {settings.MAX_UPLOAD_SIZE_MB}MB",
            )

        with open(file_path, "wb") as f:
            f.write(content)

        logger.info(
            "file_uploaded",
            patient_id=str(patient_id),
            document_id=str(document_id),
            file_size=file_size,
        )

        return str(file_path), file_size

    def _get_download_url(self, document_id: uuid.UUID) -> str:
        """Generate download URL for document."""
        return f"/api/v1/patients/me/documents/{document_id}/download"

    async def upload_document(
        self,
        patient_id: uuid.UUID,
        file: UploadFile,
        title: str,
        document_type: str,
        description: Optional[str] = None,
    ) -> DocumentUploadResponse:
        """Upload a medical document."""
        # Validate file
        self._validate_file(file)

        # Create document record
        document_id = uuid.uuid4()
        file_path, file_size = await self._save_file(file, patient_id, document_id)
        
        # Generate API download URL instead of storing filesystem path
        download_url = self._get_download_url(document_id)

        # Create database record
        document = MedicalReport(
            id=document_id,
            patient_id=patient_id,
            title=title,
            report_type=document_type,
            description=description,
            file_url=download_url,  # Store API endpoint, not filesystem path
            file_name=file.filename or f"document.{file_path.split('.')[-1]}",
            file_type=file.content_type or "application/octet-stream",
            file_size_bytes=file_size,
            report_date=datetime.now(timezone.utc),
        )

        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)

        logger.info("document_created", document_id=str(document_id), patient_id=str(patient_id))

        return DocumentUploadResponse(
            id=document.id,
            title=document.title,
            document_type=document.report_type,
            file_name=document.file_name,
            file_size=document.file_size_bytes,
            file_type=document.file_type,
            upload_date=document.created_at,
            download_url=download_url,
        )

    async def get_documents(
        self, patient_id: uuid.UUID, document_type: Optional[str] = None
    ) -> List[DocumentListItem]:
        """Get all documents for a patient."""
        query = select(MedicalReport).where(
            MedicalReport.patient_id == patient_id, MedicalReport.is_deleted == False
        )

        if document_type:
            query = query.where(MedicalReport.report_type == document_type)

        query = query.order_by(MedicalReport.created_at.desc())

        result = await self.db.execute(query)
        documents = result.scalars().all()

        return [
            DocumentListItem(
                id=doc.id,
                title=doc.title,
                document_type=doc.report_type,
                file_name=doc.file_name,
                file_size=doc.file_size_bytes,
                upload_date=doc.created_at,
                download_url=self._get_download_url(doc.id),
                is_private=doc.is_private,
            )
            for doc in documents
        ]

    async def get_document_by_id(
        self, document_id: uuid.UUID, patient_id: uuid.UUID
    ) -> Optional[DocumentDetailResponse]:
        """Get specific document by ID."""
        result = await self.db.execute(
            select(MedicalReport).where(
                MedicalReport.id == document_id,
                MedicalReport.patient_id == patient_id,
                MedicalReport.is_deleted == False,
            )
        )
        document = result.scalar_one_or_none()

        if not document:
            return None

        return DocumentDetailResponse(
            id=document.id,
            title=document.title,
            document_type=document.report_type,
            description=document.description,
            file_name=document.file_name,
            file_size=document.file_size_bytes,
            file_type=document.file_type,
            upload_date=document.created_at,
            report_date=document.report_date,
            facility_name=document.facility_name,
            performing_doctor=document.performing_doctor,
            interpretation=document.interpretation,
            is_abnormal=document.is_abnormal,
            requires_followup=document.requires_followup,
            is_private=document.is_private,
            download_url=self._get_download_url(document.id),
        )

    async def get_file_path(
        self, document_id: uuid.UUID, patient_id: uuid.UUID
    ) -> Optional[str]:
        """Get file path for download."""
        result = await self.db.execute(
            select(MedicalReport).where(
                MedicalReport.id == document_id,
                MedicalReport.patient_id == patient_id,
                MedicalReport.is_deleted == False,
            )
        )
        document = result.scalar_one_or_none()

        if not document or not document.file_url:
            return None

        return document.file_url

    async def delete_document(self, document_id: uuid.UUID, patient_id: uuid.UUID) -> bool:
        """Delete a document."""
        result = await self.db.execute(
            select(MedicalReport).where(
                MedicalReport.id == document_id,
                MedicalReport.patient_id == patient_id,
                MedicalReport.is_deleted == False,
            )
        )
        document = result.scalar_one_or_none()

        if not document:
            return False

        # Soft delete
        document.soft_delete()

        # Optionally delete file from disk
        if document.file_url and os.path.exists(document.file_url):
            try:
                os.remove(document.file_url)
                logger.info("file_deleted", file_path=document.file_url)
            except Exception as e:
                logger.error("file_deletion_failed", error=str(e), file_path=document.file_url)

        await self.db.commit()

        logger.info("document_deleted", document_id=str(document_id), patient_id=str(patient_id))

        return True
