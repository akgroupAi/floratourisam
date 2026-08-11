"""Tests for the platform fee charged on top of payable bookings."""

import pytest

from app.core.config import settings
from app.utils.pricing import (
    platform_fee_for,
    platform_fee_rate,
    price_with_platform_fee,
)


def test_default_rate_is_five_percent():
    assert settings.PLATFORM_FEE_PERCENT == 5.0
    assert platform_fee_rate() == 0.05


def test_fee_is_added_on_top_of_the_subtotal():
    subtotal, fee, total = price_with_platform_fee(10000.0)
    assert subtotal == 10000.0
    assert fee == 500.0
    assert total == 10500.0


def test_total_always_equals_subtotal_plus_fee():
    for base in (1.0, 99.99, 750.0, 12345.67, 1_000_000.0):
        subtotal, fee, total = price_with_platform_fee(base)
        assert round(subtotal + fee, 2) == total


def test_fee_applies_after_taxes():
    subtotal, fee, total = price_with_platform_fee(10000.0, taxes=1000.0)
    assert subtotal == 11000.0
    assert fee == 550.0
    assert total == 11550.0


def test_discount_reduces_the_fee():
    """A discount should lower the fee too, not just the base."""
    subtotal, fee, total = price_with_platform_fee(10000.0, discount=2000.0)
    assert subtotal == 8000.0
    assert fee == 400.0
    assert total == 8400.0


def test_free_booking_attracts_no_fee():
    """A table reservation with no pre-order must not be charged a fee on nothing."""
    assert price_with_platform_fee(0.0) == (0.0, 0.0, 0.0)


def test_negative_subtotal_never_produces_a_charge():
    subtotal, fee, total = price_with_platform_fee(100.0, discount=500.0)
    assert fee == 0.0
    assert total == 0.0
    assert subtotal == 0.0


def test_fee_is_rounded_to_two_decimals():
    _, fee, total = price_with_platform_fee(333.33)
    assert fee == 16.67
    assert total == 350.0


def test_fee_for_helper_matches_the_full_calculation():
    assert platform_fee_for(10000.0) == price_with_platform_fee(10000.0)[1]


def test_zero_percent_disables_the_fee(monkeypatch):
    """Setting the rate to 0 must switch the charge off cleanly."""
    monkeypatch.setattr(settings, "PLATFORM_FEE_PERCENT", 0.0)
    subtotal, fee, total = price_with_platform_fee(10000.0)
    assert fee == 0.0
    assert total == subtotal == 10000.0


def test_rate_is_configurable(monkeypatch):
    monkeypatch.setattr(settings, "PLATFORM_FEE_PERCENT", 2.5)
    _, fee, total = price_with_platform_fee(10000.0)
    assert fee == 250.0
    assert total == 10250.0


def test_negative_rate_is_treated_as_zero(monkeypatch):
    """A misconfigured negative rate must never discount a booking."""
    monkeypatch.setattr(settings, "PLATFORM_FEE_PERCENT", -5.0)
    _, fee, total = price_with_platform_fee(10000.0)
    assert fee == 0.0
    assert total == 10000.0


# ── Every booking path applies the fee ────────────────────────


def test_all_booking_creators_use_the_shared_helper():
    """Guards against a new booking type silently skipping the fee.

    Each of these modules creates a Booking with a price, so each must route through
    price_with_platform_fee rather than computing a total itself.
    """
    import inspect

    from app.api.v1 import bookings as bookings_api
    from app.api.v1 import restaurants as restaurants_api
    from app.services import (
        appointment_service,
        booking_service,
        consultation_service,
        package_service,
    )

    for module in (
        booking_service,
        package_service,
        consultation_service,
        appointment_service,
        bookings_api,
        restaurants_api,
    ):
        source = inspect.getsource(module)
        assert "price_with_platform_fee" in source, (
            f"{module.__name__} creates priced bookings but does not apply the "
            f"platform fee"
        )


def test_no_booking_total_is_computed_by_hand():
    """total_price must come from the helper, not from base + taxes inline."""
    import inspect

    from app.services import booking_service, package_service

    for module in (booking_service, package_service):
        source = inspect.getsource(module)
        assert "total_price=round(base_price + taxes, 2)" not in source
        assert "total_price=effective_price + taxes" not in source


def test_razorpay_reads_platform_fee_from_the_booking():
    """The gateway record must not re-derive the fee and double-count it."""
    import inspect

    from app.services import razorpay_service

    source = inspect.getsource(razorpay_service)
    assert "booking.platform_fee" in source
    assert "amount * 0.01" not in source


def test_booking_model_has_platform_fee_column():
    from app.models.booking import Booking

    column = Booking.__table__.columns.get("platform_fee")
    assert column is not None
    assert column.nullable is False
