"""Tests for room-type availability counting and the rate/availability calendar.

The bug these guard: a Room row is a room *type* with `total_rooms` units, but the old
conflict check rejected on any overlapping booking, so a hotel with ten deluxe rooms
could sell exactly one per night.
"""

import asyncio
from datetime import date, timedelta
from uuid import uuid4

import pytest

from app.services.booking_service import BookingService


class FakeRoom:
    def __init__(self, total_rooms=10, price_per_night=5000.0):
        self.id = uuid4()
        self.total_rooms = total_rooms
        self.price_per_night = price_per_night


class FakeOverride:
    def __init__(self, day, available_rooms=None, price=None, is_blocked=False, notes=None):
        self.date = day
        self.available_rooms = available_rooms
        self.price = price
        self.is_blocked = is_blocked
        self.notes = notes


class StubService(BookingService):
    """BookingService with the two DB-touching helpers replaced by fixtures.

    Everything under test — the per-night capacity maths and the assertion — is real.
    """

    def __init__(self, room, overrides=None, bookings=None):
        self._room = room
        self._overrides = {o.date: o for o in (overrides or [])}
        self._bookings = bookings or []

    async def _room_night_capacity(self, room_id, check_in, check_out):
        nights = [
            check_in + timedelta(days=i) for i in range((check_out - check_in).days)
        ]
        capacity, blocked = {}, {}
        for night in nights:
            override = self._overrides.get(night)
            blocked[night] = bool(override and override.is_blocked)
            capacity[night] = (
                override.available_rooms
                if override is not None and override.available_rooms is not None
                else self._room.total_rooms
            )
        return nights, capacity, blocked

    async def _room_night_occupancy(self, room_id, nights, exclude_booking_id=None):
        booked = {night: 0 for night in nights}
        for check_in, check_out in self._bookings:
            for night in nights:
                if check_in <= night < check_out:
                    booked[night] += 1
        return booked


D1 = date(2026, 9, 1)
D2 = date(2026, 9, 2)
D3 = date(2026, 9, 3)
D4 = date(2026, 9, 4)


def assert_available(service, check_in=D1, check_out=D3, quantity=1):
    asyncio.run(
        service._assert_room_available(uuid4(), check_in, check_out, quantity=quantity)
    )


def assert_unavailable(service, check_in=D1, check_out=D3, quantity=1, match=None):
    with pytest.raises(ValueError, match=match) as exc:
        assert_available(service, check_in, check_out, quantity)
    return str(exc.value)


# ── The core defect ───────────────────────────────────────────


def test_second_booking_of_a_ten_room_type_is_allowed():
    """The whole point: one booking must not block the other nine units."""
    service = StubService(FakeRoom(total_rooms=10), bookings=[(D1, D3)])
    assert_available(service)


def test_nine_bookings_still_leave_one_room():
    service = StubService(FakeRoom(total_rooms=10), bookings=[(D1, D3)] * 9)
    assert_available(service)


def test_tenth_booking_exhausts_a_ten_room_type():
    service = StubService(FakeRoom(total_rooms=10), bookings=[(D1, D3)] * 10)
    assert_unavailable(service, match="0 room")


def test_single_unit_room_type_still_blocks_on_one_booking():
    """Properties with one of a type must keep the old behaviour."""
    service = StubService(FakeRoom(total_rooms=1), bookings=[(D1, D3)])
    assert_unavailable(service)


def test_room_with_no_units_is_never_available():
    service = StubService(FakeRoom(total_rooms=0))
    assert_unavailable(service)


# ── Per-night rather than per-range ───────────────────────────


def test_only_the_exhausted_night_blocks_the_stay():
    """Capacity is per night, so a full Tuesday blocks a Mon-Wed stay."""
    service = StubService(
        FakeRoom(total_rooms=2),
        bookings=[(D2, D3), (D2, D3)],  # both units taken on the 2nd only
    )
    assert_unavailable(service, check_in=D1, check_out=D4, match="2026-09-02")


def test_a_stay_around_a_full_night_is_allowed():
    service = StubService(FakeRoom(total_rooms=2), bookings=[(D3, D4), (D3, D4)])
    assert_available(service, check_in=D1, check_out=D3)


def test_checkout_day_does_not_consume_a_night():
    """A booking ending on the 3rd frees the 3rd for someone else."""
    service = StubService(FakeRoom(total_rooms=1), bookings=[(D1, D3)])
    assert_available(service, check_in=D3, check_out=D4)


# ── Calendar overrides ────────────────────────────────────────


def test_calendar_override_can_reduce_capacity_below_total_rooms():
    service = StubService(
        FakeRoom(total_rooms=10),
        overrides=[FakeOverride(D1, available_rooms=2)],
        bookings=[(D1, D3)] * 2,
    )
    assert_unavailable(service, match="2026-09-01")


def test_calendar_override_can_raise_capacity_above_total_rooms():
    service = StubService(
        FakeRoom(total_rooms=1),
        overrides=[FakeOverride(D1, available_rooms=5), FakeOverride(D2, available_rooms=5)],
        bookings=[(D1, D3)] * 3,
    )
    assert_available(service)


def test_blocked_night_rejects_even_with_capacity_free():
    service = StubService(
        FakeRoom(total_rooms=10), overrides=[FakeOverride(D2, is_blocked=True)]
    )
    message = assert_unavailable(service, check_in=D1, check_out=D4)
    assert "2026-09-02" in message


def test_nights_without_an_override_fall_back_to_total_rooms():
    service = StubService(
        FakeRoom(total_rooms=3),
        overrides=[FakeOverride(D1, available_rooms=1)],
        bookings=[(D2, D3)] * 2,
    )
    assert_available(service, check_in=D2, check_out=D3)


# ── Quantity ──────────────────────────────────────────────────


def test_requesting_more_units_than_remain_is_rejected():
    service = StubService(FakeRoom(total_rooms=5), bookings=[(D1, D3)] * 3)
    assert_unavailable(service, quantity=3, match="2 room")


def test_requesting_exactly_the_remaining_units_is_allowed():
    service = StubService(FakeRoom(total_rooms=5), bookings=[(D1, D3)] * 3)
    assert_available(service, quantity=2)


# ── Guards ────────────────────────────────────────────────────


def test_zero_night_range_is_rejected():
    service = StubService(FakeRoom())
    with pytest.raises(ValueError, match="check_out must be after check_in"):
        asyncio.run(service._assert_room_available(uuid4(), D1, D1))


def test_error_message_names_the_night_that_failed():
    """An admin needs to know which date is the problem, not just that one is."""
    service = StubService(FakeRoom(total_rooms=1), bookings=[(D2, D3)])
    message = assert_unavailable(service, check_in=D1, check_out=D4)
    assert "2026-09-02" in message


# ── The stub that always said "available" ─────────────────────


def test_hotel_service_availability_no_longer_returns_true_unconditionally():
    import inspect

    from app.services import hotel_service

    source = inspect.getsource(hotel_service.HotelService.check_availability)
    assert "Placeholder" not in source
    assert "BookingService" in source, "must delegate to the real availability check"
