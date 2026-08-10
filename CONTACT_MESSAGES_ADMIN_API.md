# Contact / "Send Message" Form — Admin API

How a message submitted on the public **Send Message** (Contact Us) form reaches the admin panel, and every endpoint the admin frontend needs to read and manage it.

Base URL: `/api/v1`

---

## Flow

```
Public site "Send Message" form
        │
        ▼
POST /api/v1/contact                      ← public, no auth
        │
        ├── row saved in `lead_submissions` (form_source = "contact_page", status = "pending")
        └── notification email sent to the admin address
        │
        ▼
GET /api/v1/admin/contacts                ← admin panel list
GET /api/v1/admin/contacts/{id}           ← admin opens it → auto-moves to "in_process"
PATCH /api/v1/admin/contacts/{id}/status  ← admin marks "completed"
```

All submissions live in the shared `lead_submissions` table. The admin contact endpoints filter on
`form_source = "contact_page"`, so they show **only** Send Message submissions — quote requests and
callback requests do not leak into this list.

---

## 1. Public submit (what the website form calls)

`POST /api/v1/contact` — no authentication.

Request body:

```json
{
  "full_name": "John Doe",
  "email": "john@example.com",
  "phone": "+919876543210",
  "country": "India",
  "treatment_of_interest": "Knee Replacement",
  "message": "I would like a consultation for knee replacement surgery."
}
```

| Field | Type | Required | Rules |
|---|---|---|---|
| `full_name` | string | yes | 2–255 chars |
| `email` | string | yes | valid email |
| `phone` | string | yes | 5–20 chars |
| `country` | string | yes | 2–100 chars |
| `treatment_of_interest` | string | no | max 255 chars |
| `message` | string | yes | 10–5000 chars |

Response `201 Created`:

```json
{
  "success": true,
  "message": "Thank you for contacting us. We'll respond within 24 hours.",
  "reference_id": "3f9a1c2e-7b4d-4a91-9f0e-2c5d8b1a6e33"
}
```

> `POST /api/v1/leads/contact` is the legacy path for the same thing. It still works and writes the
> same `form_source`, so those rows also show up in the admin list, but new frontend code should use
> `POST /api/v1/contact`.

---

## 2. Admin endpoints

**Auth on every endpoint below:** `Authorization: Bearer <access_token>`, and the user's role must be
`admin` or `super_admin`. Anything else gets `403`.

### 2.1 Stats — badge counts for the dashboard

`GET /api/v1/admin/contacts/stats`

```json
{
  "total": 128,
  "pending": 12,
  "in_process": 30,
  "completed": 86,
  "new_count": 12
}
```

`new_count` is the same as `pending` — use it for the unread badge on the Contacts menu item.

### 2.2 List submissions

`GET /api/v1/admin/contacts`

Query parameters:

| Param | Type | Default | Description |
|---|---|---|---|
| `page` | int | 1 | Page number, min 1 |
| `page_size` | int | 20 | Items per page, 1–100 |
| `status` | enum | — | `pending` \| `in_process` \| `completed` |
| `country` | string | — | Partial, case-insensitive match |
| `search` | string | — | Partial match on name, email, or phone |
| `new_only` | bool | false | Only unread (pending) submissions |

Sorted newest first. Response:

```json
{
  "items": [
    {
      "id": "3f9a1c2e-7b4d-4a91-9f0e-2c5d8b1a6e33",
      "full_name": "John Doe",
      "email": "john@example.com",
      "phone": "+919876543210",
      "country": "India",
      "treatment_of_interest": "Knee Replacement",
      "message": "I would like a consultation for knee replacement surgery.",
      "status": "pending",
      "status_label": "Pending",
      "is_new": true,
      "notes": null,
      "created_at": "2026-08-10T09:14:22.100Z",
      "updated_at": "2026-08-10T09:14:22.100Z"
    }
  ],
  "total": 128,
  "page": 1,
  "page_size": 20,
  "pages": 7
}
```

`status_label` is a ready-to-render label, and `is_new` drives the unread dot — no client-side mapping needed.

### 2.3 Get one submission

`GET /api/v1/admin/contacts/{contact_id}`

Returns the same object as a list item, plus `assigned_to`:

```json
{
  "id": "3f9a1c2e-7b4d-4a91-9f0e-2c5d8b1a6e33",
  "full_name": "John Doe",
  "email": "john@example.com",
  "phone": "+919876543210",
  "country": "India",
  "treatment_of_interest": "Knee Replacement",
  "message": "I would like a consultation for knee replacement surgery.",
  "status": "in_process",
  "status_label": "In Process",
  "is_new": false,
  "notes": null,
  "assigned_to": "8c1d4b77-2f3e-4a0b-91cc-77e5a2d90411",
  "created_at": "2026-08-10T09:14:22.100Z",
  "updated_at": "2026-08-10T10:02:05.882Z"
}
```

**Side effect:** opening a `pending` submission automatically flips it to `in_process` and assigns it
to the admin who opened it. That is why the response above shows `in_process` even though the list
showed `pending`. Refetch the list (or the stats) after opening a detail view so the badge stays correct.

`404` if the id does not exist, was soft-deleted, or belongs to a different form.

### 2.4 Update status

`PATCH /api/v1/admin/contacts/{contact_id}/status`

```json
{
  "status": "completed",
  "notes": "Called the patient, treatment plan shared over email."
}
```

`status` is required (`pending` | `in_process` | `completed`). `notes` is optional, max 2000 chars;
omit it to leave existing notes untouched. Returns the full updated detail object. `404` if not found.

### 2.5 Delete

`DELETE /api/v1/admin/contacts/{contact_id}`

Soft delete — the row stays in the database with `is_deleted = true` and disappears from every list.

```json
{ "message": "Contact submission deleted successfully" }
```

---

## Status workflow

| Value | Label | Set by |
|---|---|---|
| `pending` | Pending | Automatically on submit |
| `in_process` | In Process | Automatically when an admin opens the detail view |
| `completed` | Completed | Manually via `PATCH .../status` |

Older rows may carry the legacy value `"new"`. The service treats it as `pending` everywhere —
filtering, counting, and labelling — so the frontend never has to know about it.

---

## curl examples

```bash
# Public submit
curl -X POST http://localhost:8000/api/v1/contact \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "John Doe",
    "email": "john@example.com",
    "phone": "+919876543210",
    "country": "India",
    "treatment_of_interest": "Knee Replacement",
    "message": "I would like a consultation for knee replacement surgery."
  }'

# Admin: unread only
curl "http://localhost:8000/api/v1/admin/contacts?new_only=true&page=1&page_size=20" \
  -H "Authorization: Bearer $TOKEN"

# Admin: search
curl "http://localhost:8000/api/v1/admin/contacts?search=john&status=pending" \
  -H "Authorization: Bearer $TOKEN"

# Admin: stats
curl http://localhost:8000/api/v1/admin/contacts/stats \
  -H "Authorization: Bearer $TOKEN"

# Admin: mark completed
curl -X PATCH http://localhost:8000/api/v1/admin/contacts/$ID/status \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "completed", "notes": "Called the patient."}'
```

---

## Things to watch out for

- **The form must post to `POST /api/v1/contact`.** The admin list keys off `form_source = "contact_page"`,
  which only that endpoint (and the legacy `/leads/contact`) sets. If the website's Send Message form is
  wired to `/api/v1/leads/quote` or `/api/v1/pages/quote-form` instead, the rows land under `form_source
  = "quote_form"` and will never appear in `/admin/contacts` — they show up under
  `/api/v1/admin/site/quotes`.
- **`GET /api/v1/admin/site/contacts` is the older endpoint** for the same data. It returns the raw
  `LeadSubmission` shape with no `status_label` / `is_new` and no stats companion. Prefer
  `/api/v1/admin/contacts`.
- **The admin notification email is best-effort.** If SMTP fails, the submission is still saved and the
  public request still returns `201` — the failure is only logged. Never treat "no email arrived" as
  "the message was lost"; check the list endpoint.

---

## Source files

| Concern | File |
|---|---|
| Public endpoint | [app/api/v1/contact.py](app/api/v1/contact.py) |
| Admin endpoints | [app/api/v1/admin_contact.py](app/api/v1/admin_contact.py) |
| Business logic | [app/services/contact_service.py](app/services/contact_service.py) |
| Request/response schemas | [app/schemas/contact.py](app/schemas/contact.py) |
| Database model | [app/models/site.py](app/models/site.py) (`LeadSubmission`) |
| Status enum | [app/utils/enums.py](app/utils/enums.py) (`ContactStatus`) |
| Route registration | [app/api/v1/api_router.py](app/api/v1/api_router.py) |
