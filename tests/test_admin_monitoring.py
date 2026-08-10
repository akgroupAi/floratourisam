"""Tests for the admin platform-monitoring endpoints.

These exercise the query builders and pure logic without a database: SQL is compiled
against the Postgres dialect, and guard clauses are called directly.
"""

import asyncio
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from app.schemas.admin_ops import BroadcastRequest
from app.schemas.common import PaginationParams
from app.services.admin_chat_service import AdminChatService
from app.services.admin_ops_service import AdminOpsService
from app.services.ai_monitoring_service import AIMonitoringService
from app.services.audit_service import AUDITED_ENTITIES, AuditService
from app.services.consultation_service import ConsultationService
from app.services.payment_service import PaymentService


class _QueryCaptured(Exception):
    """Sentinel to unwind once the statement is captured.

    Deliberately not StopIteration — raising that inside a coroutine is converted to
    RuntimeError by the interpreter.
    """


class CapturingDB:
    """Stands in for AsyncSession: captures the first statement, then stops."""

    def __init__(self):
        self.stmt = None

    async def execute(self, stmt):
        self.stmt = stmt
        raise _QueryCaptured

    async def commit(self):
        pass


def compile_first_query(coro_factory) -> str:
    """Run a service method far enough to capture and compile its first SQL statement."""

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


PAGE = PaginationParams(page=1, page_size=20)


# ── Payments ──────────────────────────────────────────────────


def test_admin_payment_list_is_not_scoped_to_one_user():
    """The whole point of the admin list: no implicit user_id filter.

    `payments.user_id = users.id` is the JOIN, so check for a comparison against a
    literal instead — that would be the scoping filter.
    """
    sql = compile_first_query(lambda db: PaymentService(db).get_admin_list(PAGE))
    assert "payments.user_id = '" not in sql
    assert "payments.is_deleted = false" in sql


def test_admin_payment_list_can_still_filter_by_user():
    user_id = uuid4()
    sql = compile_first_query(
        lambda db: PaymentService(db).get_admin_list(PAGE, user_id=user_id)
    )
    assert f"payments.user_id = '{user_id}'" in sql


def test_admin_payment_list_joins_the_payer():
    sql = compile_first_query(lambda db: PaymentService(db).get_admin_list(PAGE))
    assert "JOIN users ON payments.user_id = users.id" in sql


def test_admin_payment_search_covers_reference_and_payer():
    sql = compile_first_query(
        lambda db: PaymentService(db).get_admin_list(PAGE, search="jane")
    )
    for column in ("payments.reference_number", "payments.gateway_transaction_id",
                   "users.email", "users.full_name"):
        assert column in sql


def test_admin_payment_failed_only_filters_to_failures():
    sql = compile_first_query(
        lambda db: PaymentService(db).get_admin_list(PAGE, failed_only=True)
    )
    assert "payments.status = 'failed'" in sql


def test_admin_payment_date_range_is_inclusive_of_the_end_day():
    sql = compile_first_query(
        lambda db: PaymentService(db).get_admin_list(
            PAGE, from_date=date(2026, 1, 1), to_date=date(2026, 1, 31)
        )
    )
    assert "'2026-01-01 00:00:00+00:00'" in sql
    assert "'2026-02-01 00:00:00+00:00'" in sql  # to_date + 1 day, exclusive


def test_payment_stats_treats_confirmed_as_completed():
    sql = compile_first_query(lambda db: PaymentService(db).get_admin_stats())
    assert "GROUP BY payments.status" in sql


def test_reconciliation_only_counts_completed_payments():
    sql = compile_first_query(lambda db: PaymentService(db).get_reconciliation())
    assert "payments.status IN ('completed', 'confirmed')" in sql


def test_transactions_are_ordered_oldest_first():
    sql = compile_first_query(
        lambda db: PaymentService(db).get_transactions(uuid4())
    )
    assert "ORDER BY payment_transactions.created_at ASC" in sql


# ── Refund guard ──────────────────────────────────────────────


class FakePayment:
    id = uuid4()
    amount = 100.0
    currency = "INR"
    refund_amount = None
    is_refunded = False
    refunded_at = None
    refund_reason = None
    status = "completed"
    updated_by = None


def test_refund_rejects_more_than_the_payment_amount():
    async def run():
        service = PaymentService(CapturingDB())
        await service.admin_refund(FakePayment(), 150.0, "oops", actioned_by=uuid4())

    with pytest.raises(ValueError, match="exceeds refundable balance"):
        asyncio.run(run())


def test_refund_rejects_partial_that_would_overshoot():
    payment = FakePayment()
    payment.refund_amount = 80.0

    async def run():
        service = PaymentService(CapturingDB())
        await service.admin_refund(payment, 30.0, "oops", actioned_by=uuid4())

    with pytest.raises(ValueError, match="exceeds refundable balance"):
        asyncio.run(run())


# ── Consultations ─────────────────────────────────────────────


def test_admin_consultation_list_needs_no_patient_or_doctor():
    """The public endpoint returns [] for admins; this one must not filter that way."""
    sql = compile_first_query(lambda db: ConsultationService(db).get_admin_list(PAGE))
    assert "consultations.patient_id =" not in sql
    assert "consultations.doctor_id =" not in sql
    assert "consultations.is_deleted = false" in sql


def test_admin_consultation_active_only_covers_waiting_and_in_progress():
    sql = compile_first_query(
        lambda db: ConsultationService(db).get_admin_list(PAGE, active_only=True)
    )
    assert "IN ('waiting', 'in_progress')" in sql


def test_admin_consultation_hospital_filter_uses_a_doctor_subquery():
    hospital_id = uuid4()
    sql = compile_first_query(
        lambda db: ConsultationService(db).get_admin_list(PAGE, hospital_id=hospital_id)
    )
    assert "doctors.hospital_id" in sql
    assert str(hospital_id) in sql


def test_admin_consultation_today_filter_spans_exactly_one_day():
    sql = compile_first_query(
        lambda db: ConsultationService(db).get_admin_list(PAGE, today_only=True)
    )
    assert sql.count("consultations.scheduled_at") >= 2


# ── AI monitoring ─────────────────────────────────────────────


def test_ai_out_of_scope_filter_reads_the_json_flag():
    sql = compile_first_query(
        lambda db: AIMonitoringService(db).list_logs(PAGE, out_of_scope=True)
    )
    assert "ai_logs.request_metadata ->> 'in_scope') = 'false'" in sql


def test_ai_in_scope_filter_treats_missing_metadata_as_in_scope():
    """Rows written before in_scope existed must not be counted as refusals."""
    sql = compile_first_query(
        lambda db: AIMonitoringService(db).list_logs(PAGE, out_of_scope=False)
    )
    assert "= 'true'" in sql
    assert "IS NULL" in sql


def test_ai_stats_excludes_deleted_logs():
    sql = compile_first_query(lambda db: AIMonitoringService(db).get_stats())
    assert "ai_logs.is_deleted = false" in sql


def test_ai_daily_usage_groups_by_day():
    sql = compile_first_query(lambda db: AIMonitoringService(db).get_daily_usage(days=7))
    assert "date_trunc('day', ai_logs.created_at)" in sql


def test_ai_top_questions_normalises_case_and_whitespace():
    sql = compile_first_query(lambda db: AIMonitoringService(db).get_top_questions())
    assert "lower(trim(ai_logs.user_message))" in sql


def test_knowledge_status_reports_settings_without_a_built_index():
    async def run():
        return await AIMonitoringService(CapturingDB()).get_knowledge_status()

    status = asyncio.run(run())
    assert status["total_documents"] >= 0
    assert "scope_threshold" in status
    assert status["note"]


# ── Chat oversight ────────────────────────────────────────────


def test_chat_rooms_participant_filter_uses_a_subquery():
    user_id = uuid4()
    sql = compile_first_query(
        lambda db: AdminChatService(db).list_rooms(PAGE, participant_id=user_id)
    )
    assert "chat_participants.user_id" in sql
    assert str(user_id) in sql


def test_chat_transcript_hides_deleted_messages_by_default():
    sql = compile_first_query(
        lambda db: AdminChatService(db).get_messages(uuid4(), PAGE, accessed_by=uuid4())
    )
    assert "chat_messages.is_deleted = false" in sql


def test_chat_transcript_can_include_deleted_messages():
    sql = compile_first_query(
        lambda db: AdminChatService(db).get_messages(
            uuid4(), PAGE, accessed_by=uuid4(), include_deleted=True
        )
    )
    assert "chat_messages.is_deleted = false" not in sql


# ── Audit trail ───────────────────────────────────────────────


def test_audit_covers_the_core_business_entities():
    types = set(AuditService.entity_types())
    assert {"hotel", "apartment", "doctor", "hospital", "payment", "booking"} <= types


def test_audit_feed_unions_created_updated_and_deleted():
    sql = compile_first_query(lambda db: AuditService(db).get_feed(PAGE))
    for action in ("'created'", "'updated'", "'deleted'"):
        assert action in sql
    assert sql.count("UNION ALL") == len(AUDITED_ENTITIES) * 3 - 1


def test_audit_feed_excludes_updates_that_are_really_inserts():
    """updated_at == created_at is the insert itself, not an edit."""
    sql = compile_first_query(lambda db: AuditService(db).get_feed(PAGE))
    assert "updated_at > " in sql


def test_audit_feed_can_narrow_to_one_entity_type():
    sql = compile_first_query(
        lambda db: AuditService(db).get_feed(PAGE, entity_type="hotel")
    )
    assert "FROM hotels" in sql
    assert "FROM hospitals" not in sql


def test_audit_entity_history_rejects_an_unknown_type():
    async def run():
        await AuditService(CapturingDB()).get_entity_history("unicorn", uuid4(), PAGE)

    with pytest.raises(ValueError, match="Unknown entity type"):
        asyncio.run(run())


# ── Operations ────────────────────────────────────────────────


def test_broadcast_requires_an_audience():
    with pytest.raises(ValueError, match="refusing to broadcast to everyone"):
        BroadcastRequest(title="Notice", message="Hello")


def test_broadcast_accepts_roles():
    request = BroadcastRequest(title="Notice", message="Hello", roles=["patient"])
    assert request.roles == ["patient"]


def test_broadcast_accepts_explicit_users():
    user_id = uuid4()
    request = BroadcastRequest(title="Notice", message="Hello", user_ids=[user_id])
    assert request.user_ids == [user_id]


def test_broadcast_service_guard_fires_before_any_query():
    async def run():
        await AdminOpsService(CapturingDB()).broadcast("T", "M", uuid4())

    with pytest.raises(ValueError, match="Refusing to broadcast"):
        asyncio.run(run())


def test_broadcast_targets_only_active_users():
    sql = compile_first_query(
        lambda db: AdminOpsService(db).broadcast("T", "M", uuid4(), roles=["patient"])
    )
    assert "users.is_active = true" in sql
    assert "users.is_deleted = false" in sql
    assert "users.role IN ('patient')" in sql


def test_events_upcoming_only_filters_to_the_future():
    sql = compile_first_query(
        lambda db: AdminOpsService(db).list_events(PAGE, upcoming_only=True)
    )
    assert "events.start_time >=" in sql


def test_favorite_stats_groups_by_entity_type():
    sql = compile_first_query(lambda db: AdminOpsService(db).favorite_stats())
    assert "GROUP BY patient_favorites.entity_type" in sql


def test_proposal_stats_excludes_deleted_proposals():
    sql = compile_first_query(lambda db: AdminOpsService(db).proposal_stats())
    assert "treatment_proposals.is_deleted = false" in sql


# ── Pagination ceilings ───────────────────────────────────────
#
# Regression guard for a real 500: several admin routes advertised page_size up to
# 200, but the handler then built PaginationParams(page_size=...), which caps at 100.
# The ValidationError was raised inside the handler rather than during request
# parsing, so FastAPI returned 500 instead of 422. Any route whose declared ceiling
# exceeds the shared model's will crash on a large page.


def _pagination_model_ceiling() -> int:
    for meta in PaginationParams.model_fields["page_size"].metadata:
        if hasattr(meta, "le"):
            return meta.le
    raise AssertionError("PaginationParams.page_size has no upper bound")


def test_pagination_params_still_has_an_upper_bound():
    assert _pagination_model_ceiling() == 100


def test_no_admin_route_advertises_a_page_size_above_the_shared_ceiling():
    """Every `page_size` query param must fit through PaginationParams."""
    from fastapi.routing import APIRoute

    from app.main import app

    ceiling = _pagination_model_ceiling()
    offenders = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or "/admin" not in route.path:
            continue
        for param in route.dependant.query_params:
            if param.name != "page_size":
                continue
            for meta in getattr(param.field_info, "metadata", []):
                le = getattr(meta, "le", None)
                if le is not None and le > ceiling:
                    offenders.append(f"{route.path} (page_size le={le})")

    assert not offenders, (
        f"These routes accept a page_size above PaginationParams' {ceiling} "
        f"and will 500 on a large page: {offenders}"
    )


def test_max_page_size_is_accepted_by_pagination_params():
    """The advertised maximum must actually construct."""
    params = PaginationParams(page=1, page_size=_pagination_model_ceiling())
    assert params.page_size == 100
    assert params.offset == 0


def test_pagination_params_rejects_above_the_ceiling():
    with pytest.raises(ValidationError):
        PaginationParams(page=1, page_size=_pagination_model_ceiling() + 1)
