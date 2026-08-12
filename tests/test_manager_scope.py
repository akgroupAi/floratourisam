"""Tests for manager property scoping.

This is the security boundary of the manager portal: every manager endpoint filters
through it. A gap here means one manager reads another property's bookings and revenue,
so it is tested on its own rather than only through the endpoints.
"""

import asyncio
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

from app.core.manager_scope import ManagerScope, resolve_manager_scope
from app.models.booking import Booking
from app.utils.enums import UserRole


class FakeUser:
    def __init__(self, role):
        self.id = uuid4()
        self.role = role


HOTEL_A, HOTEL_B = uuid4(), uuid4()
APT_A, APT_B = uuid4(), uuid4()
REST_A, REST_B = uuid4(), uuid4()


def hotel_manager_scope():
    return ManagerScope(FakeUser(UserRole.HOTEL_MANAGER.value), hotel_ids=[HOTEL_A])


def admin_scope():
    return ManagerScope(FakeUser(UserRole.ADMIN.value))


# ── Admins are unscoped ───────────────────────────────────────


def test_admin_is_flagged_as_admin():
    assert admin_scope().is_admin is True


def test_super_admin_is_flagged_as_admin():
    assert ManagerScope(FakeUser(UserRole.SUPER_ADMIN.value)).is_admin is True


def test_admin_may_act_on_any_property():
    scope = admin_scope()
    scope.assert_hotel(uuid4())
    scope.assert_apartment(uuid4())
    scope.assert_restaurant(uuid4())


def test_admin_filters_add_no_restriction():
    """None means 'no WHERE clause', not 'match nothing'."""
    scope = admin_scope()
    assert scope.hotel_filter(Booking.id) is None
    assert scope.apartment_filter(Booking.id) is None
    assert scope.restaurant_filter(Booking.id) is None
    assert scope.booking_filter(Booking) is None
    assert scope.room_filter(Booking.hotel_room_id) is None


# ── Managers are scoped to their own properties ───────────────


def test_manager_may_act_on_an_assigned_hotel():
    hotel_manager_scope().assert_hotel(HOTEL_A)


def test_manager_is_refused_another_hotel():
    with pytest.raises(HTTPException) as exc:
        hotel_manager_scope().assert_hotel(HOTEL_B)
    assert exc.value.status_code == 403


def test_refusal_is_403_not_404():
    """404 would leak whether the id exists; 403 says only 'not yours'."""
    with pytest.raises(HTTPException) as exc:
        hotel_manager_scope().assert_hotel(HOTEL_B)
    assert exc.value.status_code == 403
    assert "do not manage" in exc.value.detail


def test_hotel_manager_cannot_reach_an_apartment():
    """Roles do not bleed: a hotel manager has no apartment ids at all."""
    with pytest.raises(HTTPException):
        hotel_manager_scope().assert_apartment(APT_A)


def test_hotel_manager_cannot_reach_a_restaurant():
    with pytest.raises(HTTPException):
        hotel_manager_scope().assert_restaurant(REST_A)


def test_manager_with_no_properties_is_refused_everything():
    scope = ManagerScope(FakeUser(UserRole.HOTEL_MANAGER.value))
    assert scope.has_any_property() is False
    with pytest.raises(HTTPException):
        scope.assert_hotel(HOTEL_A)


# ── Query filters produce the right SQL ───────────────────────


def compile_clause(clause) -> str:
    return str(
        clause.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    )


def test_hotel_filter_restricts_to_assigned_ids():
    sql = compile_clause(hotel_manager_scope().hotel_filter(Booking.id))
    assert str(HOTEL_A) in sql
    assert str(HOTEL_B) not in sql


def test_room_filter_reaches_rooms_through_the_hotel():
    sql = compile_clause(hotel_manager_scope().room_filter(Booking.hotel_room_id))
    assert "FROM rooms" in sql
    assert str(HOTEL_A) in sql


def test_booking_filter_for_a_hotel_manager_covers_only_their_rooms():
    sql = compile_clause(hotel_manager_scope().booking_filter(Booking))
    assert "bookings.hotel_room_id IN" in sql
    assert "apartment_id" not in sql
    assert "restaurant_id" not in sql


def test_booking_filter_for_an_apartment_manager_covers_only_apartments():
    scope = ManagerScope(FakeUser(UserRole.APARTMENT_MANAGER.value), apartment_ids=[APT_A])
    sql = compile_clause(scope.booking_filter(Booking))
    assert "bookings.apartment_id IN" in sql
    assert "hotel_room_id" not in sql


def test_booking_filter_with_no_properties_matches_nothing():
    """The dangerous failure mode: an empty scope must not become an unfiltered query."""
    scope = ManagerScope(FakeUser(UserRole.HOTEL_MANAGER.value))
    sql = compile_clause(scope.booking_filter(Booking))
    assert "IS NULL" in sql


def test_manager_of_several_hotels_sees_all_of_them():
    scope = ManagerScope(
        FakeUser(UserRole.HOTEL_MANAGER.value), hotel_ids=[HOTEL_A, HOTEL_B]
    )
    scope.assert_hotel(HOTEL_A)
    scope.assert_hotel(HOTEL_B)
    sql = compile_clause(scope.hotel_filter(Booking.id))
    assert str(HOTEL_A) in sql and str(HOTEL_B) in sql


# ── Non-manager roles are rejected at the door ────────────────


class FakeDB:
    async def execute(self, stmt):
        raise AssertionError("must reject the role before querying")


@pytest.mark.parametrize("role", ["patient", "doctor", "unknown_role"])
def test_non_manager_roles_are_refused(role):
    with pytest.raises(HTTPException) as exc:
        asyncio.run(resolve_manager_scope(FakeUser(role), FakeDB()))
    assert exc.value.status_code == 403
    assert "property managers" in exc.value.detail


def test_admin_resolves_without_touching_the_database():
    scope = asyncio.run(resolve_manager_scope(FakeUser(UserRole.ADMIN.value), FakeDB()))
    assert scope.is_admin is True
