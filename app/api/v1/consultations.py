"""Consultation endpoints."""

from uuid import UUID
from fastapi import APIRouter, HTTPException, Query
from app.api.deps import CurrentUser, DatabaseSession
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.consultation import ConsultationCreate, ConsultationListResponse, ConsultationResponse

router = APIRouter()


@router.get("", response_model=PaginatedResponse[ConsultationListResponse])
async def list_consultations(current_user: CurrentUser, db: DatabaseSession, page: int = Query(1, ge=1), page_size: int = Query(20)):
    """List user's consultations."""
    # Simplified - would use ConsultationService
    return PaginatedResponse.create([], 0, page, page_size)


@router.post("", response_model=ConsultationResponse)
async def create_consultation(data: ConsultationCreate, current_user: CurrentUser, db: DatabaseSession):
    """Create a new consultation booking."""
    # Would use ConsultationService
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/{consultation_id}", response_model=ConsultationResponse)
async def get_consultation(consultation_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Get consultation by ID."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/{consultation_id}/cancel")
async def cancel_consultation(consultation_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Cancel a consultation."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/{consultation_id}/join")
async def join_consultation(consultation_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Get session details to join consultation."""
    raise HTTPException(status_code=501, detail="Not implemented")
