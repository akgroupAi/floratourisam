"""Favorites / wishlist schemas."""

from datetime import datetime
from typing import Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import BaseSchema
from app.utils.enums import FavoriteEntityType


class FavoriteCreate(BaseModel):
    """Add an item to favorites."""

    entity_type: FavoriteEntityType
    entity_id: UUID
    notes: Optional[str] = Field(default=None, max_length=500)


class FavoriteNotesUpdate(BaseModel):
    """Update the personal note on a saved item."""

    notes: Optional[str] = Field(default=None, max_length=500)


class FavoriteResponse(BaseSchema):
    """A single favorited item, enriched with entity display info."""

    id: UUID
    patient_id: UUID
    entity_type: str
    entity_id: UUID
    notes: Optional[str] = None

    # Enriched from the referenced entity table
    entity_name: Optional[str] = None
    entity_image_url: Optional[str] = None
    entity_subtitle: Optional[str] = None  # e.g. specialization, city, category

    created_at: datetime


class FavoriteCheckResponse(BaseModel):
    """Quick check whether an entity is in the patient's favorites."""

    is_favorited: bool
    favorite_id: Optional[UUID] = None


class FavoriteCountsResponse(BaseModel):
    """Count of favorited items per entity type."""

    total: int
    counts: Dict[str, int]
