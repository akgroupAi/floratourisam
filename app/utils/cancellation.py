"""Cancellation policy — what a customer gets back when they cancel.

One place that decides refunds, so the amount a patient is quoted before cancelling, the
amount recorded on the booking, and the amount sent to Razorpay are always the same
number.

The rule:

    Cancel at least CANCELLATION_FREE_WINDOW_HOURS before the booking starts
        refund = subtotal − cancellation charge
    Cancel inside that window
        refund = 0

The platform fee is retained either way — it pays for a service already delivered
(taking the booking), not for the stay itself. `PLATFORM_FEE_REFUNDABLE` flips that.

Everything here is pure arithmetic on a booking. No database, no side effects — so it is
cheap to preview and easy to test.
"""

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from typing import Optional

from app.core.config import settings


@dataclass
class RefundBreakdown:
    """What a cancellation returns, and why."""

    refund_amount: float
    cancellation_charge: float
    platform_fee_retained: float
    refundable_subtotal: float
    hours_before_start: Optional[float]
    within_free_window: bool
    is_refundable: bool
    reason: str
    lines: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "refund_amount": self.refund_amount,
            "cancellation_charge": self.cancellation_charge,
            "platform_fee_retained": self.platform_fee_retained,
            "refundable_subtotal": self.refundable_subtotal,
            "hours_before_start": self.hours_before_start,
            "within_free_window": self.within_free_window,
            "is_refundable": self.is_refundable,
            "reason": self.reason,
            "lines": self.lines,
        }


def _as_utc(value) -> Optional[datetime]:
    """Coerce a date or naive datetime to an aware UTC datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    # A plain date — treat the booking as starting at the beginning of that day.
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def booking_start(booking) -> Optional[datetime]:
    """When the booking actually begins.

    Check-in for a stay, the scheduled time for a consultation or a restaurant table.
    Returns None when a booking has neither, in which case there is no deadline to
    measure against and the free window cannot have passed.
    """
    return _as_utc(getattr(booking, "check_in_date", None)) or _as_utc(
        getattr(booking, "scheduled_time", None)
    )


def compute_refund(booking, cancelled_at: Optional[datetime] = None) -> RefundBreakdown:
    """Work out the refund for cancelling this booking now.

    Safe to call on an unpaid booking — it returns a zero refund with the reason,
    rather than raising.
    """
    now = _as_utc(cancelled_at) or datetime.now(timezone.utc)

    total = float(getattr(booking, "total_price", 0.0) or 0.0)
    platform_fee = float(getattr(booking, "platform_fee", 0.0) or 0.0)
    fee_refundable = getattr(settings, "PLATFORM_FEE_REFUNDABLE", False)

    # What the refund is calculated on: the stay itself, excluding our fee unless the
    # fee is configured as refundable.
    subtotal = round(total if fee_refundable else max(total - platform_fee, 0.0), 2)
    retained_fee = 0.0 if fee_refundable else round(min(platform_fee, total), 2)

    if not getattr(booking, "is_paid", False):
        return RefundBreakdown(
            refund_amount=0.0,
            cancellation_charge=0.0,
            platform_fee_retained=0.0,
            refundable_subtotal=0.0,
            hours_before_start=None,
            within_free_window=False,
            is_refundable=False,
            reason="This booking has not been paid, so there is nothing to refund.",
            lines=[],
        )

    start = booking_start(booking)
    window_hours = float(getattr(settings, "CANCELLATION_FREE_WINDOW_HOURS", 48))
    hours_before = None
    if start is not None:
        hours_before = round((start - now).total_seconds() / 3600, 2)

    # No start date means no deadline to miss — treat it as inside the free window.
    in_time = True if start is None else hours_before >= window_hours

    if not in_time:
        return RefundBreakdown(
            refund_amount=0.0,
            cancellation_charge=round(subtotal, 2),
            platform_fee_retained=retained_fee,
            refundable_subtotal=subtotal,
            hours_before_start=hours_before,
            within_free_window=False,
            is_refundable=False,
            reason=(
                f"Cancelled less than {int(window_hours)} hours before the booking "
                f"starts, so no refund is due."
            ),
            lines=[
                {"label": "Booking total", "amount": total},
                {"label": "Retained — late cancellation", "amount": -round(subtotal, 2)},
                {"label": "Platform fee (non-refundable)", "amount": -retained_fee}
                if retained_fee
                else None,
                {"label": "Refund", "amount": 0.0},
            ],
        )

    charge_percent = max(float(getattr(settings, "CANCELLATION_CHARGE_PERCENT", 10.0)), 0.0)
    charge = round(subtotal * charge_percent / 100, 2)
    refund = round(max(subtotal - charge, 0.0), 2)

    lines = [{"label": "Booking total", "amount": total}]
    if retained_fee:
        lines.append({"label": "Platform fee (non-refundable)", "amount": -retained_fee})
    if charge:
        lines.append(
            {"label": f"Cancellation charge ({charge_percent:g}%)", "amount": -charge}
        )
    lines.append({"label": "Refund", "amount": refund})

    return RefundBreakdown(
        refund_amount=refund,
        cancellation_charge=charge,
        platform_fee_retained=retained_fee,
        refundable_subtotal=subtotal,
        hours_before_start=hours_before,
        within_free_window=True,
        is_refundable=refund > 0,
        reason=(
            f"Cancelled more than {int(window_hours)} hours before the booking starts. "
            f"A {charge_percent:g}% cancellation charge applies."
            if charge
            else f"Cancelled more than {int(window_hours)} hours before the booking starts."
        ),
        lines=[line for line in lines if line],
    )


def policy_summary() -> dict:
    """The active policy, for showing on a booking page or a terms section."""
    window = int(getattr(settings, "CANCELLATION_FREE_WINDOW_HOURS", 48))
    charge = float(getattr(settings, "CANCELLATION_CHARGE_PERCENT", 10.0))
    fee_refundable = getattr(settings, "PLATFORM_FEE_REFUNDABLE", False)
    return {
        "free_window_hours": window,
        "cancellation_charge_percent": charge,
        "platform_fee_refundable": fee_refundable,
        "summary": (
            f"Cancel at least {window} hours before your booking starts and you will be "
            f"refunded, less a {charge:g}% cancellation charge"
            + ("." if fee_refundable else " and the platform fee.")
            + f" Cancellations within {window} hours are not refunded."
        ),
    }
