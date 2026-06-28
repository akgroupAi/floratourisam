"""Shared booking status helpers."""

from app.utils.enums import BookingStatus, BookingType

# Statuses that block room/apartment inventory
OCCUPIED_BOOKING_STATUSES = (
    BookingStatus.CONFIRMED.value,
    BookingStatus.IN_PROGRESS.value,
    BookingStatus.COMPLETED.value,
)

PAYMENT_REQUIRED_TYPES = (
    BookingType.HOTEL.value,
    BookingType.APARTMENT.value,
)


def booking_status_label(status: str, is_paid: bool, booking_type: str) -> str:
    """Return a user-facing status label for booking list/detail views."""
    if (
        not is_paid
        and status == BookingStatus.PENDING.value
        and booking_type in PAYMENT_REQUIRED_TYPES
    ):
        return "Pending Payment"
    labels = {
        BookingStatus.PENDING.value: "Pending",
        BookingStatus.CONFIRMED.value: "Confirmed",
        BookingStatus.IN_PROGRESS.value: "In Progress",
        BookingStatus.COMPLETED.value: "Completed",
        BookingStatus.CANCELLED.value: "Cancelled",
        BookingStatus.NO_SHOW.value: "No Show",
    }
    return labels.get(status, status.replace("_", " ").title())
