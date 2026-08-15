"""Tests for the cancellation policy and the refund queue.

This decides how much money goes back to a customer, so the arithmetic and the window
boundary are tested directly rather than only through the endpoints.
"""

import asyncio
import inspect
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core.config import settings
from app.utils.cancellation import RefundBreakdown, compute_refund, policy_summary


class FakeBooking:
    """A paid booking starting `hours_out` from now."""

    def __init__(self, hours_out=72, paid=True, total=10500.0, platform_fee=500.0):
        self.id = uuid4()
        self.reference_number = "HTL-2026-001"
        self.total_price = total
        self.platform_fee = platform_fee
        self.is_paid = paid
        self.currency = "INR"
        self.check_in_date = None
        self.scheduled_time = (
            None if hours_out is None else datetime.now(timezone.utc) + timedelta(hours=hours_out)
        )


def refund_for(**kwargs) -> RefundBreakdown:
    return compute_refund(FakeBooking(**kwargs))


# ── Outside the 48-hour window ────────────────────────────────


def test_cancelling_well_ahead_refunds_minus_the_charge():
    """10,500 total = 10,000 stay + 500 fee. Refund 10,000 less a 10% charge."""
    result = refund_for(hours_out=72)
    assert result.refundable_subtotal == 10000.0
    assert result.cancellation_charge == 1000.0
    assert result.platform_fee_retained == 500.0
    assert result.refund_amount == 9000.0
    assert result.is_refundable is True


def test_exactly_at_the_window_still_refunds():
    """48h is 'at least 48 hours', so the boundary itself qualifies."""
    assert refund_for(hours_out=48).refund_amount > 0


def test_breakdown_lines_sum_to_the_refund():
    result = refund_for(hours_out=72)
    deductions = sum(l["amount"] for l in result.lines if l["amount"] < 0)
    total_line = next(l for l in result.lines if l["label"] == "Booking total")
    refund_line = next(l for l in result.lines if l["label"] == "Refund")
    assert round(total_line["amount"] + deductions, 2) == refund_line["amount"]


# ── Inside the window ─────────────────────────────────────────


def test_cancelling_inside_the_window_refunds_nothing():
    result = refund_for(hours_out=47)
    assert result.refund_amount == 0.0
    assert result.is_refundable is False
    assert result.within_free_window is False


def test_a_day_before_refunds_nothing():
    assert refund_for(hours_out=24).refund_amount == 0.0


def test_after_the_booking_started_refunds_nothing():
    assert refund_for(hours_out=-5).refund_amount == 0.0


def test_late_cancellation_says_why():
    assert "48 hours" in refund_for(hours_out=12).reason


# ── Edge cases ────────────────────────────────────────────────


def test_unpaid_booking_refunds_nothing_and_says_so():
    result = refund_for(hours_out=72, paid=False)
    assert result.refund_amount == 0.0
    assert "not been paid" in result.reason


def test_booking_with_no_start_time_is_treated_as_in_time():
    """A booking with no date has no deadline to miss."""
    result = refund_for(hours_out=None)
    assert result.within_free_window is True
    assert result.refund_amount == 9000.0
    assert result.hours_before_start is None


def test_free_booking_refunds_nothing():
    result = compute_refund(FakeBooking(hours_out=72, total=0.0, platform_fee=0.0))
    assert result.refund_amount == 0.0


def test_platform_fee_larger_than_total_cannot_go_negative():
    result = compute_refund(FakeBooking(hours_out=72, total=100.0, platform_fee=500.0))
    assert result.refundable_subtotal == 0.0
    assert result.refund_amount == 0.0


def test_refund_never_exceeds_what_was_paid():
    for hours in (-10, 0, 1, 47, 48, 100, 5000):
        result = refund_for(hours_out=hours)
        assert 0 <= result.refund_amount <= 10500.0


# ── Configurable policy ───────────────────────────────────────


def test_platform_fee_can_be_made_refundable(monkeypatch):
    monkeypatch.setattr(settings, "PLATFORM_FEE_REFUNDABLE", True)
    result = refund_for(hours_out=72)
    assert result.platform_fee_retained == 0.0
    assert result.refundable_subtotal == 10500.0
    assert result.refund_amount == 9450.0  # 10,500 less 10%


def test_zero_charge_refunds_the_whole_subtotal(monkeypatch):
    monkeypatch.setattr(settings, "CANCELLATION_CHARGE_PERCENT", 0.0)
    result = refund_for(hours_out=72)
    assert result.cancellation_charge == 0.0
    assert result.refund_amount == 10000.0


def test_window_is_configurable(monkeypatch):
    monkeypatch.setattr(settings, "CANCELLATION_FREE_WINDOW_HOURS", 24)
    assert refund_for(hours_out=30).refund_amount > 0  # would fail under 48h


def test_negative_charge_is_treated_as_zero(monkeypatch):
    """A misconfigured negative charge must never refund more than was paid."""
    monkeypatch.setattr(settings, "CANCELLATION_CHARGE_PERCENT", -20.0)
    result = refund_for(hours_out=72)
    assert result.refund_amount <= result.refundable_subtotal


def test_policy_summary_states_the_rule():
    summary = policy_summary()
    assert summary["free_window_hours"] == 48
    assert "48 hours" in summary["summary"]
    assert "not refunded" in summary["summary"]


# ── Cancellation writes the queue, not a payout ───────────────


def test_cancel_uses_the_policy_not_a_hardcoded_percentage():
    """The refund maths lives in queue_refund; cancel must delegate to it."""
    from app.services.booking_service import BookingService

    assert "queue_refund" in inspect.getsource(BookingService.cancel)
    assert "compute_refund" in inspect.getsource(BookingService.queue_refund)
    assert "0.8" not in inspect.getsource(BookingService.cancel), (
        "the hardcoded 80% refund must be gone"
    )


def test_cancel_queues_the_refund_rather_than_paying_it():
    """Money must not leave on cancellation — an admin releases it."""
    from app.services.booking_service import BookingService

    assert 'refund_status = "pending"' in inspect.getsource(BookingService.queue_refund)
    assert "refund_payment" not in inspect.getsource(BookingService.cancel), (
        "cancellation must not call the gateway"
    )


def test_only_the_approve_path_touches_the_gateway():
    from app.services.refund_service import RefundService

    assert "refund_payment" in inspect.getsource(RefundService.approve)
    assert "refund_payment" not in inspect.getsource(RefundService.reject)


# ── Queue guards ──────────────────────────────────────────────


class NoBookingDB:
    async def execute(self, stmt):
        return _Empty()

    async def commit(self):
        pass


class _Empty:
    def scalar_one_or_none(self):
        return None

    def scalars(self):
        return self

    def all(self):
        return []

    def unique(self):
        return self


def approve(booking):
    from app.services.refund_service import RefundService

    class DB(NoBookingDB):
        async def execute(self, stmt):
            class R:
                def scalar_one_or_none(inner):
                    return booking
            return R()

    return asyncio.run(RefundService(DB()).approve(uuid4(), approved_by=uuid4()))


class QueuedBooking:
    def __init__(self, status="pending", amount=9000.0, payment_id=None):
        self.id = uuid4()
        self.reference_number = "HTL-1"
        self.refund_status = status
        self.refund_amount = amount
        self.total_price = 10500.0
        self.payment_id = payment_id or uuid4()


def test_approving_an_already_paid_refund_is_refused():
    with pytest.raises(ValueError, match="already been processed"):
        approve(QueuedBooking(status="processed"))


def test_approving_a_rejected_refund_is_refused():
    with pytest.raises(ValueError, match="rejected"):
        approve(QueuedBooking(status="rejected"))


def test_approving_a_zero_refund_is_refused():
    with pytest.raises(ValueError, match="greater than zero"):
        approve(QueuedBooking(amount=0.0))


def test_approving_without_a_linked_payment_is_refused():
    booking = QueuedBooking()
    booking.payment_id = None
    with pytest.raises(ValueError, match="No payment is linked"):
        approve(booking)


def test_missing_booking_is_refused():
    from app.services.refund_service import RefundService

    with pytest.raises(ValueError, match="Booking not found"):
        asyncio.run(RefundService(NoBookingDB()).approve(uuid4(), approved_by=uuid4()))


def test_a_failed_refund_can_be_retried():
    """A gateway failure must stay in the queue, not vanish."""
    from app.services.refund_service import RefundService

    source = inspect.getsource(RefundService.approve)
    assert 'booking.refund_status = FAILED' in source
    assert "PENDING, FAILED" in source, "the queue must include failed refunds for retry"


# ── Every cancellation path queues a refund ───────────────────


def test_all_three_cancellation_paths_use_the_shared_queue():
    """A consultation cancelled by a patient is owed money like a hotel stay.

    Three code paths cancel a booking: the booking endpoint, a consultation status
    change, and cancel_appointment. If one skips the queue, that customer is silently
    never refunded.
    """
    from app.services.appointment_service import AppointmentService
    from app.services.booking_service import BookingService
    from app.services.consultation_service import ConsultationService

    for label, fn in [
        ("BookingService.cancel", BookingService.cancel),
        ("ConsultationService.update_status", ConsultationService.update_status),
        ("AppointmentService.cancel_appointment", AppointmentService.cancel_appointment),
    ]:
        assert "queue_refund" in inspect.getsource(fn), f"{label} does not queue a refund"


def test_queue_refund_does_not_commit_or_call_the_gateway():
    """It prepares the row; the caller commits and only an admin releases money.

    Checks the executable lines, not the prose — the docstring mentions commit to
    explain why it does not.
    """
    from app.services.booking_service import BookingService

    source = inspect.getsource(BookingService.queue_refund)
    body = source.split('"""')[-1]  # everything after the closing docstring quotes
    assert "commit" not in body
    assert "refund_payment" not in body


class QueueTarget:
    """A paid booking starting `hours_out` from now."""

    def __init__(self, hours_out=72, total=787.5, fee=37.5, paid=True):
        self.total_price = total
        self.platform_fee = fee
        self.is_paid = paid
        self.check_in_date = None
        self.scheduled_time = datetime.now(timezone.utc) + timedelta(hours=hours_out)
        self.refund_amount = None
        self.cancellation_charge = None
        self.refund_status = "none"
        self.refund_requested_at = None
        self.refund_note = None


def test_consultation_cancelled_early_queues_a_refund():
    from app.services.booking_service import BookingService

    booking = QueueTarget(hours_out=72)
    BookingService.queue_refund(booking)
    assert booking.refund_status == "pending"
    assert booking.refund_amount == 675.0  # 750 less 10%
    assert booking.cancellation_charge == 75.0
    assert booking.refund_requested_at is not None


def test_consultation_cancelled_late_queues_nothing_and_says_why():
    from app.services.booking_service import BookingService

    booking = QueueTarget(hours_out=12)
    BookingService.queue_refund(booking)
    assert booking.refund_status == "none"
    assert booking.refund_amount == 0.0
    assert "48 hours" in booking.refund_note


def test_unpaid_consultation_queues_nothing():
    from app.services.booking_service import BookingService

    booking = QueueTarget(hours_out=72, paid=False)
    BookingService.queue_refund(booking)
    assert booking.refund_status == "none"
    assert "not been paid" in booking.refund_note


def test_the_consultation_scheduled_time_drives_the_deadline():
    """Consultations have no check_in_date — the policy must fall back to scheduled_time."""
    from app.utils.cancellation import booking_start

    booking = QueueTarget(hours_out=72)
    assert booking_start(booking) is not None


# ── Patient-facing refund status ──────────────────────────────


class StatusBooking:
    def __init__(self, status="pending", amount=9000.0, note=None, ref=None):
        self.id = uuid4()
        self.reference_number = "HTL-2026-0142"
        self.currency = "INR"
        self.refund_status = status
        self.refund_amount = amount
        self.cancellation_charge = 1000.0
        self.refund_note = note
        self.refund_reference = ref
        self.refund_requested_at = None
        self.refund_processed_at = None
        self.total_price = 10500.0
        self.cancelled_at = None


def patient_status(**kwargs):
    from app.services.refund_service import RefundService

    return RefundService.patient_status(StatusBooking(**kwargs))


def test_pending_tells_the_patient_it_is_being_processed():
    s = patient_status(status="pending")
    assert s["status_label"] == "Refund being processed"
    assert s["is_refund_due"] is True
    assert "9,000.00" in s["message"]


def test_pending_states_the_settlement_time():
    """"Approved" is not "in your account" - saying so avoids support tickets."""
    s = patient_status(status="pending")
    assert "5-7 working days" in s["message"]
    assert s["expected_days"] == "5-7 working days"


def test_processed_does_not_claim_the_money_has_arrived():
    s = patient_status(status="processed", ref="rfnd_abc")
    assert s["status_label"] == "Refund issued"
    assert "5-7 working days" in s["message"]
    assert s["reference"] == "rfnd_abc"


def test_rejected_shows_the_reason_given():
    s = patient_status(status="rejected", amount=0.0, note="Cancelled after check-in time")
    assert s["status_label"] == "Refund declined"
    assert "Cancelled after check-in time" in s["message"]
    assert s["is_refund_due"] is False


def test_failed_reassures_rather_than_alarms():
    s = patient_status(status="failed")
    assert "no action is needed from you" in s["message"]


def test_no_refund_due_explains_why():
    s = patient_status(
        status="none", amount=0.0,
        note="Cancelled less than 48 hours before the booking starts.",
    )
    assert s["is_refund_due"] is False
    assert "48 hours" in s["message"]
    assert s["expected_days"] is None


def test_every_status_produces_a_message():
    for status in ("none", "pending", "processed", "rejected", "failed"):
        s = patient_status(status=status)
        assert s["message"], f"{status} has no message to display"
        assert s["status_label"]


# ── Timeline attribution ──────────────────────────────────────


def test_timeline_no_longer_hardcodes_admin():
    """A patient cancelling their own booking was being attributed to an administrator."""
    from app.services.booking_service import BookingService

    source = inspect.getsource(BookingService.get_admin_detail)
    assert 'actor_name="Admin"' not in source
    assert "_actor_label" in source


def test_actor_label_marks_the_booking_owner_as_the_patient():
    from app.services.booking_service import BookingService

    patient_user_id = uuid4()

    class FakeUser:
        id = patient_user_id
        full_name = "John Doe"
        email = "john@example.com"
        role = "patient"

    class FakePatient:
        user = FakeUser()

    class FakeBookingWithPatient:
        patient = FakePatient()

    class DB:
        async def execute(self, stmt):
            class R:
                def scalar_one_or_none(inner):
                    return FakeUser()
            return R()

    service = BookingService(DB())
    label = asyncio.run(
        service._actor_label(patient_user_id, FakeBookingWithPatient())
    )
    assert label == "John Doe (Patient)"


def test_actor_label_names_an_admin_by_role():
    from app.services.booking_service import BookingService

    class FakeAdmin:
        id = uuid4()
        full_name = "Priya Sharma"
        email = "priya@example.com"
        role = "admin"

    class DB:
        async def execute(self, stmt):
            class R:
                def scalar_one_or_none(inner):
                    return FakeAdmin()
            return R()

    class B:
        patient = None

    label = asyncio.run(BookingService(DB())._actor_label(uuid4(), B()))
    assert label == "Priya Sharma (Admin)"


def test_actor_label_falls_back_to_system_with_no_actor():
    from app.services.booking_service import BookingService

    class B:
        patient = None

    assert asyncio.run(BookingService(None)._actor_label(None, B())) == "System"


# ── Customer emails ───────────────────────────────────────────


def test_approve_emails_the_customer():
    from app.services.refund_service import RefundService

    assert "notify_customer_refund_processed" in inspect.getsource(RefundService.approve)


def test_reject_emails_the_customer():
    from app.services.refund_service import RefundService

    assert "notify_customer_refund_rejected" in inspect.getsource(RefundService.reject)


def test_customer_refund_email_does_not_promise_instant_money():
    from app.utils import admin_notify

    source = inspect.getsource(admin_notify.notify_customer_refund_processed)
    assert "5-7 working days" in source


# ── Manager refund access ─────────────────────────────────────


def test_managers_can_reach_the_refund_queue():
    from app.main import app

    paths = {getattr(r, "path", "") for r in app.routes}
    assert "/api/v1/manager/refunds" in paths
    assert "/api/v1/manager/refunds/{booking_id}/approve" in paths
    assert "/api/v1/manager/refunds/{booking_id}/reject" in paths


def test_manager_refund_routes_check_ownership_before_paying():
    """A manager must never release money on another property's booking."""
    from app.api.v1 import manager

    source = inspect.getsource(manager)
    for handler in ("approve_manager_refund", "reject_manager_refund"):
        start = source.index(f"async def {handler}(")
        body = source[start : start + 1200]
        assert "get_booking" in body, f"{handler} does not verify the booking is theirs"


def test_refund_queue_can_be_scoped_to_a_manager():
    from app.services.refund_service import RefundService

    source = inspect.getsource(RefundService.list_pending)
    assert "scope" in source
    assert "booking_filter" in source


def test_timeline_explains_why_no_refund_is_due():
    """An admin looking at a cancelled paid booking must not see an unexplained absence."""
    from app.services.booking_service import BookingService

    source = inspect.getsource(BookingService.get_admin_detail)
    assert '"none": "No refund due"' in source
    assert "b.is_paid" in source, "the refund decision must show on paid cancellations"


def test_admin_detail_exposes_the_refund_position():
    from app.schemas.booking import AdminBookingDetailResponse

    fields = set(AdminBookingDetailResponse.model_fields)
    assert {"refund_status", "refund_amount", "refund_note", "cancellation_charge"} <= fields


def test_a_cancellation_inside_the_window_records_a_reason():
    """The note is what the admin screen renders instead of a blank refund panel."""
    from app.services.booking_service import BookingService

    booking = QueueTarget(hours_out=35)  # the real case: 35h50m before check-in
    BookingService.queue_refund(booking)
    assert booking.refund_status == "none"
    assert booking.refund_amount == 0.0
    assert "48 hours" in booking.refund_note
