# Admin Panel — Frontend Implementation Guide

How to build the admin UI for the platform-monitoring endpoints. Written for whoever is implementing
the admin dashboard.

- API contract: [ADMIN_MONITORING_API.md](ADMIN_MONITORING_API.md)
- Why these exist: [ADMIN_MONITORING_GAPS.md](ADMIN_MONITORING_GAPS.md)

**Read [§10 Gotchas](#10-gotchas--read-this-before-you-start) first.** Each one will cost you an
afternoon if you find it the hard way.

---

## Contents

1. [Setup — API client and auth](#1-setup--api-client-and-auth)
2. [Navigation structure](#2-navigation-structure)
3. [Shared patterns](#3-shared-patterns)
4. [Payments](#4-payments)
5. [Consultations](#5-consultations)
6. [AI Chatbot](#6-ai-chatbot)
7. [Chat Oversight](#7-chat-oversight)
8. [Audit Trail](#8-audit-trail)
9. [Notifications, Events, Insights](#9-notifications-events-insights)
10. [Gotchas](#10-gotchas--read-this-before-you-start)
11. [TypeScript types](#11-typescript-types)
12. [Build order](#12-build-order)

---

## 1. Setup — API client and auth

Every endpoint needs `Authorization: Bearer <token>` and a role of `admin` or `super_admin`.
Non-admins get `403`.

```ts
// src/lib/adminApi.ts
const API_BASE = import.meta.env.VITE_API_BASE; // e.g. "https://floramedcare.com/apis"

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getToken()}`,
      ...init.headers,
    },
  });

  if (res.status === 401) {
    redirectToLogin();
    throw new ApiError(401, "Session expired");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? `Request failed (${res.status})`);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export const adminApi = {
  get:   <T>(path: string, params?: Record<string, unknown>) =>
           request<T>(`${path}${toQuery(params)}`),
  post:  <T>(path: string, body?: unknown) =>
           request<T>(path, { method: "POST", body: JSON.stringify(body ?? {}) }),
  patch: <T>(path: string, body?: unknown) =>
           request<T>(path, { method: "PATCH", body: JSON.stringify(body ?? {}) }),
  del:   <T>(path: string, body?: unknown) =>
           request<T>(path, { method: "DELETE", body: JSON.stringify(body ?? {}) }),
};

// Drops undefined/null/"" so empty filter inputs don't become `?status=`
function toQuery(params?: Record<string, unknown>): string {
  if (!params) return "";
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") q.append(k, String(v));
  }
  const s = q.toString();
  return s ? `?${s}` : "";
}
```

> `DELETE /admin/chat/messages/{id}` takes a JSON body (the moderation reason). That is why `del`
> accepts one.

---

## 2. Navigation structure

Suggested sidebar. Existing sections omitted.

```
Dashboard
Operations
  ├── Payments            → /admin/payments        ⚠️ badge: failed count
  ├── Consultations       → /admin/consultations   ⚠️ badge: overdue_pending
  ├── Bookings                (already built)
  └── Reconciliation      → /admin/payments/reconciliation
Communications
  ├── Chat Oversight      → /admin/chat
  ├── Notifications       → /admin/notifications
  └── Contact Messages        (already built)
AI Assistant
  ├── Overview            → /admin/ai
  ├── Conversations       → /admin/ai/conversations
  └── Review Queue        → /admin/ai/flagged      ⚠️ badge: unhelpful count
Insights
  ├── Audit Trail         → /admin/audit
  ├── Calendar            → /admin/events
  ├── Saved by Patients   → /admin/insights/favorites
  └── Proposal Funnel     → /admin/insights/proposals
```

**Sidebar badges** — poll these three on an interval (60s is plenty) and show a count when non-zero:

| Badge | Source | Field |
|---|---|---|
| Failed payments | `GET /admin/payments/stats` | `failed_payments` |
| Stuck consultations | `GET /admin/consultations/stats` | `overdue_pending` |
| AI review queue | `GET /admin/ai/stats` | `unhelpful_count` |

---

## 3. Shared patterns

### Pagination envelope

Every list endpoint returns the same shape:

```ts
interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}
```

Build one `<DataTable>` around it and reuse it everywhere. **`page_size` max is 100 on every
endpoint** — no exceptions. Requesting more returns `422`. For long chat transcripts, page through
at 100 rather than asking for a bigger page.

### Filter bar

All list endpoints share the same filter conventions:

- `search` — free text, always debounce ~300ms
- `from_date` / `to_date` — `YYYY-MM-DD`, **`to_date` is inclusive**
- Boolean shortcuts (`failed_only`, `today_only`, `active_only`, …) — render as toggle chips, not
  dropdowns; they are the one-click triage paths
- Reset page to 1 whenever any filter changes

Put filters in the URL query string so a filtered view can be shared and survives a refresh.

### Stat tiles

Every section has a `/stats` endpoint meant to render as a row of tiles above the table. Fetch stats
and the first page in parallel — do not chain them.

### States to handle on every screen

| State | Treatment |
|---|---|
| Loading | Skeleton rows, keep the filter bar interactive |
| Empty (no data yet) | "No payments recorded yet" — neutral |
| Empty (filters exclude everything) | "No results match these filters" + a Clear filters button |
| Error | Message from `ApiError.detail`, plus Retry |
| 403 | "You do not have permission" — do not show a retry |

The two empty states are different and users notice. Distinguish them by whether any filter is active.

---

## 4. Payments

### 4.1 Payments list — `/admin/payments`

`GET /admin/payments`

**Stat tiles** from `GET /admin/payments/stats`:

| Tile | Field | Note |
|---|---|---|
| Net revenue | `net_revenue` | Headline figure |
| Total revenue | `total_revenue` | |
| Refunded | `total_refunded` | Red when non-zero |
| Success rate | `success_rate` | Percentage |
| Failed | `failed_payments` | Red; click → sets `failed_only=true` |
| Pending | `pending_payments` | Amber |

**Table columns:**

| Column | Field | Rendering |
|---|---|---|
| Reference | `reference_number` | Monospace; links to detail |
| Payer | `user_name` / `user_email` | Two lines; fall back to email if name is null |
| Amount | `amount` + `currency` | Right-aligned. **Format per `currency`, do not assume INR** |
| Method | `payment_method` | |
| Gateway | `gateway` | |
| Status | `status` | Badge — see colours below |
| Booking | `booking_type` + `entity_name` | "Hotel · Grand Care Hotel" |
| Date | `initiated_at` | Relative under 24h, else absolute |

**Status badge colours:** `completed` green · `pending` amber · `processing` blue · `failed` red ·
`refunded` grey · `partially_refunded` grey with a "partial" suffix.

When `is_refunded` is true, show a refund chip with `refund_amount` even if `status` still reads
`completed` — a partial refund keeps the payment otherwise normal.

**Filters:** `status`, `payment_method`, `gateway`, `booking_type`, `search`, `from_date`, `to_date`,
plus `failed_only` and `refunded_only` toggles.

### 4.2 Payment detail — `/admin/payments/:id`

Two panels side by side.

**Left — payment record** (`GET /admin/payments/{id}`): amount and fee breakdown
(`processing_fee`, `platform_fee`, `net_amount`), gateway ids, card `card_brand` + `card_last_four`,
and timestamps. When `failure_reason` is present, show it in a red callout at the top — that is why
the admin opened this page.

**Right — gateway trail** (`GET /admin/payments/{id}/transactions`): a vertical timeline, oldest
first. Each entry shows `transaction_type` (`authorization` / `capture` / `refund` / `void`),
`amount`, `status`, and `error_code` + `error_message` when present. Render `gateway_response` in a
collapsed `<details>` — it is raw and long, but it is the thing that explains a dispute.

Empty trail is normal for older payments. Say "No gateway events recorded", not an error.

### 4.3 Refund dialog

`POST /admin/payments/{id}/refund` with `{ amount?, reason }`.

```
┌──────────────────────────────────────────────┐
│ Record a refund                              │
│                                              │
│ ⚠️ This records a refund in Flora Medical.   │
│    It does NOT move money. Issue the refund  │
│    in Razorpay first, then record it here.   │
│                                              │
│ Payment total      INR 5,000.00              │
│ Already refunded   INR 1,500.00              │
│ Refundable         INR 3,500.00              │
│                                              │
│ ( ) Full refund — INR 3,500.00               │
│ (•) Partial       [ 1200.00        ]         │
│                                              │
│ Reason * [                          ]        │
│                                              │
│              [ Cancel ] [ Record refund ]    │
└──────────────────────────────────────────────┘
```

That warning is not optional. An admin who thinks this button moves money will leave customers
unrefunded.

- `reason` is required, min 3 chars
- Omit `amount` for a full refund
- Over-refunding returns `400` with a message naming the remaining balance — show it inline on the
  amount field, not as a toast

### 4.4 Reconciliation — `/admin/payments/reconciliation`

`GET /admin/payments/reconciliation?limit=100`

Header: `bookings_checked`, `mismatch_count`, `orphaned_payments`. When `mismatch_count` is 0, show a
green all-clear state rather than an empty table.

Table of `mismatches`, with `issue` rendered as a plain-language label:

| `issue` | Label | Colour |
|---|---|---|
| `marked_paid_without_payment` | Marked paid, no payment found | Red |
| `amount_mismatch` | Amount does not match | Amber |
| `paid_but_not_marked` | Paid but not marked as paid | Blue |

Show `booking_total`, `amount_paid`, and `difference` (signed — negative means underpaid). Link the
booking reference to the booking detail page.

---

## 5. Consultations

### 5.1 List — `/admin/consultations`

`GET /admin/consultations`

**Stat tiles** from `/admin/consultations/stats`: Today · In progress · Pending · **Overdue pending**
(red, click → `unconfirmed_only=true`) · Unpaid · Completion rate · No-show rate.

`overdue_pending` is the actionable one: still `pending` though the slot has passed. Make it
prominent.

**Table columns:** Reference · Patient (`patient_name`) · Doctor (`doctor_name` + `doctor_title`,
`doctor_specialization` underneath) · Hospital (`hospital_name`) · Type (`consultation_type` — icon
for video/chat/in-person) · Scheduled (`scheduled_at`) · Status badge · Paid (`is_paid` tick/cross) ·
Fee.

**Status colours:** `pending` amber · `scheduled` blue · `waiting` / `in_progress` green pulsing ·
`completed` grey · `cancelled` red · `missed` dark red.

**Filter toggles that matter:** `today_only`, `active_only` (live right now), `unconfirmed_only`.
Plus `status`, `consultation_type`, `doctor_id`, `patient_id`, `hospital_id`, `is_paid`, `search`,
date range.

If `meet_link` is present on a `waiting` / `in_progress` row, show a Join button — that is how an
admin steps into a call that is going wrong.

### 5.2 Detail and actions

`GET /admin/consultations/{id}` for the record.

**Change status** — `PATCH /admin/consultations/{id}/status` with `{ status, notes? }`.

The backend enforces the state machine. An invalid transition returns `400` with a message listing
what *is* allowed, e.g. `Invalid transition: completed → pending. Allowed: ...`. Two options, pick
one:

- Simple: send it, and render the `400` message inline.
- Better: on load, disable status options the current state cannot reach, so the error is unreachable.

**Cancel** — `POST /admin/consultations/{id}/cancel` with `{ cancellation_reason }`. Field name is
`cancellation_reason`, not `reason`. Warn in the dialog that this also cancels the linked booking,
because it does.

---

## 6. AI Chatbot

### 6.1 Overview — `/admin/ai`

`GET /admin/ai/stats` (accepts `from_date` / `to_date` — offer 7d / 30d / 90d presets).

**Tiles:** Total cost (`total_cost`, 4dp — values are small) · Conversations · Messages · Cost per
conversation · Avg response time (`average_response_time_ms`) · Satisfaction rate · Error rate ·
**Out-of-scope rate**.

**Give `out_of_scope_rate` its own explained tile.** It is the percentage of questions the bot refused
as off-topic. Some refusals are correct. A *rising* number means the scope gate is turning away real
questions — and those users just leave, so nothing else surfaces it. Add a tooltip:

> Questions the assistant declined as off-topic. If this climbs, `RAG_SCOPE_THRESHOLD` may be too
> strict — check the review queue for wrongly refused questions.

**Charts** from `GET /admin/ai/usage/daily?days=30` — one line/bar per day. Plot cost and messages on
separate axes; they differ by orders of magnitude.

**Top questions** from `GET /admin/ai/questions/top?limit=20&days=30` — a simple ranked list. This is
the input for deciding which knowledge documents to write next.

### 6.2 Knowledge status panel

`GET /admin/ai/knowledge-status`

Show `documents_by_type` as a breakdown (doctors, hospitals, hotels, apartments, restaurants,
packages, pages…), plus `chat_model`, `embedding_model`, `rag_top_k`, `similarity_threshold`,
`scope_threshold`.

Two required behaviours:

1. When `is_built` is false, show the `warning` field as an amber banner.
2. Always render the `note` field. It explains that the index is per-worker and stale until a rebuild.

Add a **Rebuild knowledge base** button wired to the existing `POST /api/v1/ai/refresh-knowledge`. It
can take a while on a large catalogue — disable it and show a spinner while it runs.

> With multiple workers this endpoint reports whichever worker answered, so consecutive calls may
> disagree. Say so in the UI rather than letting an admin think the numbers are flickering randomly.

### 6.3 Conversations and review queue

**List** — `GET /admin/ai/conversations`. Columns: Title · User · Messages · Tokens · Cost · Rating
(stars, null = unrated) · Started. Filters: `user_id`, `context_type`, `rating`, `search`, dates.

**Transcript** — `GET /admin/ai/conversations/{id}` returns paginated `AdminAILogResponse` rows.
Render as a chat thread: `user_message` right, `ai_response` left as markdown.

Per exchange, show a small metadata strip: `total_tokens`, `response_time_ms`, `retrieved_doc_count`,
and `retrieved_doc_types`. That strip is the debugging tool — it tells you whether a bad answer came
from bad retrieval (0 docs, or the wrong types) or from bad generation (good docs, bad answer).

Flag rows where `in_scope` is false with an "Off-topic — declined" chip.

**Review queue** — `GET /admin/ai/logs/flagged`. Unhelpful plus errored answers, deduplicated and
newest first. For each, show the question, the answer, the user's `feedback` text, and the retrieval
metadata. This is a work queue, so give each row a "mark handled" affordance in local state even
though the API has no such field yet.

`GET /admin/ai/logs` is the general-purpose search across all exchanges, with
`is_helpful` / `is_error` / `out_of_scope` filters.

---

## 7. Chat Oversight

Doctor↔patient conversations. Treat this section as sensitive by default.

### 7.1 Rooms — `/admin/chat`

`GET /admin/chat/stats` tiles: Total rooms · Active · Active last 24h · Messages · Messages last 24h ·
Avg messages per room.

`GET /admin/chat/rooms` table: Room (`name`) · Type · **Participants** (render as avatar chips from
the `participants` array — each has `name`, `email`, `role`) · Messages (`message_count`) · Last
activity (`last_message_at`) · Active.

Filters: `room_type`, `is_active`, `participant_id`, `consultation_id`, `search`, dates.

### 7.2 Transcript — `/admin/chat/rooms/:id/messages`

`GET /admin/chat/rooms/{id}/messages` — oldest first, `page_size` up to 100. Long conversations need
paging; consider loading page 1 and fetching older pages on scroll.

Render as a read-only thread grouped by `sender_role`, with sender name and role on each message.
Handle `message_type` — `file` messages carry `file_url` / `file_name` instead of text.

**Three things this screen must do:**

1. **No composer.** Admins cannot post. Do not render a disabled input either; render nothing, so
   there is no implication that posting is possible.
2. **Show an access banner:** "Viewing this transcript is logged." The backend writes
   `admin_chat_transcript_accessed` with the room and the acting admin on every call. Telling the
   admin this is the honest thing to do, and it discourages idle browsing of patient conversations.
3. **`include_deleted` toggle** — off by default. When on, moderated messages appear with
   `is_deleted: true`; render them struck through and greyed.

### 7.3 Moderation

`DELETE /admin/chat/messages/{id}` with `{ reason }` in the body — required, min 3 chars.

Confirm before sending. Explain in the dialog that the message is hidden from participants but
retained with the reason and the acting admin recorded, so the moderation itself stays auditable.

---

## 8. Audit Trail

`/admin/audit`

`GET /admin/audit/entity-types` populates the entity filter (14 types). Fetch once and cache.

`GET /admin/audit` returns a chronological feed. Render as a timeline, not a table — it reads better:

```
● 10 Aug, 14:32   Priya Sharma (admin)
  updated  Hotel · Grand Care Hotel

● 10 Aug, 14:18   Rahul Mehta (hotel_manager)
  created  Hotel · Seaside Residency
```

Fields: `actor_name` + `actor_role`, `action` (`created` / `updated` / `deleted`), `entity_type`,
`entity_label`, `occurred_at`. Colour by action: created green, updated blue, deleted red.

Link `entity_type` + `entity_id` to that record's admin page where one exists.

**Two views to provide:**

- Record history — `GET /admin/audit/entity/{type}/{id}`. Embed this as a "History" tab on hotel,
  doctor, booking, and payment detail pages.
- User activity — `GET /admin/audit/user/{actor_id}/summary?days=30`. Returns counts, not events:
  `by_entity_type` (nested `{entity: {action: count}}`) and `by_action`. Render as a small matrix.
  Most useful for reviewing what an external manager has been touching.

**Surface the limits in the UI.** Put a one-line note at the top of the feed:

> Shows who created, last updated, or deleted a record. Repeated edits appear once — only the most
> recent editor is stored — and field-level changes are not tracked.

Without that, someone will read a single `updated` event as "this was edited once" and be wrong.

---

## 9. Notifications, Events, Insights

### 9.1 Broadcast — `/admin/notifications`

`POST /admin/notifications/broadcast`

```ts
{
  title: string;              // 1–255
  message: string;            // 1–2000
  roles?: string[];           // e.g. ["patient", "doctor"]
  user_ids?: string[];
  notification_type?: string; // default "system"
  action_url?: string;
  action_text?: string;
}
```

**One of `roles` or `user_ids` is mandatory.** Sending neither returns `400`; the API refuses to
message the whole platform because a field was left empty. Mirror that in the form: disable the send
button until an audience is chosen.

Before sending, show a confirmation naming the audience — "This will notify all users with role
`patient`." Response returns `recipients_targeted` and `notifications_created`; show it as a toast.

`GET /admin/notifications` lists everything sent (filters: `user_id`, `notification_type`, `is_read`,
`search`). `GET /admin/notifications/stats` gives volume and `read_rate` — a low read rate is the
signal that broadcasts are being ignored.

### 9.2 Calendar — `/admin/events`

`GET /admin/events`. Table or month view. `upcoming_only=true` sorts soonest-first; without it,
newest-first. Show `title`, `user_name`, `event_type`, `start_time`, `status`, and `meeting_url` as a
join link when present.

### 9.3 Insights

**Saved by patients** — `GET /admin/insights/favorites?limit=10`. `by_entity_type` as a donut;
`most_saved` is `{ entity_type: [{ entity_id, name, saved_count }] }` — render one ranked list per
type. This is demand, not bookings: what patients bookmark but may not have paid for.

**Proposal funnel** — `GET /admin/insights/treatment-proposals` is the small summary. For the full
proposal dashboard use `/admin/treatment-proposals/*` — see §9.4.

### 9.4 Treatment proposals — `/admin/proposals`

**Read-only.** Proposals go straight from doctor to patient — there is no admin approval step, and no
review action to build. The admin screen is for visibility: who sent what, to whom, for how much.

The only decision on a proposal is the patient's `status`: `pending` · `approved` · `rejected` ·
`revision_requested`.

**Stat tiles** from `GET /admin/treatment-proposals/stats`:

| Tile | Field | Note |
|---|---|---|
| Total proposed | `total_proposed_value` | Headline pipeline figure |
| Accepted value | `accepted_value` | |
| Awaiting response | `awaiting_patient_response` | Sent, patient has not answered |
| Value awaiting response | `pending_value` | Money still in play |
| Acceptance rate | `acceptance_rate` | |
| Average proposal | `average_proposal_value` | |

Plus **Top senders** from `top_senders` — doctor name, `proposals_sent`, `total_value`. That is the
"who is sending these" panel. And `value_by_currency` — do not sum across currencies into one figure.

**Table** — `GET /admin/treatment-proposals`. Columns: Reference · Treatment (`treatment_name`) ·
Sent by (`doctor_name` + `doctor_specialization`) · Patient (`patient_name` / `patient_email`) ·
Hospital · Budget (`total_amount` + `currency`, right-aligned) · Status · Visit date ·
Sent (`created_at`).

Filters: `status`, `doctor_id`, `patient_id`, `hospital_id`, `search`, `min_amount` / `max_amount`,
date range, and `sort_by` (`created_at` · `amount` · `amount_asc` · `visit_date`). Sorting by
`amount` surfaces the big-ticket proposals first.

**Detail** — `GET /admin/treatment-proposals/{id}`. Lead with the itemised cost breakdown as a table
that sums to `total_amount`:

```
Consultation      INR   5,000
Surgery           INR 380,000
Hospital stay     INR  55,000
Medications       INR   8,000
Other             INR   2,000   (physiotherapy — 4 sessions)
─────────────────────────────
Total             INR 450,000
```

Then the doctor's `description` and `doctor_notes`, `estimated_duration`, proposed visit date/time,
and the patient's response (`patient_response_notes`, `responded_at`).

No action buttons on this screen — there is nothing for an admin to approve.

---

## 10. Gotchas — read this before you start

**1. Refunds do not move money.** `POST /admin/payments/{id}/refund` records a refund in our database
only. The gateway refund is a separate manual step in Razorpay. If the UI implies otherwise, admins
will leave customers unrefunded. The warning text in §4.3 is required, not decorative.

**2. Quote documents need a blob download, not an `<a href>`.** `quote.documents` holds server-side
filesystem paths that are **not** browser-reachable — prefixing the API base gives you
`/apis/uploads/...` and a `404`. Use `quote.document_urls` and fetch with the auth header:

```ts
const res = await fetch(`${API_BASE}${quote.document_urls[0]}`, {
  headers: { Authorization: `Bearer ${token}` },
});
if (!res.ok) throw new Error(`Download failed: ${res.status}`);
const url = URL.createObjectURL(await res.blob());
window.open(url);
// URL.revokeObjectURL(url) when done
```

This applies to any authenticated file endpoint, not just quotes.

**3. Consultation status transitions are validated.** The state machine rejects invalid moves with
`400` and a message listing what is allowed. Either surface that message or disable impossible
options up front.

**4. AI knowledge status is per-worker.** `GET /admin/ai/knowledge-status` reports the worker that
answered. With several workers, two calls can legitimately disagree. Do not treat the difference as a
bug, and do not cache the result aggressively.

**5. `to_date` is inclusive.** The backend adds a day internally. Passing `to_date=2026-08-10`
includes everything on 10 August. Do not add a day yourself — you will double-count.

**6. `page_size` is capped at 100 everywhere.** An earlier draft of this guide said chat transcripts
and the audit feed accepted 200 — they did not, and requesting 200 returned a `500`. That is fixed;
the ceiling is now a uniform 100 and anything higher returns a clean `422`. Page through long
transcripts instead.

**Smaller ones:**

- Format money by the row's `currency` field. Multi-currency data exists; hardcoding ₹ will be wrong.
- `user_name` is nullable across every list. Fall back to `user_email`, then to "Unknown".
- `satisfaction_rate` and `average_rating` are `null` when nothing has been rated — render "—", not 0%.
- `in_scope` defaults to `true` on older AI logs written before the field existed. Absence is not a
  refusal.
- Chat `participants` can be empty if users were deleted. Do not assume at least two.
- Costs are small (`0.0148`). Use 4 decimal places or the whole AI section reads as zero.

---

## 11. TypeScript types

Generated from the live OpenAPI schema. `T | null` reflects genuinely nullable fields.

```ts
export interface Paginated<T> {
  items: T[]; total: number; page: number; page_size: number; pages: number;
}

// ── Payments ────────────────────────────────────────────────
export interface AdminPayment {
  id: string;
  reference_number: string;
  booking_id: string | null;
  amount: number;
  currency: string;
  payment_method: string;
  status: "pending" | "processing" | "completed" | "failed" | "refunded" | "partially_refunded";
  initiated_at: string;
  completed_at: string | null;
  is_refunded: boolean;
  booking_type: string | null;
  entity_name: string | null;
  user_id: string;
  user_name: string | null;
  user_email: string | null;
  gateway: string | null;
  gateway_transaction_id: string | null;
  refund_amount: number | null;
  failure_reason: string | null;
}

export interface AdminPaymentStats {
  total_payments: number; successful_payments: number; failed_payments: number;
  pending_payments: number; refunded_payments: number;
  total_revenue: number; total_refunded: number; net_revenue: number;
  success_rate: number; failure_rate: number;
  payments_by_method: Record<string, number>;
  payments_by_status: Record<string, number>;
  revenue_by_currency: Record<string, number>;
}

export interface PaymentTransaction {
  id: string; payment_id: string;
  transaction_type: "authorization" | "capture" | "refund" | "void";
  amount: number; currency: string; status: string;
  gateway_transaction_id: string | null;
  error_code: string | null; error_message: string | null;
  created_at: string;
}

export interface ReconciliationMismatch {
  booking_id: string;
  reference_number: string | null;
  booking_type: string | null;
  booking_status: string | null;
  booking_total: number; amount_paid: number; difference: number;
  issue: "marked_paid_without_payment" | "amount_mismatch" | "paid_but_not_marked";
}

export interface ReconciliationResponse {
  bookings_checked: number; mismatch_count: number;
  orphaned_payments: number; mismatches: ReconciliationMismatch[];
}

// ── Consultations ───────────────────────────────────────────
export interface AdminConsultationStats {
  total: number; today: number; pending: number; scheduled: number;
  in_progress: number; completed: number; cancelled: number; missed: number;
  unpaid: number; overdue_pending: number;
  completion_rate: number; cancellation_rate: number; no_show_rate: number;
  by_status: Record<string, number>; by_type: Record<string, number>;
}

// ── AI ──────────────────────────────────────────────────────
export interface AdminAIStats {
  total_conversations: number; total_messages: number;
  total_tokens_used: number; total_cost: number;
  average_response_time_ms: number;
  average_rating: number | null;
  error_count: number; error_rate: number;
  helpful_count: number; unhelpful_count: number;
  satisfaction_rate: number | null;
  out_of_scope_count: number; out_of_scope_rate: number;
  cost_per_conversation: number;
  intents_distribution: Record<string, number>;
  conversations_by_context: Record<string, number>;
  messages_by_model: Record<string, number>;
}

export interface AdminAILog {
  id: string;
  conversation_id: string | null;
  user_id: string | null; user_name: string | null; user_email: string | null;
  user_message: string;
  ai_response: string | null;
  model_name: string | null;
  total_tokens: number; cost: number; response_time_ms: number;
  is_error: boolean; error_message: string | null;
  is_helpful: boolean | null; feedback: string | null;
  in_scope: boolean;
  retrieved_doc_count: number;
  retrieved_doc_types: string[];
  created_at: string;
}

export interface AIKnowledgeStatus {
  is_built: boolean;
  total_documents: number;
  documents_by_type: Record<string, number>;
  embedding_model: string; chat_model: string;
  rag_top_k: number; similarity_threshold: number; scope_threshold: number;
  warning: string | null;
  note: string;
}

// ── Chat ────────────────────────────────────────────────────
export interface ChatParticipant {
  user_id: string; name: string | null; email: string | null; role: string | null;
}

export interface AdminChatRoom {
  id: string; name: string | null; room_type: string | null;
  consultation_id: string | null;
  is_active: boolean; message_count: number;
  last_message_at: string | null; closed_at: string | null;
  participants: ChatParticipant[];
  created_at: string;
}

export interface AdminChatMessage {
  id: string; room_id: string;
  sender_id: string | null; sender_name: string | null;
  sender_email: string | null; sender_role: string | null;
  message_type: string | null; content: string | null;
  file_url: string | null; file_name: string | null;
  is_edited: boolean; is_deleted: boolean;
  created_at: string;
}

// ── Audit ───────────────────────────────────────────────────
export interface AuditEvent {
  entity_type: string; entity_id: string; entity_label: string | null;
  action: "created" | "updated" | "deleted";
  actor_id: string | null; actor_name: string | null;
  actor_email: string | null; actor_role: string | null;
  occurred_at: string;
}

export interface AuditActorSummary {
  actor_id: string; days: number; total_actions: number;
  by_entity_type: Record<string, Record<string, number>>;
  by_action: Record<string, number>;
}

// ── Ops ─────────────────────────────────────────────────────
export interface BroadcastRequest {
  title: string; message: string;
  roles?: string[]; user_ids?: string[];
  notification_type?: string;
  action_url?: string; action_text?: string;
}

export interface FavoriteEntry { entity_id: string; name: string | null; saved_count: number; }

export interface FavoriteStats {
  total_favorites: number; patients_with_favorites: number;
  by_entity_type: Record<string, number>;
  most_saved: Record<string, FavoriteEntry[]>;
}

export interface ProposalTopSender {
  doctor_id: string; doctor_name: string | null;
  proposals_sent: number; total_value: number;
}

export interface ProposalStats {
  total: number;
  by_status: Record<string, number>;
  value_by_status: Record<string, number>;
  awaiting_patient_response: number;
  accepted: number; rejected: number; revision_requested: number;
  acceptance_rate: number;
  total_proposed_value: number; accepted_value: number; pending_value: number;
  average_proposal_value: number; largest_proposal_value: number;
  value_by_currency: Record<string, number>;
  top_senders: ProposalTopSender[];
}

export interface AdminProposal {
  id: string; reference_number: string;
  consultation_id: string | null;
  doctor_id: string; doctor_name: string | null; doctor_specialization: string | null;
  patient_id: string; patient_name: string | null; patient_email: string | null;
  hospital_id: string | null; hospital_name: string | null;
  treatment_name: string;
  currency: string; total_amount: number;
  status: "pending" | "approved" | "rejected" | "revision_requested";
  responded_at: string | null;
  proposed_visit_date: string | null;
  created_at: string; updated_at: string | null;
}
```

> Rather than maintaining these by hand, generate them:
> `npx openapi-typescript https://floramedcare.com/apis/api/v1/openapi.json -o src/types/api.ts`

---

## 12. Build order

Ordered by how much each unblocks someone doing their job today.

**Phase 1 — the two screens people are currently blocked on**
1. Payments list + stat tiles
2. Payment detail + gateway transaction trail
3. Refund dialog (with the warning)
4. Consultations list + stat tiles
5. Consultation detail + status/cancel actions

Until these exist, an admin cannot answer "did this payment fail?" or "what is happening today?" at
all.

**Phase 2 — oversight**
6. AI overview, charts, knowledge status
7. AI conversations + review queue
8. Chat rooms + transcript (read-only, with the access banner)
9. Audit feed + the History tab on existing detail pages

**Phase 3 — the rest**
10. Reconciliation
11. Notification broadcast + list
12. Calendar, favorites, proposal funnel
13. Sidebar badges wired to the three stats endpoints

**Reusable pieces to build first**, before any screen: `<DataTable>` over `Paginated<T>`,
`<FilterBar>` with URL sync, `<StatTile>`, `<StatusBadge>`, `<Money>` (currency-aware),
`<UserCell>` (name/email fallback), `<EmptyState>` (distinguishing no-data from no-results).

Getting those eight right first makes every screen in Phases 1–3 largely assembly.
