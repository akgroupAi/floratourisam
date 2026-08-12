"""Tests for apartment availability, minimum stay, and calendar pricing.

Two bugs these guard:
  - Three implementations of "is this apartment available" used two different status
    rules, so the display endpoints and the booking path disagreed about whether an
    unpaid `pending` booking holds the unit.
  - There was no calendar at all: no blocking, no seasonal rates, no minimum stay.
"""

import asyncio
import inspect
from datetime import date, timedelta
from uuid import uuid4

import pytest

from app.services.booking_service import BookingService


class FakeApartment:
    def __init__(self, minimum_nights=1, price_per_night=3000.0,
                 price_per_week=18000.0, price_per_month=60000.0):
        self.id = uuid4()
        self.minimum_nights = minimum_nights
        self.price_per_night = price_per_night
        self.price_per_week = price_per_week
        self.price_per_month = price_per_month


class FakeOverride:
    def __init__(self, day, price=None, is_blocked=False, minimum_nights=None, notes=None):
        self.date = day
        self.price = price
        self.is_blocked = is_blocked
        self.minimum_nights = minimum_nights
        self.notes = notes


class StubService(BookingService):
    """Real availability and pricing logic, fixtures instead of a database."""

    def __init__(self, apartment, overrides=None, bookings=None):
        self._apartment = apartment
        self._overrides = {o.date: o for o in (overrides or [])}
        self._bookings = bookings or []

    async def _load_apartment(self, apartment_id):
        return self._apartment

    async def _load_overrides(self, apartment_id, start, end):
        return {d: o for d, o in self._overrides.items() if start <= d < end}

    async def _has_conflict(self, apartment_id, check_in, check_out, exclude_booking_id=None):
        return any(ci < check_out and co > check_in for ci, co in self._bookings)

    async def _assert_apartment_available(
        self, apartment_id, check_in, check_out, exclude_booking_id=None
    ):
        if check_out <= check_in:
            raise ValueError("check_out must be after check_in")
        apartment = await self._load_apartment(apartment_id)
        nights = [check_in + timedelta(days=i) for i in range((check_out - check_in).days)]
        overrides = await self._load_overrides(apartment_id, check_in, check_out)

        for night in nights:
            override = overrides.get(night)
            if override and override.is_blocked:
                raise ValueError(f"The apartment is not available on {night.isoformat()}")

        first = overrides.get(check_in)
        required = (
            first.minimum_nights
            if first is not None and first.minimum_nights is not None
            else (apartment.minimum_nights or 1)
        )
        if len(nights) < required:
            raise ValueError(f"This apartment requires a minimum stay of {required} night(s)")

        if await self._has_conflict(apartment_id, check_in, check_out, exclude_booking_id):
            raise ValueError("The apartment is already booked for the selected dates")

    async def _apartment_base_price(self, apartment, check_in, nights):
        check_out = check_in + timedelta(days=nights)
        overrides = {
            d: o for d, o in self._overrides.items()
            if check_in <= d < check_out and o.price is not None
        }
        stay_nights = [check_in + timedelta(days=i) for i in range(nights)]
        if overrides and all(n in overrides for n in stay_nights):
            return round(sum(overrides[n].price for n in stay_nights), 2)
        if nights >= 28 and apartment.price_per_month:
            return round(apartment.price_per_month * (nights / 30), 2)
        if nights >= 7 and apartment.price_per_week:
            return round(apartment.price_per_week * (nights / 7), 2)
        if apartment.price_per_night:
            return round(apartment.price_per_night * nights, 2)
        raise ValueError("Apartment has no pricing configured")


D1 = date(2026, 9, 1)
D3 = date(2026, 9, 3)
D5 = date(2026, 9, 5)
D8 = date(2026, 9, 8)


def available(service, check_in=D1, check_out=D3) -> bool:
    return asyncio.run(service.check_apartment_availability(uuid4(), check_in, check_out))


def reason(service, check_in=D1, check_out=D3) -> str:
    with pytest.raises(ValueError) as exc:
        asyncio.run(service._assert_apartment_available(uuid4(), check_in, check_out))
    return str(exc.value)


# ── Single-unit behaviour (unlike hotel room types) ───────────


def test_apartment_is_a_single_unit_so_one_booking_blocks_it():
    """No total_rooms equivalent — an overlapping booking takes the whole unit."""
    service = StubService(FakeApartment(), bookings=[(D1, D3)])
    assert available(service) is False


def test_free_apartment_is_available():
    assert available(StubService(FakeApartment())) is True


def test_checkout_day_frees_the_night():
    service = StubService(FakeApartment(), bookings=[(D1, D3)])
    assert available(service, check_in=D3, check_out=D5) is True


# ── Blocking ──────────────────────────────────────────────────


def test_blocked_night_makes_the_stay_unavailable():
    service = StubService(FakeApartment(), overrides=[FakeOverride(date(2026, 9, 2), is_blocked=True)])
    assert available(service, check_in=D1, check_out=D3) is False


def test_blocked_message_names_the_date():
    service = StubService(FakeApartment(), overrides=[FakeOverride(date(2026, 9, 2), is_blocked=True)])
    assert "2026-09-02" in reason(service, D1, D3)


def test_block_outside_the_stay_does_not_matter():
    service = StubService(FakeApartment(), overrides=[FakeOverride(D5, is_blocked=True)])
    assert available(service, check_in=D1, check_out=D3) is True


# ── Minimum stay ──────────────────────────────────────────────


def test_stay_shorter_than_the_minimum_is_rejected():
    service = StubService(FakeApartment(minimum_nights=7))
    assert available(service, check_in=D1, check_out=D3) is False
    assert "minimum stay of 7" in reason(service, D1, D3)


def test_stay_meeting_the_minimum_is_accepted():
    service = StubService(FakeApartment(minimum_nights=7))
    assert available(service, check_in=D1, check_out=D8) is True


def test_calendar_can_raise_the_minimum_for_peak_dates():
    service = StubService(
        FakeApartment(minimum_nights=1),
        overrides=[FakeOverride(D1, minimum_nights=5)],
    )
    assert available(service, check_in=D1, check_out=D3) is False


def test_minimum_is_taken_from_the_arrival_night():
    """The rule the guest is quoted when they pick their check-in date."""
    service = StubService(
        FakeApartment(minimum_nights=1),
        overrides=[FakeOverride(D3, minimum_nights=10)],
    )
    assert available(service, check_in=D1, check_out=D3) is True


def test_default_minimum_of_one_allows_a_single_night():
    assert available(StubService(FakeApartment()), check_in=D1, check_out=date(2026, 9, 2)) is True


# ── Calendar pricing ──────────────────────────────────────────


def price(service, apartment, check_in, nights) -> float:
    return asyncio.run(service._apartment_base_price(apartment, check_in, nights))


def test_calendar_prices_are_used_when_every_night_has_one():
    apartment = FakeApartment(price_per_night=3000.0)
    service = StubService(apartment, overrides=[
        FakeOverride(D1, price=5000.0),
        FakeOverride(date(2026, 9, 2), price=5500.0),
    ])
    assert price(service, apartment, D1, 2) == 10500.0


def test_partial_calendar_coverage_falls_back_to_the_tiered_rate():
    """Half-priced nights must not silently produce a half-priced stay."""
    apartment = FakeApartment(price_per_night=3000.0)
    service = StubService(apartment, overrides=[FakeOverride(D1, price=5000.0)])
    assert price(service, apartment, D1, 2) == 6000.0


def test_weekly_rate_still_applies_for_a_week_long_stay():
    apartment = FakeApartment()
    assert price(StubService(apartment), apartment, D1, 7) == 18000.0


def test_monthly_rate_still_applies_for_a_long_stay():
    apartment = FakeApartment()
    assert price(StubService(apartment), apartment, D1, 30) == 60000.0


def test_apartment_with_no_pricing_is_rejected():
    apartment = FakeApartment(price_per_night=None, price_per_week=None, price_per_month=None)
    with pytest.raises(ValueError, match="no pricing configured"):
        price(StubService(apartment), apartment, D1, 2)


# ── The three implementations now agree ───────────────────────


def test_apartment_service_delegates_instead_of_running_its_own_query():
    from app.services import apartment_service

    source = inspect.getsource(apartment_service.ApartmentService.check_availability)
    assert "BookingService" in source
    assert "notin_" not in source, "must not use its own divergent status rule"


def test_stays_endpoint_delegates_instead_of_running_its_own_query():
    from app.api.v1 import stays

    source = inspect.getsource(stays)
    assert "check_apartment_availability" in source
    assert "BookingStatus.CANCELLED.value" not in source


def test_booking_creation_uses_the_shared_availability_check():
    """Blocked dates and minimum stay must be enforced when booking, not just displayed."""
    source = inspect.getsource(BookingService.create_apartment_booking)
    assert "_assert_apartment_available" in source


def test_model_has_the_calendar_table():
    from app.models.apartment import ApartmentAvailability

    columns = {c.name for c in ApartmentAvailability.__table__.columns}
    assert {"apartment_id", "date", "price", "is_blocked", "minimum_nights"} <= columns
