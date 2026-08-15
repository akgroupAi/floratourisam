# Cancellation & Refunds — How It Works

The 48-hour policy, the cancellation charge, and the admin-approved Razorpay refund queue —
end to end, with worked examples.

Base URL: `/api/v1`

---

## Contents

1. [The policy](#1-the-policy)
2. [End-to-end flow](#2-end-to-end-flow)
3. [Step 1 — patient previews the refund](#3-step-1--patient-previews-the-refund)
4. [Step 2 — patient cancels with a reason](#4-step-2--patient-cancels-with-a-reason)
5. [Step 3 — admin sees the queue](#5-step-3--admin-sees-the-queue)
6. [Step 4 — admin approves](#6-step-4--admin-approves)
7. [What Razorpay actually does](#7-what-razorpay-actually-does)
8. [Rejecting a refund](#8-rejecting-a-refund)
9. [When things go wrong](#9-when-things-go-wrong)
10. [Worked examples](#10-worked-examples)
11. [Deployment](#11-deployment)
12. [Still open](#12-still-open)

---

## 1. The policy

```
Cancel at least 48 hours before the booking starts
    refund = stay subtotal − 10% cancellation charge
    (the platform fee is retained)

Cancel inside 48 hours
    refund = 0
```

**48 hours is inclusive** — "at least 48 hours" means exactly 48h still refunds.

**The platform fee is not refunded.** It pays for a service already delivered — taking and handling
the booking — not for the stay itself.

**The deadline is measured from when the booking starts**: `check_in_date` for a stay,
`scheduled_time` for a consultation or restaurant table. A booking with neither has no deadline to
miss and is treated as inside the free window.

### Configuration

| Setting | Default | Effect |
|---|---|---|
| `CANCELLATION_FREE_WINDOW_HOURS` | `48` | How far ahead a cancellation still earns a refund |
| `CANCELLATION_CHARGE_PERCENT` | `10.0` | Deducted from the subtotal. `0` refunds it all |
| `PLATFORM_FEE_REFUNDABLE` | `false` | Whether the platform fee comes back |

Read at call time, so a change takes effect on restart with no code edit.

---

## 2. End-to-end flow

```
PATIENT                          PLATFORM                        RAZORPAY
   │
   │ 1. GET /bookings/{id}/refund-preview
   │───────────────────────────────▶│
   │◀───────────────────────────────│  "You'll get ₹9,000 back
   │                                │   (₹1,000 charge, ₹500 fee kept)"
   │
   │ 2. POST /bookings/{id}/cancel
   │    { "cancellation_reason": "..." }
   │───────────────────────────────▶│
   │                                │  status        = cancelled
   │                                │  refund_amount = 9000
   │                                │  refund_status = "pending"
   │◀───────────────────────────────│  ← NO money has moved yet
   │                                │
                                    │  3. Appears in /admin/refunds
                                    │
                              ADMIN │
                                    │  4. POST /admin/refunds/{id}/approve
                                    │──────────────────────────────▶│
                                    │                               │ refund created
                                    │◀──────────────────────────────│ rfnd_XXXXXXXX
                                    │  refund_status = "processed"
                                    │  refund_reference = rfnd_XXXXXXXX
                                    │
                                    │  5. Razorpay settles to the
                                    │     customer's card/bank      ──▶ 5–7 working days
```

The key property: **money leaves at step 4, never at step 2.** A Razorpay refund cannot be reversed
through the API, so a bad policy or a duplicate request would be unrecoverable if it fired
automatically. An unapproved refund is merely visible and waiting.

---

## 3. Step 1 — patient previews the refund

Call this from the cancel dialog **before** the patient confirms, so the charge is visible while they
can still change their mind.

```http
GET /api/v1/bookings/3f9a1c2e-7b4d-4a91-9f0e-2c5d8b1a6e33/refund-preview
Authorization: Bearer <patient token>
```

```json
{
  "booking_id": "3f9a1c2e-7b4d-4a91-9f0e-2c5d8b1a6e33",
  "reference_number": "HTL-2026-0142",
  "total_price": 10500.0,
  "currency": "INR",

  "refund_amount": 9000.0,
  "cancellation_charge": 1000.0,
  "platform_fee_retained": 500.0,
  "refundable_subtotal": 10000.0,

  "hours_before_start": 72.5,
  "within_free_window": true,
  "is_refundable": true,
  "reason": "Cancelled more than 48 hours before the booking starts. A 10% cancellation charge applies.",

  "lines": [
    { "label": "Booking total",                 "amount": 10500.0 },
    { "label": "Platform fee (non-refundable)", "amount":  -500.0 },
    { "label": "Cancellation charge (10%)",     "amount": -1000.0 },
    { "label": "Refund",                        "amount":  9000.0 }
  ]
}
```

`lines` is ready to render as a receipt — deductions are negative and sum to the refund. Suggested UI:

```
┌──────────────────────────────────────────────┐
│ Cancel booking HTL-2026-0142?                │
│                                              │
│ Booking total                    ₹ 10,500.00 │
│ Platform fee (non-refundable)    −    500.00 │
│ Cancellation charge (10%)        −  1,000.00 │
│ ──────────────────────────────────────────── │
│ You will be refunded              ₹ 9,000.00 │
│                                              │
│ Refunds are reviewed and released within     │
│ 1–2 business days, then take 5–7 working     │
│ days to reach your account.                  │
│                                              │
│ Reason for cancelling *                      │
│ [                                          ] │
│                                              │
│           [ Keep booking ] [ Cancel booking ]│
└──────────────────────────────────────────────┘
```

Inside the 48-hour window the same call returns `refund_amount: 0` and
`"reason": "Cancelled less than 48 hours before the booking starts, so no refund is due."` — show
that plainly rather than letting the patient find out afterwards.

---

## 4. Step 2 — patient cancels with a reason

```http
POST /api/v1/bookings/3f9a1c2e-7b4d-4a91-9f0e-2c5d8b1a6e33/cancel
Authorization: Bearer <patient token>
Content-Type: application/json

{ "cancellation_reason": "Treatment date moved by the hospital" }
```

`cancellation_reason` is **required**, 1–500 characters. It is stored on the booking and shown to the
admin reviewing the refund, to the property manager, and on the admin booking detail.

**Who may call this:** the patient who owns the booking, an admin, or the manager of the property.
Anyone else gets `404` — not `403`, so the endpoint cannot be used to discover whether a booking id
exists.

What changes on the booking:

| Field | Value |
|---|---|
| `status` | `cancelled` |
| `cancelled_at` | now |
| `cancellation_reason` | what the patient typed |
| `cancelled_by` | the caller |
| `refund_amount` | `9000.0` |
| `cancellation_charge` | `1000.0` |
| `refund_status` | **`pending`** |
| `refund_requested_at` | now |

**No money has moved.** The property manager is emailed about the cancellation; the refund now sits
in the queue.

If no refund is due (inside 48h, or unpaid), `refund_status` stays `none` and `refund_note` records
why — so an admin looking later can see it was decided, not forgotten.

---

## 5. Step 3 — admin sees the queue

```http
GET /api/v1/admin/refunds?page=1&page_size=20
Authorization: Bearer <admin token>
```

Ordered **longest-waiting first**. With no `status` filter it returns what needs action: `pending`
plus `failed`.

```json
{
  "items": [
    {
      "booking_id": "3f9a1c2e-7b4d-4a91-9f0e-2c5d8b1a6e33",
      "reference_number": "HTL-2026-0142",
      "booking_type": "hotel",
      "patient_name": "John Doe",
      "patient_email": "john@example.com",
      "total_price": 10500.0,
      "platform_fee": 500.0,
      "cancellation_charge": 1000.0,
      "refund_amount": 9000.0,
      "currency": "INR",
      "refund_status": "pending",
      "refund_requested_at": "2026-08-14T09:12:44Z",
      "waiting_hours": 18.6,
      "cancelled_at": "2026-08-14T09:12:44Z",
      "cancellation_reason": "Treatment date moved by the hospital",
      "refund_note": null,
      "payment_id": "9b1c4d7a-…"
    }
  ],
  "total": 1, "page": 1, "page_size": 20, "pages": 1
}
```

`GET /admin/refunds/stats` gives the queue health:

```json
{
  "pending": 4, "failed": 1, "processed": 128, "rejected": 3,
  "pending_value": 41500.0,
  "processed_value": 1284000.0,
  "oldest_waiting_hours": 62.4
}
```

**`oldest_waiting_hours` is the number to watch.** A customer waiting three days for a refund will
chase you, or raise a chargeback. Put `pending` on a sidebar badge.

---

## 6. Step 4 — admin approves

**This moves real money.**

```http
POST /api/v1/admin/refunds/3f9a1c2e-7b4d-4a91-9f0e-2c5d8b1a6e33/approve
Authorization: Bearer <admin token>
Content-Type: application/json

{}
```

An empty body pays exactly what the policy calculated. To override — a goodwill exception, or a
negotiated partial settlement:

```json
{ "amount": 10000 }
```

Response:

```json
{
  "booking_id": "3f9a1c2e-7b4d-4a91-9f0e-2c5d8b1a6e33",
  "refund_amount": 9000.0,
  "refund_reference": "rfnd_PqR7sT9uVwXyZa",
  "status": "processed"
}
```

Refused with `400` when: already processed, previously rejected, amount is zero or negative, amount
exceeds what was paid, or no payment is linked to the booking.

Confirm before sending — a dialog showing the amount, the patient, and that it is irreversible.

---

## 7. What Razorpay actually does

On approval the platform calls:

```
POST https://api.razorpay.com/v1/payments/{razorpay_payment_id}/refund
{ "amount": 900000, "notes": { "reason": "Booking HTL-2026-0142 cancelled" } }
```

Note **`900000`** — Razorpay works in the smallest currency unit, so ₹9,000 is 900,000 paise. The
conversion is handled for you; it matters only if you are reading raw gateway logs.

The `razorpay_payment_id` comes from the original payment's stored `gateway_response`, captured when
the patient paid.

### What comes back

```json
{
  "id": "rfnd_PqR7sT9uVwXyZa",
  "entity": "refund",
  "amount": 900000,
  "currency": "INR",
  "payment_id": "pay_MnO4pQ6rStUvWx",
  "status": "processed",
  "speed_processed": "normal",
  "created_at": 1786382712
}
```

The `id` is stored on the booking as `refund_reference` and on a `PaymentTransaction` row of type
`refund`, with the full gateway response kept for audit.

### What is updated locally

| Record | Change |
|---|---|
| `bookings` | `refund_status = processed`, `refund_processed_at`, `refund_processed_by`, `refund_reference` |
| `payments` | `is_refunded = true`, `refund_amount`, `refunded_at`, status → `refunded` or `partially_refunded` |
| `payment_transactions` | New `refund` row with the gateway response |

A partial refund sets `partially_refunded`, not `refunded` — so a ₹9,000 refund on a ₹10,500 payment
is correctly recorded as partial.

### Timing — set expectations with the customer

| Stage | Time |
|---|---|
| API call → Razorpay accepts | Immediate |
| Razorpay → customer's bank | **5–7 working days** (normal speed) |
| Instant refunds | Possible on some methods, extra fee, not enabled here |

**Your dashboard says "processed" long before the customer sees the money.** Say "5–7 working days"
in the confirmation, or you will field "where is my refund" emails on day two.

### Gateway fees

**Razorpay does not return its processing fee on a refund.** On a ₹10,500 payment you paid roughly
₹250 in gateway fees; refunding ₹9,000 does not give that back. The ₹500 platform fee you retain
partly offsets it. Worth knowing when reading `net_amount`.

### Webhooks

`refund.created` and `refund.failed` are already handled at `/payments/webhook`. Configure both in
the Razorpay dashboard — a refund that fails **after** the API accepted it (a closed bank account,
for instance) is only discoverable through the webhook.

---

## 8. Rejecting a refund

```http
POST /api/v1/admin/refunds/{booking_id}/reject
{ "reason": "No-show; cancelled after check-in time under the 48-hour policy" }
```

Sets `refund_status = rejected` and stores the reason on the booking. Nothing is sent to Razorpay.

The reason is required and the customer will ask for it, so write it as something you would be
comfortable quoting back to them.

A refund already **processed** cannot be rejected — the money is gone.

---

## 9. When things go wrong

### The gateway rejects the refund

The booking is marked `refund_status = failed` with the gateway error in `refund_note`, and **stays
in the queue** — `GET /admin/refunds` returns `pending` *and* `failed`. Fix the cause and approve
again. Nothing is silently dropped.

Common causes: insufficient balance in the Razorpay account, the payment is older than the refund
window, or it was already refunded directly in the Razorpay dashboard.

### Someone refunded in the Razorpay dashboard instead

The platform does not know. The booking sits `pending` forever and the queue overstates what is
owed. **Refund through this API, not the Razorpay dashboard.** If it has already happened, reject the
queue entry with a note pointing at the dashboard refund id.

### The booking has no linked payment

Approval is refused. Some bookings are created without a payment record — refund by hand and reject
the queue entry with a note.

---

## 10. Worked examples

All on a ₹10,500 hotel booking: ₹10,000 stay + ₹500 platform fee.

### A — cancelled 3 days ahead

| | |
|---|---|
| Subtotal | 10,000 |
| Cancellation charge (10%) | −1,000 |
| Platform fee retained | −500 |
| **Refunded** | **9,000** |
| Platform keeps | 1,500 |

### B — cancelled 47 hours ahead

| | |
|---|---|
| Inside the 48-hour window | — |
| **Refunded** | **0** |
| Platform keeps | 10,500 |

Preview returns `is_refundable: false` and the reason, so the patient sees this before confirming.

### C — cancelled exactly 48 hours ahead

Identical to A — **₹9,000**. The boundary qualifies.

### D — unpaid booking, cancelled any time

**₹0**, `refund_status` stays `none`, reason recorded as *"This booking has not been paid, so there
is nothing to refund."* Nothing enters the queue.

### E — admin overrides with a goodwill full refund

Policy says ₹9,000; the hospital cancelled, so the admin approves `{ "amount": 10000 }`.

| | |
|---|---|
| **Refunded** | **10,000** |
| Platform keeps | 500 (the fee) |

The override is recorded — `refund_amount` becomes 10,000 and `refund_processed_by` names the admin.

### F — a 30-night apartment at ₹60,000 + ₹3,000 fee

| | 5 days ahead | 24 hours ahead |
|---|---|---|
| Subtotal | 60,000 | — |
| Charge (10%) | −6,000 | — |
| Fee retained | −3,000 | −3,000 |
| **Refunded** | **54,000** | **0** |

---

## 11. Deployment

```bash
alembic upgrade 6d7a99e3eb2d
```

Or, on the deployment whose Alembic state is broken:

```bash
python scripts/sync_schema.py --apply --stamp
```

Adds `cancellation_charge`, `refund_status`, `refund_requested_at`, `refund_processed_at`,
`refund_processed_by`, `refund_reference`, `refund_note` to `bookings`, plus an index on
`refund_status`.

### Bookings cancelled before this deploy

They default to `refund_status = 'none'` and are **not** pulled into the queue — back-filling would
flood it with historical bookings, some already settled by hand.

**But anything cancelled and paid before this deploy may be owed money nothing is tracking:**

```sql
SELECT reference_number, total_price, refund_amount, cancelled_at
FROM bookings
WHERE status = 'cancelled' AND is_paid = true AND refund_status = 'none'
ORDER BY cancelled_at DESC;
```

Those carry the old hardcoded 80% figure. Decide each on its merits, refund manually, then set
`refund_status` so it stops appearing.

### Also configure

- **Razorpay webhooks** for `refund.created` and `refund.failed` — see §7
- **Publish the policy.** It currently exists only in code and `GET /admin/refunds/policy`. There is
  no terms page at all — see [SITE_PAGES_AUDIT.md](SITE_PAGES_AUDIT.md). Charging a fee that a
  customer cannot read beforehand invites chargebacks.

---

## 12. Still open

- **Consultation cancellations have no refund path.** `cancel_appointment` records nothing — not even
  an amount. The policy engine works on any booking, so wiring it in is small, but it is not done.
- **No customer email on approval or rejection.** The booking updates; nobody tells the patient. This
  is the most visible gap — a refund they are not told about generates a support ticket.
- **The property's `cancellation_policy` field is still unused.** Hotels and apartments carry free
  text an admin can edit, and no logic reads it. A per-property override would need it structured
  rather than prose.
- **No partial-refund history on bookings.** One approval per booking; a second is refused. Payments
  track cumulative refunds, bookings do not.
- **Nothing reconciles against Razorpay.** A refund issued in their dashboard leaves the queue wrong.
  A daily reconciliation job would catch it.

---

## Source

| Concern | File |
|---|---|
| Policy engine | [cancellation.py](app/utils/cancellation.py) |
| Refund queue | [refund_service.py](app/services/refund_service.py) |
| Admin endpoints | [admin_refund.py](app/api/v1/admin_refund.py) |
| Preview + cancel | [bookings.py](app/api/v1/bookings.py) |
| Cancellation | [booking_service.py](app/services/booking_service.py) (`cancel`) |
| Gateway call | [razorpay_service.py](app/services/razorpay_service.py) (`refund_payment`) |
| Schemas | [refund.py](app/schemas/refund.py) |
| Migration | `alembic/versions/6d7a99e3eb2d_add_refund_workflow.py` |
| Tests | [test_cancellation_refund.py](tests/test_cancellation_refund.py) — 26 tests |
