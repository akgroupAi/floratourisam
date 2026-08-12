"""Tests for the admin alert emails sent on bookings, consultations, and proposals."""

import asyncio
import inspect
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from app.utils import admin_notify
from app.utils.email_sender import render_admin_alert_email_html


# ── The shared template ───────────────────────────────────────


def test_template_renders_supplied_rows():
    html = render_admin_alert_email_html(
        heading="New Hotel Booking",
        subheading="Booking HTL-1",
        rows=[("Guest", "John Doe"), ("Total", "INR 10,500.00")],
    )
    assert "New Hotel Booking" in html
    assert "John Doe" in html
    assert "INR 10,500.00" in html


def test_template_drops_empty_rows():
    """Callers pass optional fields without guarding each one."""
    html = render_admin_alert_email_html(
        heading="H", subheading="S",
        rows=[("Guest", "John"), ("Phone", None), ("Notes", ""), ("Stale", "None")],
    )
    assert "Phone" not in html
    assert "Notes" not in html
    assert "Stale" not in html
    assert "John" in html


def test_template_omits_the_message_block_when_there_is_no_message():
    html = render_admin_alert_email_html(heading="H", subheading="S", rows=[("A", "b")])
    assert "Notes" not in html


def test_template_includes_a_message_block_when_given_one():
    html = render_admin_alert_email_html(
        heading="H", subheading="S", rows=[("A", "b")],
        message_title="Special requests", message_body="Late check-in please",
    )
    assert "Special requests" in html
    assert "Late check-in please" in html


def test_money_formatting_includes_currency_and_thousands():
    assert admin_notify._money(10500.0, "INR") == "INR 10,500.00"
    assert admin_notify._money(99.5, "USD") == "USD 99.50"


def test_money_handles_a_missing_amount():
    assert admin_notify._money(None, "INR") == ""


# ── Failures must never break the booking ─────────────────────


class ExplodingDB:
    """Every database call fails."""

    async def execute(self, stmt):
        raise RuntimeError("database is down")

    async def commit(self):
        raise RuntimeError("database is down")


class FakeBooking:
    id = uuid4()
    patient_id = uuid4()
    booking_type = "hotel"
    hotel_room_id = uuid4()
    apartment_id = None
    restaurant_id = None
    reference_number = "HTL-2026-001"
    check_in_date = date(2026, 9, 1)
    check_out_date = date(2026, 9, 3)
    guest_count = 2
    total_price = 10500.0
    platform_fee = 500.0
    currency = "INR"
    is_paid = False
    status = "pending"
    special_requests = None


def test_booking_alert_swallows_database_failures():
    """A mail failure must never roll back the booking that triggered it."""
    asyncio.run(admin_notify.notify_admin_new_booking(ExplodingDB(), FakeBooking()))


def test_consultation_alert_swallows_database_failures():
    class FakeConsultation:
        id = uuid4()
        patient_id = uuid4()
        doctor_id = uuid4()
        reference_number = "CNS-1"
        consultation_type = "video"
        scheduled_at = datetime.now(timezone.utc)
        duration_minutes = 30
        fee = 750.0
        is_paid = False
        status = "pending"
        reason = None
        symptoms = None

    asyncio.run(
        admin_notify.notify_admin_new_consultation(ExplodingDB(), FakeConsultation())
    )


def test_proposal_alert_swallows_database_failures():
    class FakeProposal:
        id = uuid4()
        reference_number = "TP-1"
        treatment_name = "Knee Replacement"
        estimated_duration = "5 days"
        proposed_visit_date = date(2026, 10, 1)
        currency = "INR"
        consultation_fee = 5000.0
        surgery_fee = 380000.0
        hospital_stay_fee = 55000.0
        medications_fee = 8000.0
        other_fees = 0.0
        total_amount = 448000.0
        status = "pending"
        doctor_notes = None
        description = None
        doctor = None
        patient = None
        hospital = None

    asyncio.run(admin_notify.notify_admin_new_proposal(ExplodingDB(), FakeProposal()))


# ── Recipient handling ────────────────────────────────────────


class SilentDB:
    async def execute(self, stmt):
        raise RuntimeError("not needed")

    async def commit(self):
        pass


def test_no_recipient_configured_is_a_warning_not_a_crash(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "FIRST_SUPERUSER_EMAIL", None)
    asyncio.run(admin_notify._send(SilentDB(), "subject", "<p>x</p>", "test"))


def test_admin_email_reads_from_settings():
    from app.core.config import settings

    assert admin_notify._admin_email() == settings.FIRST_SUPERUSER_EMAIL


# ── Every trigger is wired ────────────────────────────────────


@pytest.mark.parametrize(
    "module_path,class_name,method",
    [
        ("app.services.booking_service", "BookingService", "create_hotel_booking"),
        ("app.services.booking_service", "BookingService", "create_apartment_booking"),
        ("app.services.booking_service", "BookingService", "create_restaurant_booking"),
        ("app.services.consultation_service", "ConsultationService", "create"),
        ("app.services.appointment_service", "AppointmentService", "schedule_appointment"),
        (
            "app.services.treatment_proposal_service",
            "TreatmentProposalService",
            "create_proposal",
        ),
    ],
)
def test_admin_alert_is_wired_into_every_creation_path(module_path, class_name, method):
    """Guards against a new booking type shipping without an admin alert."""
    import importlib

    module = importlib.import_module(module_path)
    source = inspect.getsource(getattr(getattr(module, class_name), method))
    assert "notify_admin_new" in source, (
        f"{class_name}.{method} creates a bookable thing but sends no admin alert"
    )


def test_consultation_bookings_do_not_double_alert():
    """A consultation creates a Booking too — only the consultation alert should fire."""
    source = inspect.getsource(admin_notify.notify_admin_new_booking)
    assert "notify_admin_new_consultation" in source, (
        "the booking alert must explain why it skips consultation bookings"
    )


# ── Patient's response to a proposal ──────────────────────────


class FakeProposalResponse:
    id = uuid4()
    reference_number = "TP-2026-001"
    treatment_name = "Total Knee Replacement"
    status = "approved"
    currency = "INR"
    total_amount = 448000.0
    proposed_visit_date = date(2026, 10, 1)
    responded_at = datetime(2026, 8, 12, 14, 30, tzinfo=timezone.utc)
    patient_response_notes = None
    doctor = None
    patient = None
    hospital = None


class CapturingDB:
    """Captures the email that would be sent instead of sending it."""

    def __init__(self):
        self.sent = []

    async def execute(self, stmt):
        raise RuntimeError("not needed")

    async def commit(self):
        pass


def capture_response_email(action, monkeypatch, proposal=None):
    captured = {}

    async def fake_send(db, subject, html, category):
        captured["subject"] = subject
        captured["html"] = html
        captured["category"] = category

    monkeypatch.setattr(admin_notify, "_send", fake_send)
    asyncio.run(
        admin_notify.notify_admin_proposal_response(
            CapturingDB(), proposal or FakeProposalResponse(), action
        )
    )
    return captured


def test_acceptance_sends_an_email(monkeypatch):
    """The conversion point — treatment agreed and payment follows."""
    captured = capture_response_email("approve", monkeypatch)
    assert "Accepted" in captured["subject"]
    assert "TP-2026-001" in captured["subject"]


def test_acceptance_email_prompts_the_next_step(monkeypatch):
    captured = capture_response_email("approve", monkeypatch)
    assert "arrange scheduling and payment" in captured["html"]


def test_acceptance_email_carries_the_amount(monkeypatch):
    captured = capture_response_email("approve", monkeypatch)
    assert "448,000.00" in captured["html"]


def test_rejection_sends_an_email(monkeypatch):
    captured = capture_response_email("reject", monkeypatch)
    assert "Rejected" in captured["subject"]


def test_revision_request_sends_an_email(monkeypatch):
    captured = capture_response_email("request_revision", monkeypatch)
    assert "Revision Requested" in captured["subject"]
    assert "revise and resend" in captured["html"]


def test_patient_notes_are_included_when_given(monkeypatch):
    proposal = FakeProposalResponse()
    proposal.patient_response_notes = "Can we move it a week later?"
    captured = capture_response_email("request_revision", monkeypatch, proposal)
    assert "Can we move it a week later?" in captured["html"]


def test_unknown_action_sends_nothing(monkeypatch):
    captured = capture_response_email("something_else", monkeypatch)
    assert captured == {}


def test_response_alert_uses_its_own_category(monkeypatch):
    """Separate from the creation alert so the two are filterable in email_logs."""
    captured = capture_response_email("approve", monkeypatch)
    assert captured["category"] == "proposal_response_admin_alert"


def test_response_alert_swallows_failures():
    asyncio.run(
        admin_notify.notify_admin_proposal_response(
            ExplodingDB(), FakeProposalResponse(), "approve"
        )
    )


def test_patient_response_path_is_wired():
    from app.services.treatment_proposal_service import TreatmentProposalService

    source = inspect.getsource(TreatmentProposalService.patient_respond)
    assert "notify_admin_proposal_response" in source
