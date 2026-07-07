"""Tests for contact form APIs."""

import pytest

from app.schemas.contact import ContactCreate, ContactStatusUpdate
from app.services.contact_service import _serialize_contact, _status_label
from app.utils.enums import ContactStatus


def test_contact_create_required_fields():
    data = ContactCreate(
        full_name="John Doe",
        email="john@example.com",
        phone="+919876543210",
        country="India",
        message="I need a consultation for knee replacement.",
    )
    assert data.full_name == "John Doe"
    assert data.treatment_of_interest is None


def test_contact_create_with_treatment():
    data = ContactCreate(
        full_name="Jane Doe",
        email="jane@example.com",
        phone="+919876543210",
        country="USA",
        treatment_of_interest="Heart Surgery",
        message="Please contact me about treatment options.",
    )
    assert data.treatment_of_interest == "Heart Surgery"


def test_status_label_pending():
    assert _status_label(ContactStatus.PENDING.value) == "Pending"
    assert _status_label(ContactStatus.IN_PROCESS.value) == "In Process"
    assert _status_label(ContactStatus.COMPLETED.value) == "Completed"


def test_serialize_contact_marks_new_pending_as_new():
    class FakeLead:
        id = "00000000-0000-0000-0000-000000000001"
        name = "Test User"
        email = "test@example.com"
        phone = "123"
        country = "India"
        treatment_interest = "Dental"
        message = "Hello"
        status = "pending"
        notes = None
        assigned_to = None
        created_at = "2026-07-07T00:00:00Z"
        updated_at = "2026-07-07T00:00:00Z"

    data = _serialize_contact(FakeLead())
    assert data["is_new"] is True
    assert data["status_label"] == "Pending"


def test_contact_status_update_schema():
    update = ContactStatusUpdate(status=ContactStatus.COMPLETED, notes="Called patient")
    assert update.status == ContactStatus.COMPLETED
    assert update.notes == "Called patient"
