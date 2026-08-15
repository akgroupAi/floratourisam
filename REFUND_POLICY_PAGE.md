# Refund Policy Page — Frontend Content

Ready-to-publish copy for the public `/refund-policy` page, plus how to wire it so the numbers
stay in sync with the backend.

The engineering-facing version of this policy is in [REFUND_POLICY.md](REFUND_POLICY.md). This
document is the **customer-facing** page.

---

## Contents

1. [Wire it to the live policy](#1-wire-it-to-the-live-policy)
2. [Page copy — ready to paste](#2-page-copy--ready-to-paste)
3. [Where else this content belongs](#3-where-else-this-content-belongs)
4. [Things to decide before publishing](#4-things-to-decide-before-publishing)

---

## 1. Wire it to the live policy

**Do not hardcode 48 / 10% / 5%.** They are settings on the server. If someone changes
`CANCELLATION_CHARGE_PERCENT` in `.env`, a hardcoded page becomes a false promise you have
published — which is the version a customer will quote back at you.

```
GET /api/v1/admin/refunds/policy        no auth required, despite the /admin/ path
```

```json
{
  "free_window_hours": 48,
  "cancellation_charge_percent": 10.0,
  "platform_fee_refundable": false,
  "summary": "Cancel at least 48 hours before your booking starts and you will be refunded, less a 10% cancellation charge and the platform fee. Cancellations within 48 hours are not refunded."
}
```

```tsx
const { data: policy } = useQuery({
  queryKey: ["cancellation-policy"],
  queryFn: () => fetch(`${API_BASE}/api/v1/admin/refunds/policy`).then(r => r.json()),
  staleTime: 1000 * 60 * 60,
});
```

Interpolate `policy.free_window_hours` and `policy.cancellation_charge_percent` into the headline
rule and the examples. The platform fee percentage is not in this response — it is on each booking
as `platform_fee`; state it as "5%" on the page and keep it consistent with
`PLATFORM_FEE_PERCENT`.

If the fetch fails, render the copy with the current values rather than an empty page — but log it,
because a stale policy page is a liability.

---

## 2. Page copy — ready to paste

> Everything below is the customer-facing text. Adjust tone to match the rest of the site; keep the
> numbers and the mechanics exactly as written, because they are what the code actually does.

---

### Cancellation & Refund Policy

*Last updated: [DATE]*

We understand that plans change, especially where medical travel is involved. This page explains
exactly what you get back if you cancel, and when.

#### The short version

**Cancel at least 48 hours before your booking starts** and we refund what you paid, less a 10%
cancellation charge and the platform fee.

**Cancel within 48 hours of the start** and no refund is due.

The 48 hours is measured from your check-in date, or from your appointment time for consultations
and restaurant reservations.

#### What you get back — worked examples

Say you booked a room for ₹10,000. At checkout you paid a 5% platform fee of ₹500, so your total
was **₹10,500**.

**You cancel 5 days before check-in**

| | |
|---|---|
| Booking total | ₹ 10,500 |
| Platform fee (non-refundable) | − ₹ 500 |
| Cancellation charge (10%) | − ₹ 1,000 |
| **You are refunded** | **₹ 9,000** |

**You cancel 20 hours before check-in**

| | |
|---|---|
| Booking total | ₹ 10,500 |
| Retained — late cancellation | − ₹ 10,500 |
| **You are refunded** | **₹ 0** |

You will always see this breakdown on screen **before** you confirm the cancellation. Nothing is
calculated after the fact.

#### What the charges are for

**The platform fee (5%)** covers the cost of taking and managing your booking — a service that has
already been provided by the time you cancel. It is not refunded.

**The cancellation charge (10%)** covers the room, apartment, or appointment slot that was held for
you and taken off sale, which we may not be able to re-fill at short notice.

#### How to cancel

1. Open the booking from **My Bookings** in your account.
2. Select **Cancel booking**.
3. Review the refund breakdown shown on screen.
4. Give a short reason for cancelling — this is required.
5. Confirm.

Your booking is cancelled straight away. The refund follows the timeline below.

#### When the money arrives

| Stage | How long |
|---|---|
| Your cancellation is recorded | Immediately |
| We review and release the refund | Usually within 48 hours |
| Your bank or card issuer credits it | 5–7 working days after release |

Refunds go back to **the original payment method** — the same card, UPI ID, or account you paid
from. We cannot send a refund to a different account, and we cannot refund in cash or as credit.

You can track the status at any time on the booking page in your account. We will also email you
when the refund is released.

> **"Refund processed" means we have sent it, not that it has arrived.** Once released, the money
> is with your bank, and the 5–7 working days is their processing time, not ours.

#### Other situations

**You have not paid yet.** Nothing to refund — cancel freely at no cost.

**We cancel your booking.** If a hotel, apartment, or clinic cannot honour a confirmed booking, you
receive a **full refund with no charges deducted**, including the platform fee. Contact us and we
will arrange it.

**Your refund was declined.** In rare cases a refund request may be declined — for example where a
booking has already been used, or where the cancellation falls outside this policy. You will
receive an email explaining the reason. Reply to it if you disagree.

**Your refund failed at the bank.** Occasionally a refund is rejected by the payment provider, most
often when the original card has expired or been closed. We are notified automatically and will
retry or contact you for alternative details. You do not need to do anything, but do get in touch
if more than 10 working days pass.

**Your consultation was cancelled.** Online and in-person consultations follow the same 48-hour
rule, measured from the appointment time.

#### Changes to a booking

We do not currently support changing dates on an existing booking. To move your stay, cancel under
this policy and book again. If you are cancelling more than 48 hours ahead, please
[contact us](/contact) first — we may be able to help you avoid the charge.

#### Questions

Email **[support@floramedcare.com]** or use our [contact form](/contact). Please include your
booking reference — it looks like `HTL-20260817-A1B2C3` and is shown on your booking and in your
confirmation email.

---

## 3. Where else this content belongs

A refund policy page nobody visits does not prevent disputes. Put the rule where the decision is
actually made:

| Place | What to show |
|---|---|
| **Checkout, before payment** | One line: *"Free cancellation until [date, 48h before check-in]. After that, no refund."* Show the actual date, not "48 hours" — people cannot do that arithmetic under time pressure. |
| **Booking confirmation email** | The same line plus the cancellation deadline as a date. |
| **Cancel dialog** | The `lines` array from `GET /bookings/{id}/refund-preview`, rendered as a receipt. Already specified in [FRONTEND_WORK_REQUIRED.md §2.1](FRONTEND_WORK_REQUIRED.md). |
| **Booking detail page** | `GET /bookings/{id}/refund-status` — use `status_label` and `message` verbatim. |
| **Footer** | Link to this page from every page. |

The checkout line is the one that prevents disputes. By the time someone opens the policy page they
are usually already unhappy.

---

## 4. Things to decide before publishing

Four points where the page above states something the system does not yet fully back up. Worth
settling before it goes live, since a published policy is a commitment.

**1. There is no way to make an exception.** A customer who cancels at 47 hours for a legitimate
reason cannot be refunded — `refund_status` is set to `none` and such bookings never appear in the
admin refund queue. The page says *"contact us first"* for date changes, which implies flexibility
you cannot currently deliver. Either add a discretionary override on the admin booking screen (I can
build this — roughly an hour) or soften that sentence.

**2. Zero refund inside 48 hours is at the strict end.** Most booking platforms taper — 50% inside
48h, 0% inside 24h — rather than dropping straight to nothing. Your call commercially, but a hard
zero generates chargebacks, and a chargeback costs more than a partial refund. The window and
percentage are both settings, so a taper would be a code change to
[cancellation.py](app/utils/cancellation.py), not a migration.

**3. The "we cancel your booking" promise is manual.** The page promises a full no-deduction refund
if a property cannot honour a booking. There is no code path that does this automatically — an
admin has to approve a refund with a manual amount override. That works, but only if whoever staffs
the queue knows the rule. Worth writing into your internal process notes.

**4. This has not had legal review.** I have written it to match what the code does and to read
clearly, but I am not able to tell you whether it satisfies Indian consumer protection law, the
Consumer Protection (E-Commerce) Rules 2020, or your Razorpay merchant agreement — all three plausibly
have something to say about a non-refundable fee and a zero-refund window. Have someone qualified
read it before it goes live.

Related: the site still has **no terms of service and no privacy policy** at all, which is a larger
gap than this page. A payment gateway account can be suspended over it.
