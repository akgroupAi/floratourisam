"""Tests for booking travellers and their documents.

These carry passports and medical reports, so the access rules and the upload guards
are tested directly rather than only through the endpoints.
"""

import asyncio
import inspect
from datetime import date
from uuid import uuid4

import pytest

from app.schemas.booking import (
    DOCUMENT_TYPES,
    GUEST_TYPES,
    BookingGuestCreate,
    BookingGuestUpdate,
    HotelBookingCreate,
)
from app.services.booking_guest_service import (
    ALLOWED_CONTENT_TYPES,
    MAX_DOCUMENT_BYTES,
    MAX_DOCUMENTS_PER_BOOKING,
    BookingGuestService,
    booking_documents_dir,
    document_download_url,
)


# ── Traveller schema ──────────────────────────────────────────


def test_a_traveller_needs_a_name():
    with pytest.raises(ValueError):
        BookingGuestCreate(full_name="X")  # under the 2-char minimum


def test_guest_defaults_to_companion():
    assert BookingGuestCreate(full_name="Jane Doe").guest_type == "companion"


def test_guest_type_is_restricted():
    with pytest.raises(ValueError, match="guest_type must be one of"):
        BookingGuestCreate(full_name="Jane Doe", guest_type="tourist")


def test_known_guest_types():
    assert GUEST_TYPES == {"patient", "companion"}


def test_passport_cannot_expire_before_birth():
    with pytest.raises(ValueError, match="passport_expiry cannot be before"):
        BookingGuestCreate(
            full_name="Jane Doe",
            date_of_birth=date(1990, 5, 1),
            passport_expiry=date(1985, 1, 1),
        )


def test_full_traveller_details_are_accepted():
    guest = BookingGuestCreate(
        full_name="John Doe",
        guest_type="patient",
        date_of_birth=date(1980, 3, 15),
        gender="male",
        nationality="United Kingdom",
        passport_number="GB1234567",
        passport_expiry=date(2030, 1, 1),
        phone="+441234567890",
        email="john@example.com",
        special_needs="Wheelchair access required",
    )
    assert guest.passport_number == "GB1234567"
    assert guest.special_needs.startswith("Wheelchair")


def test_update_schema_allows_partial_edits():
    update = BookingGuestUpdate(phone="+919876543210")
    supplied = update.model_dump(exclude_unset=True)
    assert supplied == {"phone": "+919876543210"}


def test_booking_creation_accepts_travellers_inline():
    booking = HotelBookingCreate(
        room_id=uuid4(),
        check_in_date=date(2026, 9, 1),
        check_out_date=date(2026, 9, 5),
        guest_count=2,
        guests=[
            {"full_name": "John Doe", "guest_type": "patient"},
            {"full_name": "Jane Doe", "relationship_to_patient": "spouse"},
        ],
    )
    assert len(booking.guests) == 2
    assert booking.guests[0].guest_type == "patient"


# ── Who is the patient ────────────────────────────────────────


class RecordingDB:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass

    async def commit(self):
        pass


def add_guests(guests):
    db = RecordingDB()
    asyncio.run(BookingGuestService(db).add_guests(uuid4(), guests, created_by=uuid4()))
    return db.added


def test_one_traveller_marked_patient_is_the_primary():
    rows = add_guests([
        BookingGuestCreate(full_name="John Doe", guest_type="patient"),
        BookingGuestCreate(full_name="Jane Doe"),
    ])
    assert rows[0].guest_type == "patient"
    assert rows[0].is_primary is True
    assert rows[1].guest_type == "companion"
    assert rows[1].is_primary is False


def test_two_patients_are_rejected():
    """A booking treats one person; the rest are companions."""
    with pytest.raises(ValueError, match="only have one patient"):
        add_guests([
            BookingGuestCreate(full_name="John Doe", guest_type="patient"),
            BookingGuestCreate(full_name="Jane Doe", guest_type="patient"),
        ])


def test_first_traveller_is_promoted_when_nobody_is_marked():
    """A booking with companions but nobody being treated is meaningless."""
    rows = add_guests([
        BookingGuestCreate(full_name="John Doe"),
        BookingGuestCreate(full_name="Jane Doe"),
    ])
    assert rows[0].guest_type == "patient"
    assert rows[0].is_primary is True
    assert rows[1].guest_type == "companion"


def test_relationship_is_cleared_on_the_patient():
    """"Spouse of the patient" is meaningless on the patient themselves."""
    rows = add_guests([
        BookingGuestCreate(
            full_name="John Doe", guest_type="patient", relationship_to_patient="self"
        ),
    ])
    assert rows[0].relationship_to_patient is None


def test_companion_keeps_their_relationship():
    rows = add_guests([
        BookingGuestCreate(full_name="John Doe", guest_type="patient"),
        BookingGuestCreate(full_name="Jane Doe", relationship_to_patient="spouse"),
    ])
    assert rows[1].relationship_to_patient == "spouse"


def test_empty_traveller_list_is_a_no_op():
    assert add_guests([]) == []


# ── Documents ─────────────────────────────────────────────────


def test_document_types_cover_what_medical_travel_needs():
    assert {"passport", "flight_ticket", "visa", "insurance"} <= DOCUMENT_TYPES


def test_only_images_and_pdfs_are_accepted():
    assert set(ALLOWED_CONTENT_TYPES) == {
        "image/jpeg", "image/jpg", "image/png", "image/webp", "application/pdf",
    }


def test_upload_limits_are_sane():
    assert MAX_DOCUMENT_BYTES == 10 * 1024 * 1024
    assert MAX_DOCUMENTS_PER_BOOKING == 25


def test_download_url_is_an_authenticated_api_path():
    booking_id, document_id = uuid4(), uuid4()
    url = document_download_url(booking_id, document_id)
    assert url == f"/api/v1/bookings/{booking_id}/documents/{document_id}"


def test_documents_directory_derives_from_upload_dir(monkeypatch):
    """Not the process working directory — the mistake that broke quote documents."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "UPLOAD_DIR", "/srv/uploads")
    assert str(booking_documents_dir()).replace("\\", "/").endswith(
        "/srv/uploads/booking_documents"
    )


class FakeDocument:
    def __init__(self, file_path):
        self.file_path = file_path


def test_document_path_is_rebuilt_from_the_basename(monkeypatch, tmp_path):
    """A tampered file_path must not read outside the upload directory."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    docs = booking_documents_dir()
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "real.pdf").write_bytes(b"%PDF-1.4")

    service = BookingGuestService(None)
    resolved = service.resolve_document_path(FakeDocument("/etc/passwd/../real.pdf"))
    assert resolved == docs / "real.pdf"


def test_traversal_attempt_resolves_to_nothing(monkeypatch, tmp_path):
    from app.core.config import settings

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    booking_documents_dir().mkdir(parents=True, exist_ok=True)

    service = BookingGuestService(None)
    assert service.resolve_document_path(FakeDocument("../../../etc/passwd")) is None


def test_missing_file_resolves_to_none(monkeypatch, tmp_path):
    from app.core.config import settings

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    booking_documents_dir().mkdir(parents=True, exist_ok=True)

    service = BookingGuestService(None)
    assert service.resolve_document_path(FakeDocument("gone.pdf")) is None


# ── Access control ────────────────────────────────────────────


def test_document_routes_all_resolve_the_caller_first():
    """Every traveller and document route must go through the ownership check."""
    from app.api.v1 import bookings

    source = inspect.getsource(bookings)
    for handler in (
        "list_booking_guests",
        "add_booking_guests",
        "update_booking_guest",
        "remove_booking_guest",
        "list_booking_documents",
        "upload_booking_document",
        "download_booking_document",
        "delete_booking_document",
    ):
        start = source.index(f"async def {handler}(")
        body = source[start : start + 2000]
        assert "_booking_for_caller" in body, f"{handler} does not check ownership"


def test_unauthorised_access_returns_404_not_403():
    """403 would confirm the booking exists; 404 reveals nothing.

    Checks the raises, not the prose — the docstring mentions 403 to explain the choice.
    """
    from app.api.v1 import bookings

    code = "\n".join(
        line
        for line in inspect.getsource(bookings._booking_for_caller).splitlines()
        if "raise HTTPException" in line or "status_code" in line
    )
    assert "404" in code
    assert "403" not in code
    assert (
        inspect.getsource(bookings._booking_for_caller).count("Booking not found") >= 3
    )


def test_patient_cannot_be_removed_from_their_own_booking():
    source = inspect.getsource(BookingGuestService.remove_guest)
    assert "cannot be removed" in source
