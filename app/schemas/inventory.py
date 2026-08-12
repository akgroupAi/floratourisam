"""Inventory dashboard, alert, and bulk-operation schemas."""

from datetime import date as _date
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class InventorySummaryResponse(BaseModel):
    """What exists and how much of it is sellable."""

    hotels: int
    hotels_active: int
    room_types: int
    room_units_sellable: int = Field(..., description="Sum of total_rooms on sellable room types")
    apartments: int
    apartments_active: int
    restaurants: int
    menu_items: int
    menu_items_available: int
    blocked_room_nights_ahead: int
    blocked_apartment_nights_ahead: int


class HotelOccupancy(BaseModel):
    """Occupancy for one hotel over the window."""

    hotel_id: str
    name: str
    room_units: int
    capacity_nights: int
    sold_nights: int
    occupancy_percent: float


class OccupancyResponse(BaseModel):
    """Room-night occupancy across a date range."""

    start_date: _date
    end_date: _date
    nights: int
    room_units: int
    capacity_nights: int = Field(..., description="room_units × nights")
    sold_nights: int
    occupancy_percent: float
    by_hotel: List[HotelOccupancy] = []


class InventoryAlert(BaseModel):
    """One actionable inventory problem."""

    severity: str = Field(..., description="high | medium | low")
    type: str
    message: str
    entity_type: str
    entity_id: str


class InventoryAlertsResponse(BaseModel):
    """Problems needing attention, worst first."""

    total: int
    by_severity: Dict[str, int]
    alerts: List[InventoryAlert] = []


class _BulkTargets(BaseModel):
    """Shared targeting for bulk operations."""

    start_date: _date
    end_date: _date = Field(..., description="Exclusive")
    hotel_ids: Optional[List[UUID]] = None
    room_ids: Optional[List[UUID]] = None
    city: Optional[str] = Field(None, description="Partial, case-insensitive match")
    dry_run: bool = Field(
        True, description="Report what would change without writing. Send false to apply."
    )

    @model_validator(mode="after")
    def require_a_target(self):
        if not self.hotel_ids and not self.room_ids and not self.city:
            raise ValueError(
                "Specify hotel_ids, room_ids, or city — refusing to target every room implicitly"
            )
        return self


class BulkPricingRequest(_BulkTargets):
    """Change prices across many rooms. Supply exactly one of the two price fields."""

    percent_change: Optional[float] = Field(
        None, description="e.g. 15 for +15%, -10 for a 10% cut"
    )
    set_price: Optional[float] = Field(None, ge=0, description="Flat price for every match")
    weekdays: Optional[List[int]] = Field(
        None, description="Restrict to these weekdays (0=Monday .. 6=Sunday)"
    )

    @model_validator(mode="after")
    def require_one_price_mode(self):
        if (self.percent_change is None) == (self.set_price is None):
            raise ValueError("Provide exactly one of percent_change or set_price")
        return self


class BulkAvailabilityRequest(_BulkTargets):
    """Block or reopen a date range across many rooms."""

    is_blocked: bool
    notes: Optional[str] = Field(None, max_length=500)


class BulkChange(BaseModel):
    """One room a bulk operation would touch."""

    room_id: str
    room_type: Optional[str] = None
    hotel_name: Optional[str] = None
    current_price: Optional[float] = None
    new_price: Optional[float] = None
    nights: int


class BulkOperationResponse(BaseModel):
    """What a bulk operation did, or would do on a dry run."""

    dry_run: bool
    rooms_matched: int
    nights_affected: int
    is_blocked: Optional[bool] = None
    changes: List[BulkChange] = []
