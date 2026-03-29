"""Patient favorites / wishlist endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DatabaseSession, RequirePatient
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.favorite import (
    FavoriteCheckResponse,
    FavoriteCountsResponse,
    FavoriteCreate,
    FavoriteNotesUpdate,
    FavoriteResponse,
)
from app.services.favorite_service import FavoriteService
from app.services.patient_service import PatientService
from app.utils.enums import FavoriteEntityType

router = APIRouter()


async def _get_patient(current_user, db):
    """Resolve the patient profile for the current user."""
    service = PatientService(db)
    return await service.get_or_create(current_user.id)


# ---------------------------------------------------------------------------
# List & counts
# ---------------------------------------------------------------------------

@router.get("/counts", response_model=FavoriteCountsResponse)
async def get_favorite_counts(
    current_user: CurrentUser,
    db: DatabaseSession,
    _: None = RequirePatient,
):
    """Return count of saved items per entity type."""
    patient = await _get_patient(current_user, db)
    service = FavoriteService(db)
    return await service.get_counts(patient.id)


@router.get("", response_model=PaginatedResponse[FavoriteResponse])
async def list_favorites(
    current_user: CurrentUser,
    db: DatabaseSession,
    _: None = RequirePatient,
    entity_type: Optional[FavoriteEntityType] = Query(default=None, description="Filter by entity type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List the current patient's saved items, enriched with entity details."""
    patient = await _get_patient(current_user, db)
    service = FavoriteService(db)
    items, total = await service.get_list(
        patient_id=patient.id,
        pagination=PaginationParams(page=page, page_size=page_size),
        entity_type=entity_type,
    )
    return PaginatedResponse.create(items, total, page, page_size)


# ---------------------------------------------------------------------------
# Check (before adding, to show filled/empty heart icon)
# ---------------------------------------------------------------------------

@router.get("/check/{entity_type}/{entity_id}", response_model=FavoriteCheckResponse)
async def check_favorite(
    entity_type: FavoriteEntityType,
    entity_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
    _: None = RequirePatient,
):
    """Check whether a specific entity is in the patient's favorites."""
    patient = await _get_patient(current_user, db)
    service = FavoriteService(db)
    is_fav, fav_id = await service.is_favorited(patient.id, entity_type, entity_id)
    return FavoriteCheckResponse(is_favorited=is_fav, favorite_id=fav_id)


# ---------------------------------------------------------------------------
# Add
# ---------------------------------------------------------------------------

@router.post("", response_model=FavoriteResponse, status_code=status.HTTP_201_CREATED)
async def add_favorite(
    data: FavoriteCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
    _: None = RequirePatient,
):
    """Save an entity to the patient's favorites."""
    patient = await _get_patient(current_user, db)
    service = FavoriteService(db)
    try:
        return await service.add(patient.id, data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


# ---------------------------------------------------------------------------
# Update notes
# ---------------------------------------------------------------------------

@router.patch("/{entity_type}/{entity_id}", response_model=FavoriteResponse)
async def update_favorite_notes(
    entity_type: FavoriteEntityType,
    entity_id: UUID,
    data: FavoriteNotesUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
    _: None = RequirePatient,
):
    """Update the personal note on a saved item."""
    patient = await _get_patient(current_user, db)
    service = FavoriteService(db)
    fav = await service.find(patient.id, entity_type, entity_id)
    if not fav:
        raise HTTPException(status_code=404, detail="Favorite not found")
    return await service.update_notes(fav, data)


# ---------------------------------------------------------------------------
# Remove
# ---------------------------------------------------------------------------

@router.delete("/{entity_type}/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(
    entity_type: FavoriteEntityType,
    entity_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
    _: None = RequirePatient,
):
    """Remove an entity from the patient's favorites."""
    patient = await _get_patient(current_user, db)
    service = FavoriteService(db)
    fav = await service.find(patient.id, entity_type, entity_id)
    if not fav:
        raise HTTPException(status_code=404, detail="Favorite not found")
    await service.remove(fav)
