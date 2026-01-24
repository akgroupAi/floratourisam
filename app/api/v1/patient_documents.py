"""Patient medical documents API endpoints."""

from typing import Annotated, List, Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

from app.api.deps import CurrentUser, DatabaseSession, get_current_patient
from app.models.patient import Patient
from app.schemas.common import MessageResponse
from app.schemas.medical_document import (
    DocumentDetailResponse,
    DocumentListItem,
    DocumentType,
    DocumentUploadResponse,
)
from app.services.document_service import DocumentService

router = APIRouter()


@router.post("/me/documents", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    current_user: CurrentUser,
    patient: Annotated[Patient, Depends(get_current_patient)],
    db: DatabaseSession,
    file: Annotated[UploadFile, File(description="Medical document file (PDF, JPG, PNG, DICOM)")],
    title: Annotated[str, Form(description="Document title")],
    document_type: Annotated[DocumentType, Form(description="Type of medical document")],
    description: Annotated[Optional[str], Form(description="Optional description")] = None,
):
    """
    Upload a medical document.
    
    - **file**: Medical document file (max 10MB)
    - **title**: Document title
    - **document_type**: Type of document (lab_report, prescription, xray, etc.)
    - **description**: Optional description
    
    Supported file types: PDF, JPG, JPEG, PNG, DICOM
    """
    service = DocumentService(db)
    
    return await service.upload_document(
        patient_id=patient.id,
        file=file,
        title=title,
        document_type=document_type.value,
        description=description,
    )


@router.get("/me/documents", response_model=List[DocumentListItem])
async def list_documents(
    current_user: CurrentUser,
    patient: Annotated[Patient, Depends(get_current_patient)],
    db: DatabaseSession,
    document_type: Optional[DocumentType] = None,
):
    """
    List all medical documents for the current patient.
    
    - **document_type**: Optional filter by document type
    """
    service = DocumentService(db)
    
    return await service.get_documents(
        patient_id=patient.id,
        document_type=document_type.value if document_type else None,
    )


@router.get("/me/documents/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: UUID,
    current_user: CurrentUser,
    patient: Annotated[Patient, Depends(get_current_patient)],
    db: DatabaseSession,
):
    """
    Get detailed information about a specific document.
    """
    service = DocumentService(db)
    
    document = await service.get_document_by_id(
        document_id=document_id,
        patient_id=patient.id,
    )
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    return document


@router.get("/me/documents/{document_id}/download")
async def download_document(
    document_id: UUID,
    current_user: CurrentUser,
    patient: Annotated[Patient, Depends(get_current_patient)],
    db: DatabaseSession,
):
    """
    Download a medical document file.
    """
    service = DocumentService(db)
    
    file_path = await service.get_file_path(
        document_id=document_id,
        patient_id=patient.id,
    )
    
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    # Get document details for filename
    document = await service.get_document_by_id(document_id, patient.id)
    filename = document.file_name if document else "document"
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream",
    )


@router.delete("/me/documents/{document_id}", response_model=MessageResponse)
async def delete_document(
    document_id: UUID,
    current_user: CurrentUser,
    patient: Annotated[Patient, Depends(get_current_patient)],
    db: DatabaseSession,
):
    """
    Delete a medical document.
    
    This will soft-delete the document record and remove the file from storage.
    """
    service = DocumentService(db)
    
    success = await service.delete_document(
        document_id=document_id,
        patient_id=patient.id,
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    return MessageResponse(message="Document deleted successfully")
