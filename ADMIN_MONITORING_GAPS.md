# Admin Platform Monitoring — Coverage Audit

What an admin can and cannot see today, and what is still needed to monitor the whole platform.

Audited by enumerating every registered route against every table in the schema. Findings below were
verified in the code, not inferred from naming.

---

## Summary

The admin surface is strong on **content and catalogue management** — hospitals, doctors, hotels,
apartments, restaurants, packages, CMS, RBAC, and leads are all well covered (roughly 280 admin
routes). It is weak on **operational monitoring**: money, live clinical activity, communications, and
system health.

The five blind spots that matter most:

| # | Gap | Why it matters | Effort |
|---|---|---|---|
| 1 | No admin view of payments | Cannot see any individual transaction, failure, or refund | S |
| 2 | Gateway transaction log unreachable | Nothing to debug a failed/disputed payment with | S |
| 3 | No global consultations view | Cannot see live clinical activity across the platform | S |
| 4 | No AI chatbot monitoring | Token spend and answer quality are invisible | M |
| 5 | No cross-entity audit trail | Cannot answer "who changed this price / deleted this doctor" | M |

Effort: **S** ≈ half a day, **M** ≈ 1–2 days, **L** ≈ 3+ days.

---

## 1. Payments — the largest gap

### What exists

Aggregate revenue only: `/admin/dashboard/revenue/stats` and the `revenue` block in
`/admin/dashboard/summary` give totals, monthly trends, and growth percentages.

### What is missing

**There is no admin endpoint that lists payments.** `GET /api/v1/payments` is not admin-scoped — it
passes `current_user.id` unconditionally:

```python
# app/api/v1/payments.py:101-109
payments, total = await service.get_list(
    PaginationParams(page=page, page_size=page_size),
    current_user.id,          # ← always the caller
    ...
)
```

An admin calling it sees **only their own payments**, which is normally none. So today nobody can
answer:

- Which payments failed in the last 24 hours, and why?
- Show me this customer's refund and its current state.
- Which bookings are marked confirmed but have no completed payment?
- Do our totals reconcile against the Razorpay settlement report?

`PaymentService.get_list()` already accepts `user_id: Optional[UUID] = None` and only filters when it
is set ([payment_service.py:35-50](app/services/payment_service.py#L35-L50)) — the capability is
built, just never exposed.

### Recommended

```
GET    /api/v1/admin/payments                    list all, filter status/method/gateway/date/user
GET    /api/v1/admin/payments/stats              counts + amounts by status, failure rate, refund rate
GET    /api/v1/admin/payments/{id}               full detail incl. gateway payload
GET    /api/v1/admin/payments/{id}/transactions  the gateway event trail (see §2)
POST   /api/v1/admin/payments/{id}/refund        admin-initiated refund with a reason
GET    /api/v1/admin/payments/reconciliation     completed payments vs booking totals, flag mismatches
```

Mostly a thin admin router over the existing service. **Effort: S.**

---

## 2. `payment_transactions` has no API at all

The table exists and models the gateway event trail — `authorization`, `capture`, `refund`, `void`,
with amount, status, and gateway response ([models/payment.py:184](app/models/payment.py#L184)).

**No endpoint anywhere reads it.** A `grep` for `PaymentTransaction` across `app/api/` returns
nothing. When a payment goes wrong, the one record that explains what happened is unreachable without
database access.

Fold this into §1 as `/admin/payments/{id}/transactions`. **Effort: S.**

---

## 3. Consultations and appointments — no global view

### Consultations

`GET /api/v1/consultations` branches on role, and an admin falls into the patient branch:

```python
# app/api/v1/consultations.py
if current_user.role == "doctor":
    ...doctor's consultations...
else:
    patient = await patient_service.get_by_user_id(current_user.id)
    if not patient:
        return PaginatedResponse.create([], 0, page, page_size)   # ← admins land here
```

An admin gets an **empty list**, silently. The only access is per-patient drill-down
(`/admin/patients/{id}/consultations`), which requires already knowing which patient to look at.

Missing: which consultations are scheduled today, which are in progress, which have been sitting in
`pending` unconfirmed, which doctors have no-showed, cancellation rates by doctor.

`/admin/dashboard/consultations/stats` gives counts but no list to act on.

### Appointments

Same shape. Only `/appointments/me` and `/admin/dashboard/appointments/today` (a count). No global
list, no filtering, no admin reschedule or cancel.

### Recommended

```
GET   /api/v1/admin/consultations              filter status/doctor/patient/date, incl. today & in-progress
GET   /api/v1/admin/consultations/{id}
PATCH /api/v1/admin/consultations/{id}/status  intervene on a stuck consultation
GET   /api/v1/admin/appointments               filter status/doctor/date
POST  /api/v1/admin/appointments/{id}/cancel   cancel on the patient's behalf
```

**Effort: S** for the read endpoints, **M** with intervention actions.

---

## 4. AI chatbot — no monitoring

`ai_logs` records tokens, cost, response time, and thumbs-up/down for every message. `ai_conversations`
records per-conversation totals. Nothing reads them in aggregate.

`AIStatsResponse` is **already defined** in [schemas/ai.py](app/schemas/ai.py) — total conversations,
tokens, cost, average response time, average rating, intent distribution — and is wired to no
endpoint. The only admin AI route is `POST /ai/refresh-knowledge`.

So there is no answer to: what is the chatbot costing per month, is spend trending up, which answers
were marked unhelpful, what are users actually asking, what is the error rate.

This matters more now that the assistant recommends hotels, apartments, and packages: nobody can see
whether those recommendations are landing, or whether the new scope gate is wrongly refusing real
questions. That last one is a silent failure — users just leave.

### Recommended

```
GET /api/v1/admin/ai/stats             fills the existing AIStatsResponse; date range + daily trend
GET /api/v1/admin/ai/conversations     all users' conversations, filter by rating/date/user
GET /api/v1/admin/ai/logs              individual messages, filter is_helpful=false, is_error=true
GET /api/v1/admin/ai/logs/flagged      unhelpful + errored, the review queue
GET /api/v1/admin/ai/knowledge-status  doc count by type, last rebuild time, staleness warning
```

The last one closes a real operational hole: the knowledge base is an in-memory singleton, so a hotel
added through the admin panel is not recommended until a rebuild runs. Right now there is no way to
tell whether it is stale.

Add an `out_of_scope` counter so a rising refusal rate is visible — that is the signal that
`RAG_SCOPE_THRESHOLD` needs lowering. **Effort: M.**

---

## 5. No cross-entity audit trail

Every table carries `created_by`, `updated_by`, `deleted_by`, and `deleted_at` via `AuditMixin`
([models/base.py:32](app/models/base.py#L32)). The data is being captured on every row.

There is no way to query it. `rbac_audit_logs` covers role and permission changes only. So there is no
answer to: who changed this hotel's price, who deleted that doctor, what did this manager touch last
week, what changed just before the complaint came in.

For a platform with external managers (hotel, apartment, restaurant) editing their own listings, this
is an accountability gap as much as a debugging one.

### Recommended

```
GET /api/v1/admin/audit                    unified feed: entity type, id, action, actor, timestamp
GET /api/v1/admin/audit/entity/{type}/{id} full history for one record
GET /api/v1/admin/audit/user/{user_id}     everything one actor changed
```

A read-only feed over the existing `created_by`/`updated_by`/`deleted_by` columns is cheap and covers
most of the need. Field-level before/after diffs would need a proper audit table and a SQLAlchemy
event listener — worth doing only if compliance requires it. **Effort: M** for the feed, **L** with
diffs.

---

## 6. Communications — chat, notifications, email

### Chat: no admin access

`chat_rooms`, `chat_messages`, `chat_participants` have **no admin endpoints**. Rooms are visible only
to participants. Admins cannot audit a doctor↔patient conversation to resolve a dispute, cannot see
which rooms are active, and cannot moderate abuse.

For a medical platform this is likely also a compliance requirement.

```
GET    /api/v1/admin/chat/rooms                 all rooms, filter active/participant/date
GET    /api/v1/admin/chat/rooms/{id}/messages   full transcript, read-only
GET    /api/v1/admin/chat/stats                 active rooms, message volume, response times
DELETE /api/v1/admin/chat/messages/{id}         moderate abusive content
```

**Effort: S.** Access should itself be audit-logged — reading patient conversations is sensitive.

### Notifications: read-only, per-user

Admins cannot send anything. No broadcast, no targeted announcement, no delivery visibility.

```
POST /api/v1/admin/notifications/broadcast   announce to a role or segment
GET  /api/v1/admin/notifications             all notifications, filter read/unread/type
GET  /api/v1/admin/notifications/stats       delivery and read rates
```

**Effort: S–M.**

### Email: covered, but not discoverable

`/api/v1/email/logs`, `/logs/{id}`, `/logs/{id}/resend`, and the template CRUD are **already
`RequireAdmin`** — this one is fine. It just does not live under `/admin/`, so it is easy to miss when
building the admin UI. A stats endpoint (bounce/failure rate over time) would help; the resend path
already exists.

---

## 7. Other gaps worth noting

| Area | Status | Note |
|---|---|---|
| **Events** | No admin scope | `/events` is per-user; no platform calendar |
| **Favorites** | No admin view | Useful demand signal — what patients are saving |
| **Documents** | Partial | `/documents/admin/all` and `/stats` exist; no per-user browse or moderation |
| **Treatment proposals** | Partial | `/admin/all` and `/{id}/review` exist; no stats or funnel view |
| **System health** | `/health` only | No DB pool, worker, or background-job visibility |
| **Bookings** | Good | `/admin/bookings/` + `/report/dashboard` cover this |
| **Users** | Good | `/api/v1/users*` is `RequireAdmin` — just outside `/admin/` |
| **Config** | Good | `/api/v1/config*` covers platform settings |

---

## 8. Structural cleanup (no new features)

These do not add capability but make the admin surface usable:

1. **The admin surface is scattered across eight prefixes** — `/admin/*`, `/users`, `/email`,
   `/config`, `/reviews/admin`, `/documents/admin`, `/treatment-proposals/admin`, `/cms/admin`. Users,
   email, and config are properly admin-gated but invisible to anyone building the UI from the
   `/admin` tree. Either move them or document the full list in one place.
2. **Duplicate quote and contact endpoints.** `/admin/site/quotes*` vs `/admin/quotes*`, and
   `/admin/site/contacts` vs `/admin/contacts`. The `site` versions are older and weaker. Mark them
   deprecated in OpenAPI and give the frontend a migration date.
3. **Count endpoints are duplicated across routers** — `/admin/hospitals/totaldoctors`,
   `/admin/departments/totaldoctors`, `/admin/doctors/assignments/doctorsassigned`, and
   `/admin/dashboard/doctors/totalregistered` all count doctors with slightly different filters. They
   will drift apart. Consolidate onto `/admin/dashboard/*` and deprecate the rest.
4. **Duplicate route registrations.** `images.admin_router` is mounted twice (at `/admin/images` and
   `/images`), and `/admin/rbac` has several methods registered twice on the same path — visible as
   duplicate-operation-id warnings when generating the OpenAPI schema.

---

## Suggested order

**Phase 1 — money and clinical operations (≈2–3 days)**
1. `/admin/payments` + transactions + reconciliation (§1, §2)
2. `/admin/consultations` and `/admin/appointments` (§3)

Rationale: these are the two areas where an admin currently cannot answer a question a customer is
actively asking them.

**Phase 2 — oversight (≈3–4 days)**
3. `/admin/ai/*` monitoring, including knowledge-base staleness (§4)
4. `/admin/chat/*` read-only access with its own audit logging (§6)
5. `/admin/audit` unified feed (§5)

**Phase 3 — polish (≈2 days)**
6. Notification broadcast (§6)
7. Events, favorites, proposals stats (§7)
8. Structural cleanup and deprecations (§8)

---

## Verification notes

Claims in this document were checked against the code rather than inferred:

- Admin payment visibility — traced `list_payments` → `PaymentService.get_list`, confirmed the
  `user_id` argument is always the caller.
- `PaymentTransaction` — `grep` across `app/api/` returns no usage.
- Admin consultation visibility — traced the role branch in `list_consultations` to the empty-list
  return for non-doctor, non-patient users.
- `AIStatsResponse` — `grep` outside `schemas/ai.py` returns only bytecode caches, no callers.
- Admin gating of `/users`, `/email`, `/config` — confirmed `RequireAdmin` on each route.
- Route inventory — enumerated from the live `app.routes` table, not from source reading.
