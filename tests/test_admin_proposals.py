"""Tests for admin treatment proposal endpoints and proposal access control."""

import asyncio
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.api.v1.admin_proposal import _admin_list_item
from app.schemas.treatment_proposal import (
    AdminProposalListResponse,
    AdminProposalStatsResponse,
)
from app.services.treatment_proposal_service import TreatmentProposalService


class _QueryCaptured(Exception):
    """Sentinel to unwind once the statement is captured."""


class CapturingDB:
    """Captures the first statement; optionally replays canned scalar results."""

    def __init__(self, scalars=None):
        self.stmt = None
        self._scalars = list(scalars or [])

    async def execute(self, stmt):
        if self._scalars:
            return _FakeResult(self._scalars.pop(0))
        self.stmt = stmt
        raise _QueryCaptured


class _FakeResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


def compile_first_query(coro_factory) -> str:
    async def run():
        db = CapturingDB()
        try:
            await coro_factory(db)
        except _QueryCaptured:
            pass
        return db.stmt

    stmt = asyncio.run(run())
    assert stmt is not None, "no SQL statement was captured"
    return str(
        stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    )


# ── Access control on the shared detail endpoint ──────────────


class FakeProposal:
    id = uuid4()
    doctor_id = uuid4()
    patient_id = uuid4()


class FakeUser:
    def __init__(self, role="patient"):
        self.id = uuid4()
        self.role = role


def _can_view(user, scalar_results):
    async def run():
        service = TreatmentProposalService(CapturingDB(scalars=scalar_results))
        return await service.can_view_proposal(FakeProposal(), user)

    return asyncio.run(run())


def test_admin_can_view_any_proposal():
    # Short-circuits on role, so no queries are needed.
    assert _can_view(FakeUser("admin"), []) is True


def test_super_admin_can_view_any_proposal():
    assert _can_view(FakeUser("super_admin"), []) is True


def test_sending_doctor_can_view_their_proposal():
    assert _can_view(FakeUser("doctor"), [[FakeProposal.doctor_id]]) is True


def test_receiving_patient_can_view_their_proposal():
    assert _can_view(FakeUser("patient"), [[], [FakeProposal.patient_id]]) is True


def test_unrelated_user_cannot_view_a_proposal():
    """The bug this guards: any authenticated user could read any proposal."""
    assert _can_view(FakeUser("patient"), [[], []]) is False


def test_a_different_doctor_cannot_view_someone_elses_proposal():
    assert _can_view(FakeUser("doctor"), [[uuid4()], []]) is False


# ── Admin list query ──────────────────────────────────────────


def test_admin_list_excludes_deleted_proposals():
    sql = compile_first_query(lambda db: TreatmentProposalService(db).admin_list_proposals())
    assert "treatment_proposals.is_deleted = false" in sql


def test_pending_review_filter_looks_for_null_admin_approved():
    """Not-yet-reviewed is admin_approved IS NULL, not false."""
    sql = compile_first_query(
        lambda db: TreatmentProposalService(db).admin_list_proposals(pending_review_only=True)
    )
    assert "treatment_proposals.admin_approved IS NULL" in sql


def test_admin_approved_false_is_distinct_from_unreviewed():
    sql = compile_first_query(
        lambda db: TreatmentProposalService(db).admin_list_proposals(admin_approved=False)
    )
    assert "treatment_proposals.admin_approved = false" in sql
    assert "admin_approved IS NULL" not in sql


def test_pending_review_takes_precedence_over_admin_approved():
    """Both supplied: the review queue wins, and the two never contradict."""
    sql = compile_first_query(
        lambda db: TreatmentProposalService(db).admin_list_proposals(
            pending_review_only=True, admin_approved=True
        )
    )
    assert "admin_approved IS NULL" in sql
    assert "treatment_proposals.admin_approved = true" not in sql


def test_search_covers_reference_treatment_doctor_and_patient():
    sql = compile_first_query(
        lambda db: TreatmentProposalService(db).admin_list_proposals(search="jane")
    )
    assert "treatment_proposals.reference_number ILIKE" in sql
    assert "treatment_proposals.treatment_name ILIKE" in sql
    assert "FROM doctors" in sql
    assert "FROM patients" in sql


def test_amount_range_filters_on_total():
    sql = compile_first_query(
        lambda db: TreatmentProposalService(db).admin_list_proposals(
            min_amount=1000, max_amount=50000
        )
    )
    assert "treatment_proposals.total_amount >= 1000" in sql
    assert "treatment_proposals.total_amount <= 50000" in sql


def test_date_range_end_is_inclusive():
    sql = compile_first_query(
        lambda db: TreatmentProposalService(db).admin_list_proposals(
            from_date=date(2026, 1, 1), to_date=date(2026, 1, 31)
        )
    )
    assert "'2026-01-01 00:00:00+00:00'" in sql
    assert "'2026-02-01 00:00:00+00:00'" in sql


def test_stats_groups_status_with_its_value():
    sql = compile_first_query(lambda db: TreatmentProposalService(db).admin_stats())
    assert "GROUP BY treatment_proposals.status" in sql
    assert "sum(treatment_proposals.total_amount)" in sql


# ── List row shape ────────────────────────────────────────────


class FakeUserRow:
    full_name = "Dr. Mehta"
    email = "mehta@example.com"


class FakeDoctor:
    user = FakeUserRow()
    primary_specialty = "Orthopedics"


class FakePatientUser:
    full_name = "John Doe"
    email = "john@example.com"


class FakePatient:
    user = FakePatientUser()


class FakeHospital:
    name = "Apollo Hospital"


class FullProposal:
    id = uuid4()
    reference_number = "TP-2026-0001"
    consultation_id = uuid4()
    doctor_id = uuid4()
    patient_id = uuid4()
    hospital_id = uuid4()
    doctor = FakeDoctor()
    patient = FakePatient()
    hospital = FakeHospital()
    treatment_name = "Total Knee Replacement"
    currency = "INR"
    total_amount = 450000.0
    status = "pending"
    admin_approved = None
    admin_reviewed_at = None
    responded_at = None
    proposed_visit_date = date(2026, 9, 1)
    created_at = "2026-08-10T00:00:00Z"
    updated_at = "2026-08-10T00:00:00Z"


def test_list_row_carries_sender_recipient_and_budget():
    """The dashboard needs who sent it, who got it, and how much — in the list."""
    row = _admin_list_item(FullProposal())
    assert row["doctor_name"] == "Dr. Mehta"
    assert row["doctor_specialization"] == "Orthopedics"
    assert row["patient_name"] == "John Doe"
    assert row["patient_email"] == "john@example.com"
    assert row["hospital_name"] == "Apollo Hospital"
    assert row["total_amount"] == 450000.0
    assert row["currency"] == "INR"


def test_list_row_exposes_admin_approval_state():
    """The original /admin/all row omitted this, so approval was invisible."""
    row = _admin_list_item(FullProposal())
    assert "admin_approved" in row
    assert row["admin_approved"] is None  # not yet reviewed


def test_list_row_survives_missing_relations():
    proposal = FullProposal()
    proposal.doctor = None
    proposal.patient = None
    proposal.hospital = None
    row = _admin_list_item(proposal)
    assert row["doctor_name"] is None
    assert row["patient_name"] is None
    assert row["hospital_name"] is None


def test_list_row_validates_against_the_response_schema():
    AdminProposalListResponse.model_validate(_admin_list_item(FullProposal()))


def test_stats_schema_accepts_an_empty_platform():
    AdminProposalStatsResponse.model_validate({
        "total": 0, "by_status": {}, "value_by_status": {},
        "pending_admin_review": 0, "admin_approved": 0, "admin_rejected": 0,
        "accepted": 0, "acceptance_rate": 0.0,
        "total_proposed_value": 0.0, "accepted_value": 0.0, "pending_review_value": 0.0,
        "average_proposal_value": 0.0, "largest_proposal_value": 0.0,
        "value_by_currency": {}, "top_senders": [],
    })
