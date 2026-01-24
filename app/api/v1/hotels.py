"""Hotel endpoints."""

from uuid import UUID
from fastapi import APIRouter, HTTPException, Query
from app.api.deps import DatabaseSession
from app.schemas.common import PaginatedResponse, PaginationParams

router = APIRouter()


@router.get("")
async def list_hotels(db: DatabaseSession, page: int = Query(1), page_size: int = Query(20), city: str = None):
    """List hotels with filters."""
    return PaginatedResponse.create([], 0, page, page_size)


@router.get("/{hotel_id}")
async def get_hotel(hotel_id: UUID, db: DatabaseSession):
    """Get hotel by ID."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/{hotel_id}/rooms")
async def get_hotel_rooms(hotel_id: UUID, db: DatabaseSession):
    """Get hotel rooms."""
    return []


@router.get("/{hotel_id}/rooms/{room_id}/availability")
async def check_room_availability(hotel_id: UUID, room_id: UUID, check_in: str, check_out: str, db: DatabaseSession):
    """Check room availability for dates."""
    return {"available": True, "price_per_night": 100}
