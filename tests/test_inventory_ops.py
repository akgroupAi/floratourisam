"""Tests for menu daily stock, inventory bulk operations, and their guards."""

import asyncio
from datetime import date, timedelta
from uuid import uuid4

import pytest

from app.schemas.inventory import BulkAvailabilityRequest, BulkPricingRequest
from app.services.inventory_service import InventoryService
from app.services.manager_service import ManagerService


class FakeMenuItem:
    def __init__(self, daily_quantity=None, sold_today=0, stock_date=None):
        self.id = uuid4()
        self.daily_quantity = daily_quantity
        self.sold_today = sold_today
        self.stock_date = stock_date


TODAY = date(2026, 8, 12)
YESTERDAY = TODAY - timedelta(days=1)


# ── Menu daily stock ──────────────────────────────────────────


def test_item_without_a_quantity_is_unlimited():
    assert ManagerService.remaining_stock(FakeMenuItem(), TODAY) is None
    assert ManagerService.is_sold_out(FakeMenuItem(), TODAY) is False


def test_remaining_counts_down_from_the_daily_quantity():
    item = FakeMenuItem(daily_quantity=20, sold_today=8, stock_date=TODAY)
    assert ManagerService.remaining_stock(item, TODAY) == 12


def test_item_is_sold_out_when_the_quantity_is_reached():
    item = FakeMenuItem(daily_quantity=20, sold_today=20, stock_date=TODAY)
    assert ManagerService.remaining_stock(item, TODAY) == 0
    assert ManagerService.is_sold_out(item, TODAY) is True


def test_overselling_never_reports_negative_stock():
    item = FakeMenuItem(daily_quantity=20, sold_today=25, stock_date=TODAY)
    assert ManagerService.remaining_stock(item, TODAY) == 0


def test_yesterdays_sales_do_not_count_against_today():
    """The date comparison is the nightly reset — no scheduled job needed."""
    item = FakeMenuItem(daily_quantity=20, sold_today=20, stock_date=YESTERDAY)
    assert ManagerService.remaining_stock(item, TODAY) == 20
    assert ManagerService.is_sold_out(item, TODAY) is False


def test_a_never_stocked_item_starts_full():
    item = FakeMenuItem(daily_quantity=10, sold_today=0, stock_date=None)
    assert ManagerService.remaining_stock(item, TODAY) == 10


def test_zero_quantity_means_sold_out_not_unlimited():
    """0 and None must not be confused — one is 'none left', the other 'no limit'."""
    item = FakeMenuItem(daily_quantity=0, sold_today=0, stock_date=TODAY)
    assert ManagerService.remaining_stock(item, TODAY) == 0
    assert ManagerService.is_sold_out(item, TODAY) is True


# ── Bulk operation guards ─────────────────────────────────────


def test_bulk_pricing_requires_a_target():
    """Refusing an untargeted change is the point — it would hit every room."""
    with pytest.raises(ValueError, match="refusing to target every room"):
        BulkPricingRequest(
            start_date=TODAY, end_date=TODAY + timedelta(days=5), percent_change=10
        )


def test_bulk_pricing_requires_exactly_one_price_mode():
    with pytest.raises(ValueError, match="exactly one"):
        BulkPricingRequest(
            start_date=TODAY, end_date=TODAY + timedelta(days=5),
            city="Ahmedabad", percent_change=10, set_price=5000,
        )


def test_bulk_pricing_rejects_neither_price_mode():
    with pytest.raises(ValueError, match="exactly one"):
        BulkPricingRequest(
            start_date=TODAY, end_date=TODAY + timedelta(days=5), city="Ahmedabad"
        )


def test_bulk_pricing_defaults_to_a_dry_run():
    """A bulk price change must never apply because someone forgot a flag."""
    request = BulkPricingRequest(
        start_date=TODAY, end_date=TODAY + timedelta(days=5),
        city="Ahmedabad", percent_change=10,
    )
    assert request.dry_run is True


def test_bulk_availability_defaults_to_a_dry_run():
    request = BulkAvailabilityRequest(
        start_date=TODAY, end_date=TODAY + timedelta(days=5),
        city="Ahmedabad", is_blocked=True,
    )
    assert request.dry_run is True


def test_bulk_availability_requires_a_target():
    with pytest.raises(ValueError, match="refusing to target every room"):
        BulkAvailabilityRequest(
            start_date=TODAY, end_date=TODAY + timedelta(days=5), is_blocked=True
        )


def test_targeting_by_city_is_accepted():
    request = BulkPricingRequest(
        start_date=TODAY, end_date=TODAY + timedelta(days=5),
        city="Ahmedabad", percent_change=15, dry_run=False,
    )
    assert request.city == "Ahmedabad"
    assert request.dry_run is False


def test_targeting_by_explicit_room_ids_is_accepted():
    room_id = uuid4()
    request = BulkPricingRequest(
        start_date=TODAY, end_date=TODAY + timedelta(days=5),
        room_ids=[room_id], set_price=5000,
    )
    assert request.room_ids == [room_id]


# ── Bulk pricing service guards ───────────────────────────────


class NoRowsDB:
    async def execute(self, stmt):
        return _Empty()

    async def commit(self):
        pass


class _Empty:
    def all(self):
        return []

    def scalars(self):
        return self

    def scalar_one_or_none(self):
        return None


def run_bulk(**kwargs):
    service = InventoryService(NoRowsDB())
    return asyncio.run(
        service.bulk_room_pricing(
            start=TODAY, end=TODAY + timedelta(days=5), updated_by=uuid4(), **kwargs
        )
    )


def test_service_rejects_an_inverted_date_range():
    service = InventoryService(NoRowsDB())
    with pytest.raises(ValueError, match="end date must be after"):
        asyncio.run(
            service.bulk_room_pricing(
                start=TODAY, end=TODAY, updated_by=uuid4(), percent_change=10
            )
        )


def test_service_rejects_a_discount_below_minus_one_hundred_percent():
    """-150% would produce a negative price."""
    with pytest.raises(ValueError, match="below zero"):
        run_bulk(percent_change=-150)


def test_service_rejects_a_negative_flat_price():
    with pytest.raises(ValueError, match="cannot be negative"):
        run_bulk(set_price=-100)


def test_service_rejects_both_price_modes():
    with pytest.raises(ValueError, match="only one"):
        run_bulk(percent_change=10, set_price=5000)


def test_service_rejects_neither_price_mode():
    with pytest.raises(ValueError, match="Provide percent_change or set_price"):
        run_bulk()


def test_no_matching_rooms_returns_an_empty_result_not_an_error():
    result = run_bulk(percent_change=10)
    assert result["rooms_matched"] == 0
    assert result["changes"] == []
