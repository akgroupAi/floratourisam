"""Tests for backend fixes B3–B9."""

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.patient import PatientUpdate
from app.schemas.review import AdminReviewApprove
from app.services.review_service import ReviewService
from app.utils.booking_helpers import booking_status_label
from app.utils.validation_messages import format_validation_message, primary_validation_message


def test_patient_update_empty_date_of_birth_becomes_none():
    """B3: empty string for date_of_birth is accepted and converted to None."""
    data = PatientUpdate(date_of_birth="")
    assert data.date_of_birth is None


def test_patient_update_valid_date_of_birth():
    """B3: valid date values still work."""
    data = PatientUpdate(date_of_birth="1990-05-15")
    assert data.date_of_birth == date(1990, 5, 15)


def test_validation_message_field_required():
    """B4: technical messages are replaced with user-friendly text."""
    msg = format_validation_message(
        {"type": "missing", "loc": ("body", "email"), "msg": "Field required"}
    )
    assert msg == "Email is required."


def test_validation_message_email():
    """B4: email validation message is user-friendly."""
    msg = format_validation_message(
        {
            "type": "value_error.email",
            "loc": ("body", "email"),
            "msg": "value is not a valid email address",
        }
    )
    assert msg == "Please enter a valid email address."


def test_primary_validation_message():
    """B4: primary message uses first formatted error."""
    errors = [
        {"type": "missing", "loc": ("body", "full_name"), "msg": "Field required"},
        {"type": "missing", "loc": ("body", "email"), "msg": "Field required"},
    ]
    assert primary_validation_message(errors) == "Name is required."


def test_booking_status_label_pending_payment():
    """B9: unpaid hotel/apartment bookings show Pending Payment."""
    label = booking_status_label("pending", is_paid=False, booking_type="hotel")
    assert label == "Pending Payment"


def test_booking_status_label_confirmed():
    """B9: paid confirmed bookings show Confirmed."""
    label = booking_status_label("confirmed", is_paid=True, booking_type="hotel")
    assert label == "Confirmed"


def test_admin_review_reject_without_reason():
    """B7: rejecting without rejection_reason uses a default."""
    data = AdminReviewApprove(approve=False)
    assert data.approve is False
    assert data.rejection_reason == "Rejected by administrator"


def test_admin_review_reject_with_reason():
    """B7: custom rejection reason is preserved."""
    data = AdminReviewApprove(approve=False, rejection_reason="Spam content")
    assert data.rejection_reason == "Spam content"


@pytest.mark.asyncio
async def test_review_enrich_includes_reviewer_email(db_session):
    """B6: enriched reviews include reviewer email and entity name."""
    from app.models.patient import Patient
    from app.models.review import Review
    from app.models.user import User
    from app.models.hotel import Hotel

    user = User(
        id=uuid4(),
        email="reviewer@example.com",
        full_name="Jane Reviewer",
        hashed_password="hashed",
        role="patient",
        is_active=True,
    )
    patient = Patient(id=uuid4(), user_id=user.id)
    hotel = Hotel(
        id=uuid4(),
        name="Test Hotel",
        slug="test-hotel",
        address_line1="123 Main",
        city="City",
        country="Country",
        currency="USD",
    )
    review = Review(
        id=uuid4(),
        entity_type="hotel",
        entity_id=hotel.id,
        patient_id=patient.id,
        rating=5,
        title="Great stay",
        body="Excellent service throughout.",
        is_verified=True,
        is_approved=True,
        created_by=user.id,
        updated_by=user.id,
    )
    db_session.add_all([user, patient, hotel, review])
    await db_session.flush()

    service = ReviewService(db_session)
    serialized = await service.serialize_review(review)

    assert serialized["reviewer_name"] == "Jane Reviewer"
    assert serialized["reviewer_email"] == "reviewer@example.com"
    assert serialized["entity_name"] == "Test Hotel"


def test_menu_item_create_requires_category_or_category_id():
    """B8: menu item requires category or category_id."""
    from app.api.v1.admin_restaurant import MenuItemCreate

    with pytest.raises(ValidationError):
        MenuItemCreate(name="Soup", price=10.0)

    item = MenuItemCreate(name="Soup", price=10.0, category_id=uuid4())
    assert item.category_id is not None
