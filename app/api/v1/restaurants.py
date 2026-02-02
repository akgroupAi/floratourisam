"""Restaurant endpoints."""

from uuid import UUID
from fastapi import APIRouter, HTTPException, Query
from app.api.deps import DatabaseSession
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.restaurant import RestaurantResponse, MenuItemResponse
from app.services.restaurant_service import RestaurantService

router = APIRouter()


@router.get("", response_model=PaginatedResponse[RestaurantResponse])
async def list_restaurants(db: DatabaseSession, page: int = Query(1), page_size: int = Query(20), city: str = None):
    """List restaurants."""
    service = RestaurantService(db)
    restaurants, total = await service.get_list(PaginationParams(page=page, page_size=page_size), city)
    return PaginatedResponse.create(restaurants, total, page, page_size)


@router.get("/{restaurant_id}", response_model=RestaurantResponse)
async def get_restaurant(restaurant_id: UUID, db: DatabaseSession):
    """Get restaurant by ID."""
    service = RestaurantService(db)
    restaurant = await service.get_by_id(restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    return restaurant


@router.get("/{restaurant_id}/menu", response_model=list[MenuItemResponse])
async def get_restaurant_menu(restaurant_id: UUID, db: DatabaseSession):
    """Get restaurant menu."""
    service = RestaurantService(db)
    return await service.get_menu(restaurant_id)
