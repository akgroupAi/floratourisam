# Frontend Work Required

Everything the frontend needs after the backend changes in this cycle. Roughly 99 endpoints are new
or changed.

Read [§1 Breaking changes](#1-breaking-changes--do-these-first) first — those will break existing
screens whether or not you build anything new.

---

## Contents

1. [Breaking changes — do these first](#1-breaking-changes--do-these-first)
2. [Patient side](#2-patient-side)
3. [Admin side](#3-admin-side)
4. [Manager portal — entirely new](#4-manager-portal--entirely-new)
5. [Priority order](#5-priority-order)

---

## 1. Breaking changes — do these first

These affect screens you already have.

### 1.1 Prices went up 5%

Every payable booking now carries a **platform fee** charged on top of the subtotal. It is already
inside `total_price`, and exposed separately as `platform_fee` on:

- `POST /bookings/calculate-price` (the preview)
- `BookingResponse` (booking detail)

**Show it as its own line.** A total that silently jumps 5% at checkout generates refund requests.

```
Room 2 nights × ₹5,000     ₹10,000
Platform fee (5%)          ₹   500
─────────────────────────────────
Total                      ₹10,500
```

### 1.2 `page_size` is capped at 100 everywhere

Anything higher returns `422` with *"Page size must be at most 100."* This previously returned `500`
on some admin endpoints. If any call sends 200, change it and page instead.

### 1.3 Booking read and cancel now check ownership

`GET /bookings/{id}` and `POST /bookings/{id}/cancel` previously let **any** authenticated user read
or cancel **any** booking. Both now return **`404`** unless the caller is the owning patient, an
admin, or the property's manager.

`404` is deliberate — a `403` would confirm the booking exists. Treat 404 on these as "not yours or
gone", not as a bug.

### 1.4 Treatment proposals: admin approval removed

`admin_approved`, `admin_notes`, `admin_reviewed_at` are **gone from every response**, and both
review endpoints are removed. If any screen renders an "approval status" for a proposal, delete it —
the patient's `status` is now the only decision.

### 1.5 Quote documents were never fetchable

`quote.documents` holds server-side paths. Prefixing the API base gives `/apis/uploads/...` → `404`.
Use **`quote.document_urls`** with the auth header and a blob URL. Same pattern as §2.3.

---

## 2. Patient side

### 2.1 Cancel a booking — the full flow

```
GET  /bookings/{id}/refund-preview     what they get back, before confirming
POST /bookings/{id}/cancel             { "cancellation_reason": "..." }   required, 1–500 chars
GET  /bookings/{id}/refund-status      where the refund has got to
```

**Show the preview before they confirm.** The response carries a `lines` array ready to render as a
receipt — labelled rows, negative deductions, summing to the refund:

```
┌──────────────────────────────────────────────┐
│ Cancel booking HTL-2026-0142?                │
│ Booking total                    ₹ 10,500.00 │
│ Platform fee (non-refundable)    −    500.00 │
│ Cancellation charge (10%)        −  1,000.00 │
│ ──────────────────────────────────────────── │
│ You will be refunded              ₹ 9,000.00 │
│                                              │
│ Reason for cancelling *  [                 ] │
│        [ Keep booking ]  [ Cancel booking ]  │
└──────────────────────────────────────────────┘
```

Inside 48 hours the preview returns `refund_amount: 0` with a reason — show it plainly rather than
letting them discover it after cancelling.

### 2.2 Refund status on the booking / profile

`GET /bookings/{id}/refund-status` returns **ready-to-display wording**:

```json
{
  "status_label": "Refund being processed",
  "refund_amount": 9000.0,
  "is_refund_due": true,
  "message": "Your refund of INR 9,000.00 has been approved … 5-7 working days …",
  "expected_days": "5-7 working days",
  "reference": null
}
```

Use `status_label` and `message` directly — do not compose your own wording per screen. Every status
including "no refund due" has a message explaining why.

**Do not say "refunded" when status is `processed`.** It means issued, not arrived. `expected_days`
is there for exactly this.

### 2.3 Travellers and documents at booking time

Supply travellers inline on hotel, apartment, and package bookings:

```json
{ "room_id": "…", "guests": [
    {"full_name": "John Doe", "guest_type": "patient", "passport_number": "GB1234567"},
    {"full_name": "Jane Doe", "relationship_to_patient": "spouse"}
]}
```

Or afterwards:

```
GET/POST      /bookings/{id}/guests
PUT/DELETE    /bookings/{id}/guests/{guest_id}
GET/POST      /bookings/{id}/documents          multipart upload
GET/DELETE    /bookings/{id}/documents/{doc_id}
```

Document types: `passport`, `flight_ticket`, `visa`, `insurance`, `medical_report`, `id_proof`,
`other`. JPG/PNG/WebP/PDF, 10 MB, 25 per booking. Attach to a person with `guest_id`.

**Downloads need a blob, not `<a href>`** — the endpoint requires the `Authorization` header:

```js
const res = await fetch(`${API_BASE}${doc.download_url}`, {
  headers: { Authorization: `Bearer ${token}` },
});
window.open(URL.createObjectURL(await res.blob()));
```

Exactly one traveller may be `guest_type: "patient"`; the rest are `companion`. The patient cannot be
deleted from their own booking.

### 2.4 Booking timeline now attributes correctly

`GET /admin/bookings/{id}` returns a timeline whose `actor_name` is now the real person and role —
`"John Doe (Patient)"`, `"Priya Sharma (Admin)"`, `"(Property Manager)"`. It used to say "Admin" for
everything, including patient-initiated cancellations. Refund events appear in the timeline too.

---

## 3. Admin side

### 3.1 Refunds — the screen that does not exist yet

**This is the gap that matters.** The backend works; there is no UI.

```
GET  /admin/refunds                      the work queue, longest wait first
GET  /admin/refunds/stats                counts + pending_value + oldest_waiting_hours
POST /admin/refunds/{id}/approve         { } or { "amount": 10000 }   ← MOVES REAL MONEY
POST /admin/refunds/{id}/reject          { "reason": "..." }
GET  /admin/refunds/policy               the active rules, for a terms page
```

Build:

- A **queue table** ordered longest-waiting first, showing `waiting_hours`, patient, amount, reason
- **Approve** with a confirmation dialog naming the amount and stating it is irreversible, plus an
  optional amount override field
- **Reject** requiring a reason (it is emailed to the customer, so write it as quotable)
- A **sidebar badge** from `stats.pending`

`GET /admin/refunds` with no `status` returns `pending` **plus `failed`** — a gateway failure stays in
the queue for retry. Render `failed` distinctly with `refund_note` (the gateway error).

> Your current dashboard calls `/admin/refunds/stats` but not `/admin/refunds`. The rows come from the
> list endpoint — stats only gives counts, so an empty table with a non-zero badge means the list call
> is missing.

### 3.2 Everything else that has no UI

| Area | Endpoints | What it gives you |
|---|---|---|
| **Payments** | `/admin/payments` ×6 | The first admin view of any transaction. Previously impossible — the public endpoint scoped to the caller |
| **Consultations** | `/admin/consultations` ×4 | Previously returned an **empty list** for admins |
| **AI monitoring** | `/admin/ai` ×8 | Spend, cost/conversation, review queue, knowledge freshness |
| **Chat oversight** | `/admin/chat` ×4 | Read-only transcripts. **No composer** — admins cannot post. Show "viewing is logged" |
| **Audit trail** | `/admin/audit` ×4 | Who changed what. Embed as a History tab on detail pages |
| **Inventory** | `/admin/inventory` ×5 | Occupancy, alerts, bulk pricing. **Bulk ops default to dry run** — show the preview before applying |
| **Notifications** | `/admin/notifications` ×3 | Broadcast. Must name `roles` or `user_ids`, else `400` |
| **Insights** | `/admin/insights` ×2 | Saved-by-patients, proposal funnel |
| **Proposals** | `/admin/treatment-proposals` ×3 | Who sent, budget, top senders |
| **Quotes & contacts** | ×9 | Already documented |

Details in [ADMIN_MONITORING_API.md](ADMIN_MONITORING_API.md) and
[ADMIN_FRONTEND_IMPLEMENTATION.md](ADMIN_FRONTEND_IMPLEMENTATION.md).

---

## 4. Manager portal — entirely new

16 endpoints under `/manager`, none of which have a UI. Property managers currently cannot do routine
work without an admin.

```
GET  /manager/me/properties          hotels, apartments, restaurants I manage
GET  /manager/me/dashboard           arrivals, departures, in-house, revenue today
GET  /manager/rooms                  my room types
GET/PUT /manager/rooms/{id}/calendar rates, inventory, blocks
GET/PUT /manager/apartments/{id}/calendar
GET  /manager/bookings               + confirm / cancel
GET  /manager/reviews                + respond
GET  /manager/menu                   + PUT /menu/{id}/stock
GET  /manager/refunds                + approve / reject   ← managers can release refunds too
```

Everything is scoped: a manager sees only their own properties, enforced server-side.

**The portal is empty until managers are assigned** to properties via
`POST /admin/{type}/{id}/assign-manager`. An unassigned manager correctly sees nothing — which looks
broken if you are not expecting it.

Full spec: [MANAGER_PORTAL_API.md](MANAGER_PORTAL_API.md).

---

## 5. Priority order

**Blocking — customers are affected today**

1. **Platform fee line item** (§1.1) — prices already went up; showing it is not optional
2. **Cancel + refund preview + refund status** (§2.1, §2.2) — patients can cancel but see nothing back
3. **Admin refund queue** (§3.1) — money is owed and nobody can release it

**High value**

4. Admin payments and consultations (§3.2) — both were previously impossible to see
5. Travellers and documents (§2.3)
6. Manager portal (§4)

**Then**

7. AI monitoring, chat oversight, audit trail, inventory
8. Notifications, insights, proposals

Items 1–3 are the ones where the backend is live and the absence is visible to a customer or costing
you money. Everything else is capability nobody is waiting on yet.

---

## Reference docs

| Topic | Doc |
|---|---|
| Cancellation & refunds, end to end | [REFUND_POLICY.md](REFUND_POLICY.md) |
| Travellers & documents | [BOOKING_TRAVELLERS_API.md](BOOKING_TRAVELLERS_API.md) |
| Admin monitoring contract | [ADMIN_MONITORING_API.md](ADMIN_MONITORING_API.md) |
| Admin UI build guide | [ADMIN_FRONTEND_IMPLEMENTATION.md](ADMIN_FRONTEND_IMPLEMENTATION.md) |
| Manager portal | [MANAGER_PORTAL_API.md](MANAGER_PORTAL_API.md) |
| Rate & availability calendars | [ROOM_CALENDAR_API.md](ROOM_CALENDAR_API.md) |
| Admin email alerts | [ADMIN_EMAIL_ALERTS.md](ADMIN_EMAIL_ALERTS.md) |
| Quote requests | [QUOTE_REQUESTS_ADMIN_API.md](QUOTE_REQUESTS_ADMIN_API.md) |

Types can be generated rather than hand-written:

```bash
npx openapi-typescript https://floramedcare.com/apis/api/v1/openapi.json -o src/types/api.ts
```
