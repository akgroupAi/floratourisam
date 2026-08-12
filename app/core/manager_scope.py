"""Property scoping for the manager portal.

Every manager endpoint filters through this. A manager must only ever see the hotels,
apartments, and restaurants assigned to them via ``manager_id`` — get this wrong once
and a manager reads another property's bookings and revenue, so the logic lives here in
one tested place rather than being repeated per route.

Admins and super admins are unscoped: `is_admin` is True and the filter helpers return
None, meaning "no restriction".
"""

from typing import List, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.apartment import Apartment
from app.models.hotel import Hotel, Room
from app.models.restaurant import Restaurant
from app.models.user import User
from app.utils.enums import UserRole

ADMIN_ROLES = (UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value)

MANAGER_ROLES = (
    UserRole.HOTEL_MANAGER.value,
    UserRole.APARTMENT_MANAGER.value,
    UserRole.RESTAURANT_MANAGER.value,
)


class ManagerScope:
    """The properties one user is allowed to act on."""

    def __init__(
        self,
        user: User,
        hotel_ids: Optional[List[UUID]] = None,
        apartment_ids: Optional[List[UUID]] = None,
        restaurant_ids: Optional[List[UUID]] = None,
    ):
        self.user = user
        self.hotel_ids = hotel_ids or []
        self.apartment_ids = apartment_ids or []
        self.restaurant_ids = restaurant_ids or []

    @property
    def is_admin(self) -> bool:
        return self.user.role in ADMIN_ROLES

    @property
    def role(self) -> str:
        return self.user.role

    def has_any_property(self) -> bool:
        return bool(self.hotel_ids or self.apartment_ids or self.restaurant_ids)

    # ── Assertions ────────────────────────────────────────────
    # Each raises 403 rather than 404 on a property the caller does not manage.
    # Returning 404 would leak whether an id exists; 403 says only "not yours".

    def assert_hotel(self, hotel_id: UUID) -> None:
        if self.is_admin:
            return
        if hotel_id not in self.hotel_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not manage this hotel",
            )

    def assert_apartment(self, apartment_id: UUID) -> None:
        if self.is_admin:
            return
        if apartment_id not in self.apartment_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not manage this apartment",
            )

    def assert_restaurant(self, restaurant_id: UUID) -> None:
        if self.is_admin:
            return
        if restaurant_id not in self.restaurant_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not manage this restaurant",
            )

    # ── Query filters ─────────────────────────────────────────
    # Return None for admins, meaning "add no restriction".

    def hotel_filter(self, column):
        return None if self.is_admin else column.in_(self.hotel_ids)

    def apartment_filter(self, column):
        return None if self.is_admin else column.in_(self.apartment_ids)

    def restaurant_filter(self, column):
        return None if self.is_admin else column.in_(self.restaurant_ids)

    def room_filter(self, column):
        """Restrict a Room-id column to rooms inside the manager's hotels."""
        if self.is_admin:
            return None
        return column.in_(select(Room.id).where(Room.hotel_id.in_(self.hotel_ids)))

    def booking_filter(self, booking_model):
        """Restrict bookings to anything at a property the caller manages.

        A manager with no properties gets a clause that matches nothing, rather than
        an unfiltered query.
        """
        if self.is_admin:
            return None

        from sqlalchemy import or_

        clauses = []
        if self.hotel_ids:
            clauses.append(
                booking_model.hotel_room_id.in_(
                    select(Room.id).where(Room.hotel_id.in_(self.hotel_ids))
                )
            )
        if self.apartment_ids:
            clauses.append(booking_model.apartment_id.in_(self.apartment_ids))
        if self.restaurant_ids:
            clauses.append(booking_model.restaurant_id.in_(self.restaurant_ids))

        if not clauses:
            return booking_model.id.is_(None)
        return or_(*clauses)


async def resolve_manager_scope(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ManagerScope:
    """Resolve the caller to the properties they may act on.

    Rejects any role that is neither an admin nor a property manager, so a patient or
    doctor never reaches a manager endpoint even if one forgets its own guard.
    """
    role = current_user.role

    if role in ADMIN_ROLES:
        return ManagerScope(current_user)

    if role not in MANAGER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This area is for property managers",
        )

    hotel_ids: List[UUID] = []
    apartment_ids: List[UUID] = []
    restaurant_ids: List[UUID] = []

    if role == UserRole.HOTEL_MANAGER.value:
        hotel_ids = list(
            (
                await db.execute(
                    select(Hotel.id).where(
                        Hotel.manager_id == current_user.id,
                        Hotel.is_deleted == False,
                    )
                )
            )
            .scalars()
            .all()
        )
    elif role == UserRole.APARTMENT_MANAGER.value:
        apartment_ids = list(
            (
                await db.execute(
                    select(Apartment.id).where(
                        Apartment.manager_id == current_user.id,
                        Apartment.is_deleted == False,
                    )
                )
            )
            .scalars()
            .all()
        )
    elif role == UserRole.RESTAURANT_MANAGER.value:
        restaurant_ids = list(
            (
                await db.execute(
                    select(Restaurant.id).where(
                        Restaurant.manager_id == current_user.id,
                        Restaurant.is_deleted == False,
                    )
                )
            )
            .scalars()
            .all()
        )

    return ManagerScope(current_user, hotel_ids, apartment_ids, restaurant_ids)


# Use as: scope: ManagerScopeDep
ManagerScopeDep = Depends(resolve_manager_scope)
