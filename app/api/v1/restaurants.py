"""Restaurant endpoints."""

from uuid import UUID
from fastapi import APIRouter, HTTPException, Query
from app.api.deps import DatabaseSession
from app.schemas.common import PaginatedResponse

router = APIRouter()


@router.get("")
async def list_restaurants(db: DatabaseSession, page: int = Query(1), page_size: int = Query(20), city: str = None):
    """List restaurants."""
    return PaginatedResponse.create([], 0, page, page_size)


@router.get("/{restaurant_id}")
async def get_restaurant(restaurant_id: UUID, db: DatabaseSession):
    """Get restaurant by ID."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/{restaurant_id}/menu")
async def get_restaurant_menu(restaurant_id: UUID, db: DatabaseSession):
    """Get restaurant menu."""
    return []
