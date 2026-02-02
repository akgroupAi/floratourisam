"""Hotel endpoints."""

from uuid import UUID
from fastapi import APIRouter, HTTPException, Query
from app.api.deps import DatabaseSession
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.hotel import HotelResponse, RoomResponse
from app.services.hotel_service import HotelService

router = APIRouter()


@router.get("", response_model=PaginatedResponse[HotelResponse])
async def list_hotels(db: DatabaseSession, page: int = Query(1), page_size: int = Query(20), city: str = None):
    """List hotels with filters."""
    service = HotelService(db)
    hotels, total = await service.get_list(PaginationParams(page=page, page_size=page_size), city)
    return PaginatedResponse.create(hotels, total, page, page_size)


@router.get("/{hotel_id}", response_model=HotelResponse)
async def get_hotel(hotel_id: UUID, db: DatabaseSession):
    """Get hotel by ID."""
    service = HotelService(db)
    hotel = await service.get_by_id(hotel_id)
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    return hotel


@router.get("/{hotel_id}/rooms", response_model=list[RoomResponse])
async def get_hotel_rooms(hotel_id: UUID, db: DatabaseSession):
    """Get hotel rooms."""
    service = HotelService(db)
    return await service.get_rooms(hotel_id)


@router.get("/{hotel_id}/rooms/{room_id}/availability")
async def check_room_availability(hotel_id: UUID, room_id: UUID, check_in: str, check_out: str, db: DatabaseSession):
    """Check room availability for dates."""
    service = HotelService(db)
    available = await service.check_availability(room_id, check_in, check_out)
    return {"available": available}
