# Admin Platform Monitoring — API Reference

The 33 endpoints added to close the gaps in [ADMIN_MONITORING_GAPS.md](ADMIN_MONITORING_GAPS.md).

Base URL: `/api/v1`
Auth: every endpoint requires `Authorization: Bearer <token>` with role `admin` or `super_admin`.

---

## Contents

| Area | Prefix | Endpoints |
|---|---|---|
| [Payments](#1-payments) | `/admin/payments` | 6 |
| [Consultations](#2-consultations) | `/admin/consultations` | 5 |
| [AI chatbot](#3-ai-chatbot) | `/admin/ai` | 8 |
| [Chat oversight](#4-chat-oversight) | `/admin/chat` | 4 |
| [Audit trail](#5-audit-trail) | `/admin/audit` | 4 |
| [Notifications](#6-notifications) | `/admin/notifications` | 3 |
| [Treatment proposals](#6b-treatment-proposals) | `/admin/treatment-proposals` | 4 |
| [Events](#7-events-and-insights) | `/admin/events` | 1 |
| [Insights](#7-events-and-insights) | `/admin/insights` | 2 |

---

## 1. Payments

Previously there was **no** admin payment view at all — `GET /api/v1/payments` scopes to the calling
user, so an admin saw only their own payments. These endpoints span every user.

### `GET /admin/payments`

| Param | Type | Description |
|---|---|---|
| `page`, `page_size` | int | Pagination (page_size 1–100) |
| `status` | string | `pending`, `processing`, `completed`, `failed`, `refunded`, `partially_refunded` |
| `payment_method` | string | `credit_card`, `debit_card`, `bank_transfer`, `wallet`, `cash` |
| `gateway` | string | e.g. `razorpay` |
| `booking_type` | string | `hotel`, `apartment`, `restaurant` |
| `user_id` | UUID | One user's payments |
| `search` | string | Reference number, gateway txn id, payer name or email |
| `refunded_only` | bool | Only refunded payments |
| `failed_only` | bool | Shortcut for triaging failures |
| `from_date`, `to_date` | date | Inclusive range on `initiated_at` |

Each row carries the payer (`user_id`, `user_name`, `user_email`), gateway ids, `refund_amount`, and
`failure_reason`. Newest first.

### `GET /admin/payments/stats`

Accepts `from_date` / `to_date`.

```json
{
  "total_payments": 1420, "successful_payments": 1305, "failed_payments": 78,
  "pending_payments": 25, "refunded_payments": 12,
  "total_revenue": 4820500.0, "total_refunded": 38000.0, "net_revenue": 4782500.0,
  "success_rate": 91.9, "failure_rate": 5.49,
  "payments_by_method": { "credit_card": 900, "wallet": 520 },
  "payments_by_status": { "completed": 1305, "failed": 78 },
  "revenue_by_currency": { "INR": 4600000.0, "USD": 220500.0 }
}
```

### `GET /admin/payments/{id}` · `GET /admin/payments/{id}/transactions`

Detail, and the gateway event trail — `authorization`, `capture`, `refund`, `void` with gateway
responses and error codes, oldest first. **The `payment_transactions` table had no API at all before
this**; it is the record that explains a failed or disputed payment.

### `POST /admin/payments/{id}/refund`

```json
{ "amount": 1500.0, "reason": "Guest cancelled within free window" }
```

Omit `amount` for a full refund. Partial refunds accumulate; status becomes `partially_refunded`
until the full amount is reached, then `refunded`. A `refund` row is written to the transaction trail
with the acting admin. Refunding more than the remaining balance returns `400`.

> **This records a refund; it does not move money.** Issue the refund in the payment gateway first,
> then record it here so the totals reconcile.

### `GET /admin/payments/reconciliation`

Compares booking totals against completed payments and flags three failure modes:

| `issue` | Meaning |
|---|---|
| `marked_paid_without_payment` | Booking says paid, no completed payment exists |
| `amount_mismatch` | Payments do not sum to the booking total |
| `paid_but_not_marked` | Fully paid but `is_paid` is still false |

Also returns `orphaned_payments` — payments pointing at a booking that no longer exists. `limit`
controls how many recent bookings are checked (default 100).

---

## 2. Consultations

`GET /api/v1/consultations` resolves the caller to a doctor or patient, so an admin got an **empty
list**. These span the platform.

### `GET /admin/consultations`

Filters: `status`, `consultation_type`, `doctor_id`, `patient_id`, `hospital_id` (all consultations
for that hospital's doctors), `is_paid`, `search` (reference, doctor or patient name/email),
`from_date`, `to_date`, plus three shortcuts:

- `today_only` — scheduled today
- `active_only` — `waiting` or `in_progress` right now
- `unconfirmed_only` — still `pending`, the ones needing a nudge

Rows resolve doctor name, specialty, hospital, and patient name.

### `GET /admin/consultations/stats`

Counts by status and type, `today`, `unpaid`, `overdue_pending` (still pending though the slot has
passed), and `completion_rate` / `cancellation_rate` / `no_show_rate`.

### `GET /admin/consultations/{id}` · `PATCH /admin/consultations/{id}/status` · `POST /admin/consultations/{id}/cancel`

```json
{ "status": "completed", "notes": "Doctor confirmed by phone" }
```

The normal state machine still applies — an invalid transition returns `400` listing what is allowed.
Admins can act on any consultation but cannot force it into a state the workflow forbids. Cancelling
also cancels the linked booking, exactly as a user-initiated cancellation does.

---

## 3. AI Chatbot

`ai_logs` recorded tokens, cost, and feedback per message; nothing read it in aggregate.

### `GET /admin/ai/stats`

Accepts `from_date` / `to_date`.

```json
{
  "total_conversations": 840, "total_messages": 3120,
  "total_tokens_used": 1840200, "total_cost": 12.4471,
  "average_response_time_ms": 1284.3, "average_rating": 4.3,
  "error_count": 14, "error_rate": 0.45,
  "helpful_count": 212, "unhelpful_count": 31, "satisfaction_rate": 87.24,
  "out_of_scope_count": 96, "out_of_scope_rate": 3.08,
  "cost_per_conversation": 0.0148,
  "intents_distribution": {}, "conversations_by_context": { "general": 700 },
  "messages_by_model": { "gpt-4o-mini": 3120 }
}
```

**Watch `out_of_scope_rate`.** It counts questions the scope gate refused as off-topic. A rising
value means `RAG_SCOPE_THRESHOLD` is too strict and real questions are being turned away — a failure
that is otherwise silent, because those users simply leave.

### The rest

| Endpoint | Purpose |
|---|---|
| `GET /admin/ai/usage/daily?days=30` | Per-day messages, tokens, cost — the spend chart series |
| `GET /admin/ai/questions/top?limit=20&days=30` | What users actually ask, normalised |
| `GET /admin/ai/knowledge-status` | What is indexed, by type, plus live retrieval settings |
| `GET /admin/ai/conversations` | All users' conversations; filter `user_id`, `rating`, `context_type`, `search` |
| `GET /admin/ai/conversations/{id}` | Full transcript of one conversation |
| `GET /admin/ai/logs` | Every exchange; filter `is_helpful=false`, `is_error=true`, `out_of_scope=true` |
| `GET /admin/ai/logs/flagged` | Review queue — unhelpful plus errored, deduplicated |

`knowledge-status` reports the state of **the worker that served the request**. The knowledge base is
an in-memory snapshot per process, so with several workers the answer can differ between calls, and
content added through the admin panel is not recommended until `POST /api/v1/ai/refresh-knowledge`
runs on each.

Log rows expose `in_scope`, `retrieved_doc_count`, and `retrieved_doc_types`, so you can see whether a
bad answer came from bad retrieval or bad generation.

---

## 4. Chat Oversight

Chat rooms were visible only to their participants — no admin access at all, which is both a
dispute-resolution and a compliance gap for a medical platform.

| Endpoint | Purpose |
|---|---|
| `GET /admin/chat/stats` | Rooms and messages, including last-24h volume |
| `GET /admin/chat/rooms` | Rooms with participants; filter `room_type`, `is_active`, `participant_id`, `consultation_id` |
| `GET /admin/chat/rooms/{id}/messages` | Full transcript, oldest first |
| `DELETE /admin/chat/messages/{id}` | Moderate a message; `reason` required |

Two deliberate constraints:

1. **Read-only.** Admins cannot post into a room.
2. **Transcript access is logged.** Every call to the transcript endpoint writes
   `admin_chat_transcript_accessed` with the room and the acting admin — reading a doctor/patient
   conversation is itself a sensitive action, so the access is auditable.

Deleted messages are soft-deleted with the reason, actor, and timestamp recorded on the row. Pass
`include_deleted=true` on the transcript to see them.

---

## 5. Audit Trail

Built from the `created_by` / `updated_by` / `deleted_by` columns `AuditMixin` already stamps on every
table. Covers 14 entity types: hospital, department, doctor, patient, hotel, apartment, restaurant,
package, treatment, booking, payment, consultation, lead, user.

| Endpoint | Purpose |
|---|---|
| `GET /admin/audit/entity-types` | Valid `entity_type` values |
| `GET /admin/audit` | Feed; filter `entity_type`, `entity_id`, `actor_id`, `action`, dates |
| `GET /admin/audit/entity/{type}/{id}` | History for one record |
| `GET /admin/audit/user/{actor_id}/summary?days=30` | What one user changed, by entity and action |

Each event resolves the actor's name, email, and role, and carries an `entity_label` (hotel name,
booking reference, …) so the feed reads without extra lookups.

### Known limits — read before relying on this

- **`updated_by` holds only the most recent editor.** Repeated edits collapse into a single `updated`
  event. This tells you who last touched a record, not the full history.
- **No before/after field values.** Real diffs need a dedicated audit table populated by a SQLAlchemy
  event listener. If compliance requires field-level history, that is the next step.
- **The feed is a `UNION ALL` across 14 tables × 3 actions.** Fine at current data volumes; if it
  slows down, add indexes on the `created_by` / `updated_by` / `deleted_by` columns, or narrow with
  `entity_type` which reduces it to a single table.

---

## 6. Notifications

### `POST /admin/notifications/broadcast`

```json
{
  "title": "Scheduled maintenance",
  "message": "The platform will be briefly unavailable on Sunday 02:00–03:00 IST.",
  "roles": ["patient", "doctor"],
  "action_url": "/status",
  "action_text": "See details"
}
```

Targets every **active, non-deleted** user holding those roles, or pass `user_ids` for an explicit
list. Records are created in the database and pushed over WebSocket to anyone connected.

**You must name an audience.** A request with neither `roles` nor `user_ids` is rejected — the API
will not message the entire platform because a field was omitted. All notifications are created in
one transaction, so a broadcast either lands or it does not.

| Endpoint | Purpose |
|---|---|
| `GET /admin/notifications` | All users' notifications; filter `user_id`, `type`, `is_read`, `search` |
| `GET /admin/notifications/stats` | Volume, read rate, last-24h count, breakdown by type |

---

## 6b. Treatment Proposals

`/admin/treatment-proposals` — who sent each proposal, the money involved, and the detail behind it.

**Read-only.** Proposals go straight from doctor to patient; there is no admin approval step. The
patient's `status` (`pending`, `approved`, `rejected`, `revision_requested`) is the only decision on
a proposal. Admins have visibility, not a gate.

### `GET /admin/treatment-proposals/stats`

Everything the dashboard needs in one call.

```json
{
  "total": 184,
  "by_status": { "pending": 32, "approved": 96, "rejected": 41, "revision_requested": 15 },
  "value_by_status": { "approved": 21400000.0, "pending": 6800000.0 },
  "awaiting_patient_response": 32,
  "accepted": 96,
  "rejected": 41,
  "revision_requested": 15,
  "acceptance_rate": 52.17,
  "total_proposed_value": 41250000.0,
  "accepted_value": 21400000.0,
  "pending_value": 6800000.0,
  "average_proposal_value": 224184.78,
  "largest_proposal_value": 1850000.0,
  "value_by_currency": { "INR": 39100000.0, "USD": 2150000.0 },
  "top_senders": [
    { "doctor_id": "…", "doctor_name": "Dr. Pranjel Pipara", "proposals_sent": 34, "total_value": 8900000.0 }
  ]
}
```

`pending_value` is the money in proposals the patient has not answered yet. `top_senders` answers
"who is sending these".

`GET /admin/insights/treatment-proposals` returns this same object — both endpoints call the same
code, so they cannot drift apart.

### `GET /admin/treatment-proposals`

| Param | Type | Description |
|---|---|---|
| `page`, `page_size` | int | Pagination (max 100) |
| `status` | string | Patient decision: `pending`, `approved`, `rejected`, `revision_requested` |
| `doctor_id` | UUID | Proposals sent by one doctor |
| `patient_id` | UUID | Proposals received by one patient |
| `hospital_id` | UUID | |
| `search` | string | Reference, treatment name, doctor or patient name/email |
| `min_amount`, `max_amount` | float | Budget range |
| `from_date`, `to_date` | date | Inclusive |
| `sort_by` | enum | `created_at` (default) · `amount` · `amount_asc` · `visit_date` |

Rows carry `doctor_name`, `doctor_specialization`, `patient_name`, `patient_email`, `hospital_name`,
`treatment_name`, `total_amount` + `currency`, `status`, `responded_at`, and `proposed_visit_date`.

### `GET /admin/treatment-proposals/{id}`

Full detail: the itemised cost breakdown (`consultation_fee`, `surgery_fee`, `hospital_stay_fee`,
`medications_fee`, `other_fees` + `other_fees_description`, `total_amount`), the doctor's
`description` and `doctor_notes`, `estimated_duration`, `proposed_visit_date` / `proposed_visit_time`,
and the patient's `patient_response_notes` and `responded_at`.

> The older `GET /treatment-proposals/admin/all` still works but is superseded — it has only a
> `status` filter and omits the payer/sender detail the dashboard needs.

### Admin approval removed

Proposals previously carried a second, platform-side decision (`admin_approved` / `admin_notes` /
`admin_reviewed_at`) and a review endpoint. That step is not required, so it is gone:

- `POST /admin/treatment-proposals/{id}/review` — **removed**
- `POST /treatment-proposals/admin/{id}/review` — **removed**
- `admin_approved`, `admin_notes`, `admin_reviewed_at` — **removed from all responses**
- `admin_approved` and `pending_review_only` filters — **removed**
- Stats fields `pending_admin_review` / `admin_approved` / `admin_rejected` / `pending_review_value`
  are replaced by `awaiting_patient_response` / `rejected` / `revision_requested` / `pending_value`

The database columns are still present but nothing reads or writes them, so historical values are not
lost. Drop them in a migration once you have confirmed you do not need them.

### Access control fix

`GET /treatment-proposals/{id}` (the shared, non-admin route) previously accepted `current_user` but
never checked it — **any authenticated user could read any proposal**, including another patient's
diagnosis and full cost breakdown. It now returns `403` unless the caller is the sending doctor, the
receiving patient, or an admin.

---

## 7. Events and Insights

| Endpoint | Purpose |
|---|---|
| `GET /admin/events` | Platform-wide calendar; filter `user_id`, `event_type`, `status`, `upcoming_only`, dates |
| `GET /admin/insights/favorites` | What patients save — totals by type plus the most-saved per type |
| `GET /admin/insights/treatment-proposals` | Proposal funnel: by status, awaiting admin review, acceptance rate, pipeline value |

`favorites` is a demand signal — what patients bookmark but may not have booked. `most_saved` resolves
names for doctors, hospitals, hotels, apartments, restaurants, and packages.

---

## Testing

37 tests in [tests/test_admin_monitoring.py](tests/test_admin_monitoring.py). They compile each query
against the Postgres dialect and assert on the generated SQL, so they run without a database and
still catch real filter mistakes — including the two that motivated this work:

```python
def test_admin_payment_list_is_not_scoped_to_one_user(): ...
def test_admin_consultation_list_needs_no_patient_or_doctor(): ...
```

Also covered: the refund over-limit guard, the broadcast audience guard, the audit `UNION` shape and
its unknown-entity rejection, and the JSON `in_scope` filter treating pre-existing rows (written
before the flag existed) as in-scope rather than as refusals.

---

## Source files

| Concern | File |
|---|---|
| Payments | [admin_payment.py](app/api/v1/admin_payment.py) · [payment_service.py](app/services/payment_service.py) |
| Consultations | [admin_consultation.py](app/api/v1/admin_consultation.py) · [consultation_service.py](app/services/consultation_service.py) |
| AI monitoring | [admin_ai.py](app/api/v1/admin_ai.py) · [ai_monitoring_service.py](app/services/ai_monitoring_service.py) |
| Chat oversight | [admin_chat.py](app/api/v1/admin_chat.py) · [admin_chat_service.py](app/services/admin_chat_service.py) |
| Audit trail | [admin_audit.py](app/api/v1/admin_audit.py) · [audit_service.py](app/services/audit_service.py) |
| Operations | [admin_ops.py](app/api/v1/admin_ops.py) · [admin_ops_service.py](app/services/admin_ops_service.py) |
| Schemas | [payment.py](app/schemas/payment.py) · [consultation.py](app/schemas/consultation.py) · [ai.py](app/schemas/ai.py) · [admin_chat.py](app/schemas/admin_chat.py) · [audit.py](app/schemas/audit.py) · [admin_ops.py](app/schemas/admin_ops.py) |
| Route registration | [api_router.py](app/api/v1/api_router.py) |
| Tests | [test_admin_monitoring.py](tests/test_admin_monitoring.py) |

---

## Still open

From the gap analysis, deliberately not built:

- **Field-level audit diffs.** Needs a dedicated table and event listeners — see the limits in §5.
- **System health beyond `/health`.** DB pool, worker, and background-job visibility is an
  infrastructure concern better served by your monitoring stack than by an API endpoint.
- **Structural cleanup** (§8 of the gap analysis): deprecating the duplicate `/admin/site/quotes*` and
  `/admin/site/contacts` routes, consolidating the scattered count endpoints, and fixing the duplicate
  `images.admin_router` registration. These change existing behaviour, so they need a frontend
  migration plan rather than being done silently.
