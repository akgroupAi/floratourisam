"""Platform fee calculation.

A single place where the platform fee is worked out, so a quote, a booking, and the
Razorpay charge can never disagree about what the customer owes.

The fee is charged **on top of** the booking subtotal — the customer pays it. This is
separate from the notional gateway/processing split recorded on a Payment for
accounting, which comes out of the amount collected.
"""

from typing import Tuple

from app.core.config import settings


def platform_fee_rate() -> float:
    """Fee as a fraction, e.g. 0.05 for 5%."""
    return max(settings.PLATFORM_FEE_PERCENT, 0.0) / 100.0


def platform_fee_for(subtotal: float) -> float:
    """Platform fee owed on a subtotal. Zero for free or negative subtotals."""
    if not subtotal or subtotal <= 0:
        return 0.0
    return round(subtotal * platform_fee_rate(), 2)


def price_with_platform_fee(
    base_price: float,
    taxes: float = 0.0,
    discount: float = 0.0,
) -> Tuple[float, float, float]:
    """Work out what a customer pays for a booking.

    Returns ``(subtotal, platform_fee, total)`` where the fee applies to the
    post-discount subtotal — a discount should reduce the fee too, not just the base.

    Free bookings (a restaurant table with no pre-order, a zero-fee consultation)
    attract no fee, so nobody is asked to pay a fee on nothing.
    """
    subtotal = round((base_price or 0.0) + (taxes or 0.0) - (discount or 0.0), 2)
    if subtotal <= 0:
        return max(subtotal, 0.0), 0.0, max(subtotal, 0.0)

    fee = platform_fee_for(subtotal)
    return subtotal, fee, round(subtotal + fee, 2)
