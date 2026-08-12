# Admin Email Alerts

Emails sent to the admin when a patient books or a doctor sends a treatment proposal.

Recipient: `FIRST_SUPERUSER_EMAIL` from settings — the same address the contact and quote alerts
already use.

---

## What triggers an email

| Event | Subject | Fires from |
|---|---|---|
| Patient books a **hotel** | `New Hotel Booking: HTL-…` | `create_hotel_booking` |
| Patient books an **apartment** | `New Apartment Booking: APT-…` | `create_apartment_booking` |
| Patient books a **restaurant** | `New Restaurant Booking: BKG-…` | `create_restaurant_booking` |
| Patient books a **consultation** | `New Consultation: CNS-…` | `consultation_service.create` |
| Patient books an **appointment** | `New Consultation: CNS-…` | `appointment_service.schedule_appointment` |
| Doctor sends a **treatment proposal** | `New Treatment Proposal: TP-…` | `create_proposal` |
| Patient **accepts** a proposal | `Treatment Proposal Accepted: TP-…` | `patient_respond` |
| Patient **rejects** a proposal | `Treatment Proposal Rejected: TP-…` | `patient_respond` |
| Patient **requests a revision** | `Treatment Proposal — Revision Requested: TP-…` | `patient_respond` |

Both consultation paths are covered — the platform creates consultations in two places
(`/consultations` and `/appointments`) and either would otherwise have been missed.

---

## When it fires: at booking, not at payment

The email goes out **when the booking is created**, not when it is paid. Hotel and apartment
bookings start as `pending` and only become `confirmed` after payment, so waiting for payment would
mean the admin never hears about an abandoned checkout.

Each email states the payment position explicitly:

```
Payment:  Awaiting payment
Status:   Pending
```

and unpaid bookings carry a footer line: *"This booking has not been paid yet — it is held as
pending."* An admin can then chase it or ignore it.

> This does mean an abandoned booking still generates an email. If that turns out to be noisy, the
> cleaner fix is a short expiry on unpaid bookings rather than suppressing the alert — a booking that
> exists but nobody knows about is the worse failure.

---

## What each email contains

**Bookings** — reference, property and room/unit, guest name, email, phone, dates, nights, guest
count, platform fee, total, payment status, booking status, and any special requests.

**Consultations** — reference, patient contact, doctor with specialty and hospital, consultation
type, scheduled time, duration, fee, payment status, and the patient's stated reason or symptoms.

**Treatment proposals (sent)** — reference, treatment, doctor, patient, hospital, proposed visit
date, the **full itemised cost breakdown** (consultation, surgery, hospital stay, medications,
other), total, and the doctor's notes.

**Treatment proposal responses** — reference, outcome, treatment, patient, doctor, hospital, proposed
visit date, total, when they responded, and any notes the patient left.

An **acceptance is the conversion point** — treatment is agreed and payment follows — so that email
closes with *"Treatment is agreed — arrange scheduling and payment."* A revision request closes with
*"The doctor needs to revise and resend this proposal."* Rejections are sent too: an admin wants to
see lost business, not only won business.

All four use one shared template, `render_admin_alert_email_html`, so they stay visually consistent
with the existing contact and quote alerts rather than drifting apart. Empty fields are dropped
automatically, so a booking with no phone number simply omits that row.

---

## Failure behaviour

**Every alert is best-effort.** A mail failure is logged and swallowed — it can never roll back the
booking, consultation, or proposal that triggered it. That is deliberate and tested: the alert
functions are called with a database that fails every call, and they return normally.

If `FIRST_SUPERUSER_EMAIL` is unset, the send is skipped with a warning rather than raising.

Delivery is recorded in `email_logs` like every other email, so a missing alert can be diagnosed via
`GET /api/v1/email/logs` filtered by category:

| Category | Event |
|---|---|
| `booking_admin_alert` | Hotel, apartment, restaurant |
| `consultation_admin_alert` | Consultations and appointments |
| `proposal_admin_alert` | Treatment proposals sent by a doctor |
| `proposal_response_admin_alert` | Patient accepted, rejected, or asked for a revision |

---

## Configuration

No new settings. The recipient is the existing `FIRST_SUPERUSER_EMAIL`, and SMTP config is unchanged.

To send to a distribution list rather than one person, point `FIRST_SUPERUSER_EMAIL` at a group
address. If you later need per-event recipients, `_admin_email()` in
[admin_notify.py](app/utils/admin_notify.py) is the single place to change.

---

## Source

| Concern | File |
|---|---|
| Alert helpers | [admin_notify.py](app/utils/admin_notify.py) |
| Shared template | [email_sender.py](app/utils/email_sender.py) (`render_admin_alert_email_html`) |
| Booking triggers | [booking_service.py](app/services/booking_service.py) |
| Consultation triggers | [consultation_service.py](app/services/consultation_service.py) · [appointment_service.py](app/services/appointment_service.py) |
| Proposal trigger | [treatment_proposal_service.py](app/services/treatment_proposal_service.py) |
| Tests | [test_admin_notify.py](tests/test_admin_notify.py) — 28 tests |
