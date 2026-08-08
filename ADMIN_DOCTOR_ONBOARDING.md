# Add / Invite a Doctor — Frontend Guide

For the admin panel. Covers the "Add Doctor" screen, the invite email the doctor
receives, and every response you need to handle.

- Base URL: `/api/v1`
- Auth header: `Authorization: Bearer <access_token>`
- Token comes from `POST /auth/admin/login` (**not** `/auth/login` — that one rejects admins)
- Allowed roles: `admin` and `super_admin`, except approve/reject which are `super_admin` only

Companion doc: [ADMIN_FRONTEND_API_GUIDE.md](ADMIN_FRONTEND_API_GUIDE.md).

---

## 1. What happens when you add a doctor

```
Admin submits the "Add Doctor" form
        │
        ▼
POST /admin/doctors            → creates the login account + the doctor profile
        │
        ▼
Backend emails the doctor      → link to {FRONTEND_URL}/reset-password?token=...
        │                         (valid 72 hours)
        ▼
Doctor opens the link, sets their own password
        │
        ▼
Doctor signs in at POST /auth/login (the public site login)
```

The invite link points at the **`/reset-password` page you already have**. You do not
need to build a new screen for the doctor — just make sure that page works (see §6).

---

## 2. Two ways to add a doctor

The `password` field decides which. It is **optional**.

| | Mode A — Invite (recommended) | Mode B — Temporary password |
|---|---|---|
| Send `password`? | No — omit it | Yes |
| Doctor's email contains | "Set Your Password" button | The password, shown once, + "Change Password" button |
| Can the doctor log in right away? | No — only via the link | Yes |
| Plaintext password sent by email? | Never | Yes |

Build the form with the password field **empty and optional** by default, and a hint like
*"Leave blank — the doctor will set their own password from the email we send them."*
Offer the password field only as an advanced/override option.

---

## 3. Create the doctor

```http
POST /api/v1/admin/doctors
Authorization: Bearer <admin_token>
Content-Type: application/json
```

**Minimum body (Mode A):**

```json
{
  "email": "doctor@example.com",
  "full_name": "Dr. Example Name"
}
```

**Full body — everything after `full_name` is optional:**

```json
{
  "email": "doctor@example.com",
  "password": null,
  "full_name": "Dr. Example Name",
  "phone": "+919999999999",

  "hospital_id": "uuid-or-null",
  "title": "Dr.",
  "license_number": "MED-12345",
  "license_expiry": "2030-01-01",
  "primary_specialty": "Cardiology",
  "years_of_experience": 10,
  "qualifications": ["MBBS", "MD"],
  "education": [
    { "degree": "MBBS", "college": "Example University", "year": 2012, "location": "India" }
  ],
  "certifications": [
    { "name": "Fellowship Example", "location": "USA" }
  ],
  "bio": "Short professional bio...",
  "languages_spoken": ["English", "Hindi"],
  "consultation_fee": 1000,
  "consultation_duration_minutes": 30,
  "video_consultation_enabled": true,
  "chat_consultation_enabled": true,
  "in_person_enabled": true,

  "address_line1": "Clinic address",
  "address_line2": null,
  "city": "Ahmedabad",
  "state": "Gujarat",
  "country": "India",
  "postal_code": "380001",

  "specializations": [
    { "specialization": "Cardiology", "is_primary": true },
    { "specialization": "Interventional Cardiology", "is_primary": false }
  ],
  "availability": [
    {
      "day_of_week": 0,
      "start_time": "10:00:00",
      "end_time": "18:00:00",
      "is_available": true,
      "slot_duration_minutes": 30,
      "max_appointments": 8
    }
  ],

  "is_verified": true,
  "send_welcome_email": true
}
```

### Field notes

| Field | Rule |
|-------|------|
| `email` | Required, must be unique across all users |
| `full_name` | Required, 2–255 chars |
| `password` | **Optional.** If sent: min 8 chars, ≥1 uppercase, ≥1 lowercase, ≥1 digit, ≥1 special char |
| `send_welcome_email` | Default `true`. Send `false` to create the account silently (bulk import) — then use **Resend invite** later |
| `is_verified` | Default `true` → doctor goes live immediately. Send `false` to put them in the pending-approval queue instead |
| `day_of_week` | `0 = Monday` … `6 = Sunday` |
| `start_time` / `end_time` | `"HH:MM:SS"` |
| `license_expiry` | `"YYYY-MM-DD"` |
| `hospital_id` | Must be an existing hospital, else `404` |

### Response — `201 Created`

The full doctor object, same shape as `GET /admin/doctors/{id}`:

```json
{
  "id": "e48197c0-...",
  "user_id": "efaf1e47-...",
  "full_name": "Dr. Example Name",
  "email": "doctor@example.com",
  "phone": "+919999999999",
  "primary_specialty": "Cardiology",
  "approval_status": "approved",
  "is_verified": true,
  "specializations": ["Cardiology"],
  "specialization_details": [ /* full records with is_primary, certification */ ],
  "availability": [ /* full records */ ],
  "hospital_id": null,
  "hospital_name": null,
  "rating": null,
  "total_reviews": 0,
  "total_consultations": 0,
  "created_at": "2026-08-08T10:00:00Z"
}
```

> The response does **not** tell you whether the email was actually delivered. If you need
> certainty, follow up with **Resend invite** (§5), which does report failures.

---

## 4. What the doctor receives

Subject: **Your Flora Medical doctor account**

- **Mode A:** their login email, a *Set Your Password* button, the raw link, and the expiry notice.
- **Mode B:** the same, plus a *Temporary password* block showing the password once.

The button links to:

```
{FRONTEND_URL}/reset-password?token=<token>
```

The link is valid for **72 hours**. After that the doctor must use "Forgot password" on
the login page, or the admin resends the invite.

---

## 5. Resend invite

Use this for an expired link, an email the doctor never got, or an account created with
`send_welcome_email: false`.

```http
POST /api/v1/admin/doctors/{doctor_id}/resend-invite
Authorization: Bearer <admin_token>
```

```json
{ "success": true, "message": "Set-password email sent to doctor@example.com" }
```

- Generates a fresh link and **invalidates the previous one**
- Never re-sends a plaintext password, even for Mode B accounts
- `502` means the email genuinely failed to send — show a real error toast and let the admin retry
- `400` means the doctor's account is inactive (deleted/deactivated)

Put this action in the doctor's row menu and on the detail page.

---

## 6. The `/reset-password` page

This is where the doctor lands from the email. It already exists — just confirm it:

1. Reads the token from the query string: `?token=...`
2. Posts **all three** fields (`confirm_password` is required, missing it returns `422`):

```http
POST /api/v1/auth/reset-password
Content-Type: application/json

{
  "token": "<from the URL>",
  "new_password": "Doctor@123456",
  "confirm_password": "Doctor@123456"
}
```

3. On success → redirect to the login page. The token is single-use, so a refresh/retry
   will fail with `400` — show "This link has already been used or has expired. Ask your
   administrator to resend the invite."

After this the doctor signs in at `POST /auth/login` (public login, not admin login).

> **Note for existing users:** password-reset links issued before this release no longer
> work. Anyone holding an old link just has to request a new one.

---

## 7. Approval status

`approval_status` is one of `pending` · `approved` · `rejected` · `suspended`.

A doctor is only visible on the public website when `approval_status === "approved"`
**and** `is_verified === true`.

If you create doctors with `is_verified: false`, they land in the review queue:

| Purpose | Call |
|---------|------|
| Pending list | `GET /admin/doctors/pending?page=1&page_size=20` |
| Badge count | `GET /admin/doctors/pending/count` → `{ "pending_count": 3 }` |
| Approve (super_admin) | `POST /admin/doctors/{id}/approve` |
| Reject (super_admin) | `POST /admin/doctors/{id}/reject` with `{ "reason": "..." }` — reason is required, 5–2000 chars |

Approve and reject each send their own email to the doctor and raise an in-app
notification. Hide these two buttons for plain `admin` users — they get `403`.

---

## 8. Listing doctors

```http
GET /api/v1/admin/doctors?page=1&page_size=20&search=&status=&is_verified=
```

Query params: `page`, `page_size` (max 100), `search` (name or email), `hospital_id`,
`specialization`, `status` (`pending`/`approved`/`rejected`/`suspended`), `is_verified`.

With no `status` filter, pending doctors sort to the top, then newest first.

Other endpoints on the same resource:

| Action | Method | Path |
|--------|--------|------|
| Doctor detail | `GET` | `/admin/doctors/{doctor_id}` |
| Update doctor | `PUT` | `/admin/doctors/{doctor_id}` |
| Delete doctor (soft) | `DELETE` | `/admin/doctors/{doctor_id}` |

---

## 9. Errors to handle

Business errors come back as `{"detail": "..."}`. Validation errors use the envelope with
a per-field `errors` array — map those onto the form fields.

| Status | Response | Show the admin |
|--------|----------|----------------|
| `400` | `{"detail": "Email already registered"}` | Inline error on the email field |
| `400` | `{"detail": "License number already registered"}` | Inline error on the licence field |
| `400` | `{"detail": "Doctor account is inactive"}` | Toast — cannot resend to a deactivated account |
| `403` | — | Hide approve/reject for non-super-admins |
| `404` | `{"detail": "Hospital not found"}` | Refresh the hospital dropdown |
| `404` | `{"detail": "Doctor not found"}` | Row is stale — refresh the list |
| `422` | `{"success": false, "error_code": "VALIDATION_ERROR", "errors": [{"field": "password", "message": "..."}]}` | Field-level errors |
| `502` | `{"detail": "Could not send the email..."}` | "Couldn't send the email — check with the backend team, then retry" |

---

## 10. Build checklist

- [ ] Password field is **optional** and empty by default, with the "doctor sets their own" hint
- [ ] Password strength validated client-side only when the field is actually filled
- [ ] **Resend invite** action on the doctor row and detail page, with real error handling for `502`
- [ ] `/reset-password` sends `token` + `new_password` + `confirm_password`
- [ ] Friendly message for an already-used or expired link
- [ ] `approval_status` shown as a chip in the doctor list
- [ ] Pending badge fed by `GET /admin/doctors/pending/count`
- [ ] Approve / Reject buttons hidden unless the logged-in user is `super_admin`
- [ ] Reject dialog requires a reason (min 5 characters)
