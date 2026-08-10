"""Tests for quote request APIs ('Get a Free Medical Plan Quote')."""

import pytest

from app.core.config import settings
from app.schemas.quote import QuoteAssignUpdate, QuoteStatusUpdate
from app.services.quote_service import (
    _serialize_quote,
    _status_label,
    document_url,
    quote_documents_dir,
    resolve_document_path,
)
from app.utils.enums import QuoteStatus


class FakeLead:
    """Minimal stand-in for a LeadSubmission row."""

    id = "00000000-0000-0000-0000-000000000001"
    name = "Test User"
    email = "test@example.com"
    phone = "123"
    country = "India"
    medical_condition = "Orthopedics"
    treatment_interest = "Knee Replacement"
    preferred_destination = "Ahmedabad"
    message = "Please send me a plan."
    documents = None
    status = "new"
    notes = None
    assigned_to = None
    utm_source = None
    utm_medium = None
    utm_campaign = None
    created_at = "2026-08-10T00:00:00Z"
    updated_at = "2026-08-10T00:00:00Z"


def test_status_labels():
    assert _status_label(QuoteStatus.NEW.value) == "New"
    assert _status_label(QuoteStatus.CONTACTED.value) == "Contacted"
    assert _status_label(QuoteStatus.QUALIFIED.value) == "Qualified"
    assert _status_label(QuoteStatus.CONVERTED.value) == "Converted"


def test_serialize_marks_new_quote_as_new():
    data = _serialize_quote(FakeLead())
    assert data["is_new"] is True
    assert data["status_label"] == "New"
    assert data["full_name"] == "Test User"
    assert data["treatment_of_interest"] == "Knee Replacement"


def test_serialize_handles_missing_documents():
    data = _serialize_quote(FakeLead())
    assert data["documents"] == []
    assert data["document_count"] == 0


def test_serialize_counts_documents():
    lead = FakeLead()
    lead.documents = ["uploads/quote_submissions/a.pdf", "uploads/quote_submissions/b.jpg"]
    data = _serialize_quote(lead)
    assert data["document_count"] == 2
    assert len(data["documents"]) == 2


def test_serialize_converted_quote_is_not_new():
    lead = FakeLead()
    lead.status = "converted"
    lead.documents = None
    data = _serialize_quote(lead)
    assert data["is_new"] is False
    assert data["status_label"] == "Converted"


def test_serialize_defaults_missing_status_to_new():
    lead = FakeLead()
    lead.status = None
    lead.documents = None
    data = _serialize_quote(lead)
    assert data["status"] == QuoteStatus.NEW.value
    assert data["is_new"] is True


def test_status_update_schema():
    update = QuoteStatusUpdate(status=QuoteStatus.QUALIFIED, notes="Docs verified")
    assert update.status == QuoteStatus.QUALIFIED
    assert update.notes == "Docs verified"


def test_status_update_rejects_unknown_stage():
    with pytest.raises(ValueError):
        QuoteStatusUpdate(status="archived")


def test_assign_schema_requires_uuid():
    update = QuoteAssignUpdate(assigned_to="8c1d4b77-2f3e-4a0b-91cc-77e5a2d90411")
    assert str(update.assigned_to) == "8c1d4b77-2f3e-4a0b-91cc-77e5a2d90411"


# ── Document download ─────────────────────────────────────────


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    """Point UPLOAD_DIR at a temp dir and create the quote documents folder."""
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    docs_dir = quote_documents_dir()
    docs_dir.mkdir(parents=True, exist_ok=True)
    return docs_dir


def test_document_url_is_an_authenticated_api_path():
    url = document_url("abc-123", "uploads/quote_submissions/report.pdf")
    assert url == "/api/v1/admin/quotes/abc-123/documents/report.pdf"


def test_document_url_handles_windows_stored_paths():
    url = document_url("abc-123", "uploads\\quote_submissions\\report.pdf")
    assert url.endswith("/documents/report.pdf")


def test_serialize_exposes_a_url_per_document():
    lead = FakeLead()
    lead.documents = ["uploads/quote_submissions/a.pdf", "uploads/quote_submissions/b.jpg"]
    data = _serialize_quote(lead)
    assert data["document_urls"] == [
        f"/api/v1/admin/quotes/{lead.id}/documents/a.pdf",
        f"/api/v1/admin/quotes/{lead.id}/documents/b.jpg",
    ]


def test_resolve_returns_path_for_an_owned_existing_file(upload_dir):
    (upload_dir / "report.pdf").write_bytes(b"%PDF-1.4")
    lead = FakeLead()
    lead.documents = ["uploads/quote_submissions/report.pdf"]
    assert resolve_document_path(lead, "report.pdf") == upload_dir / "report.pdf"


def test_resolve_rejects_a_file_belonging_to_another_quote(upload_dir):
    (upload_dir / "someone-elses.pdf").write_bytes(b"%PDF-1.4")
    lead = FakeLead()
    lead.documents = ["uploads/quote_submissions/mine.pdf"]
    assert resolve_document_path(lead, "someone-elses.pdf") is None


def test_resolve_rejects_path_traversal(upload_dir):
    lead = FakeLead()
    lead.documents = ["uploads/quote_submissions/report.pdf"]
    for attempt in ("../../.env", "..", ".", "sub/report.pdf", "/etc/passwd"):
        assert resolve_document_path(lead, attempt) is None, attempt


def test_resolve_returns_none_when_the_file_is_missing_on_disk(upload_dir):
    lead = FakeLead()
    lead.documents = ["uploads/quote_submissions/gone.pdf"]
    assert resolve_document_path(lead, "gone.pdf") is None


def test_resolve_handles_quotes_with_no_documents(upload_dir):
    lead = FakeLead()
    lead.documents = None
    assert resolve_document_path(lead, "anything.pdf") is None


def test_resolve_matches_windows_stored_paths(upload_dir):
    (upload_dir / "report.pdf").write_bytes(b"%PDF-1.4")
    lead = FakeLead()
    lead.documents = ["uploads\\quote_submissions\\report.pdf"]
    assert resolve_document_path(lead, "report.pdf") == upload_dir / "report.pdf"
