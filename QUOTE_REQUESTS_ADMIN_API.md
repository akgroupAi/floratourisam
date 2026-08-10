# "Get a Free Medical Plan Quote" — Admin API

How a quote request submitted on the public site reaches the admin panel, and every endpoint the
admin frontend needs to read and work the resulting leads.

Base URL: `/api/v1`

This mirrors [CONTACT_MESSAGES_ADMIN_API.md](CONTACT_MESSAGES_ADMIN_API.md) — same list/stats/detail/
update/delete shape, same auth, same pagination envelope. The differences are called out in
[Differences from the contact API](#differences-from-the-contact-api).

---

## Flow

```
Public site "Get a Free Medical Plan Quote" form
        │
        ├── POST /api/v1/pages/quote-form   (multipart — supports document uploads)
        └── POST /api/v1/leads/quote        (JSON — no uploads)
        │
        ├── row saved in `lead_submissions` (form_source = "quote_form", status = "new")
        ├── uploaded files written to uploads/quote_submissions/
        └── notification email sent to the admin address
        │
        ▼
GET   /api/v1/admin/quotes                        ← admin panel list
GET   /api/v1/admin/quotes/{id}                   ← detail + attached documents
GET   /api/v1/admin/quotes/{id}/documents/{file}  ← download an attachment (admin auth)
PATCH /api/v1/admin/quotes/{id}/status            ← move through the funnel
PATCH /api/v1/admin/quotes/{id}/assign            ← hand to a team member
```

Quote requests share the `lead_submissions` table with contact messages. The admin quote endpoints
match `form_source = "quote_form"` **or `NULL`** (older rows were saved before the tagging existed),
so contact-page messages never leak into this list.

---

## 1. Public submit (what the website form calls)

### 1.1 With document uploads — `POST /api/v1/pages/quote-form`

`multipart/form-data`, no authentication. This is the endpoint the live form uses
(`GET /api/v1/pages/quote-form` returns the field definitions and names this as `submit_endpoint`).

| Field | Type | Required |
|---|---|---|
| `country` | text | yes |
| `medical_condition` | text | yes |
| `email` | text | yes |
| `documents` | file[] | no — PDF/JPG/JPEG/PNG, max 10 MB each |

```json
{
  "success": true,
  "message": "Thank you! We've received your quote request. Our team will contact you within 24 hours.",
  "reference_id": "3f9a1c2e-7b4d-4a91-9f0e-2c5d8b1a6e33",
  "data": { "country": "India", "medical_condition": "Orthopedics", "email": "john@example.com", "files_uploaded": 2 }
}
```

> Note this endpoint returns `200` with `"success": false` on a rejected file type or oversized file —
> it does not use a `4xx` status. Check the `success` flag, not just the HTTP code.

### 1.2 Without uploads — `POST /api/v1/leads/quote`

`application/json`, no authentication. All fields except `email` are optional:

```json
{
  "email": "john@example.com",
  "name": "John Doe",
  "phone": "+919876543210",
  "country": "India",
  "medical_condition": "Orthopedics",
  "treatment_interest": "Knee Replacement",
  "preferred_destination": "Ahmedabad",
  "message": "Please send me a treatment plan and cost estimate.",
  "utm_source": "google",
  "utm_medium": "cpc",
  "utm_campaign": "ortho-2026"
}
```

Both endpoints now email the admin on submission (previously only the contact form did).

---

## 2. Admin endpoints

**Auth on every endpoint below:** `Authorization: Bearer <access_token>`, role `admin` or
`super_admin`. Anything else gets `403`.

### 2.1 Stats — dashboard tiles

`GET /api/v1/admin/quotes/stats`

```json
{
  "total": 340,
  "new": 24,
  "contacted": 118,
  "qualified": 96,
  "converted": 102,
  "new_count": 24,
  "conversion_rate": 30.0
}
```

`new_count` mirrors `new` — use it for the unread badge, same as the contact API.
`conversion_rate` is `converted / total` as a percentage, rounded to one decimal.

### 2.2 List quote requests

`GET /api/v1/admin/quotes`

| Param | Type | Default | Description |
|---|---|---|---|
| `page` | int | 1 | Page number, min 1 |
| `page_size` | int | 20 | Items per page, 1–100 |
| `status` | enum | — | `new` \| `contacted` \| `qualified` \| `converted` |
| `country` | string | — | Partial, case-insensitive match |
| `medical_condition` | string | — | Partial, case-insensitive match |
| `search` | string | — | Partial match on name, email, or phone |
| `new_only` | bool | false | Only unworked (`new`) requests |
| `has_documents` | bool | — | `true` = only with attachments, `false` = only without |
| `sort_by` | enum | `created_at` | `created_at` (newest first), `name`, `email`, `country` |

```json
{
  "items": [
    {
      "id": "3f9a1c2e-7b4d-4a91-9f0e-2c5d8b1a6e33",
      "full_name": "John Doe",
      "email": "john@example.com",
      "phone": "+919876543210",
      "country": "India",
      "medical_condition": "Orthopedics",
      "treatment_of_interest": "Knee Replacement",
      "preferred_destination": "Ahmedabad",
      "message": "Please send me a treatment plan and cost estimate.",
      "document_count": 2,
      "status": "new",
      "status_label": "New",
      "is_new": true,
      "notes": null,
      "created_at": "2026-08-10T09:14:22.100Z",
      "updated_at": "2026-08-10T09:14:22.100Z"
    }
  ],
  "total": 340,
  "page": 1,
  "page_size": 20,
  "pages": 17
}
```

The list carries `document_count` rather than the file paths — fetch the detail endpoint for those.

### 2.3 Get one quote request

`GET /api/v1/admin/quotes/{quote_id}`

Everything from the list item, plus attachments, assignment, and campaign tracking:

```json
{
  "id": "3f9a1c2e-7b4d-4a91-9f0e-2c5d8b1a6e33",
  "full_name": "John Doe",
  "email": "john@example.com",
  "phone": "+919876543210",
  "country": "India",
  "medical_condition": "Orthopedics",
  "treatment_of_interest": "Knee Replacement",
  "preferred_destination": "Ahmedabad",
  "message": "Please send me a treatment plan and cost estimate.",
  "documents": [
    "uploads/quote_submissions/9b1c-....pdf",
    "uploads/quote_submissions/4d7a-....jpg"
  ],
  "document_urls": [
    "/api/v1/admin/quotes/3f9a1c2e-7b4d-4a91-9f0e-2c5d8b1a6e33/documents/9b1c-....pdf",
    "/api/v1/admin/quotes/3f9a1c2e-7b4d-4a91-9f0e-2c5d8b1a6e33/documents/4d7a-....jpg"
  ],
  "document_count": 2,
  "status": "contacted",
  "status_label": "Contacted",
  "is_new": false,
  "notes": "Called on 10 Aug, sending cost estimate.",
  "assigned_to": "8c1d4b77-2f3e-4a0b-91cc-77e5a2d90411",
  "utm_source": "google",
  "utm_medium": "cpc",
  "utm_campaign": "ortho-2026",
  "created_at": "2026-08-10T09:14:22.100Z",
  "updated_at": "2026-08-10T11:40:11.507Z"
}
```

`404` if the id does not exist or was soft-deleted.

### 2.4 Download an attached document

`GET /api/v1/admin/quotes/{quote_id}/documents/{filename}`

Streams the file back with the right `Content-Type` (PDF, JPEG, or PNG). Admin auth required, same
as every other endpoint here — send the `Authorization` header.

**Use the `document_urls` values verbatim; do not build this URL from `documents`.** The `documents`
field holds server-side storage paths (`uploads/quote_submissions/...`), which are *not* reachable
from the browser. Fetching them directly returns `404 {"detail":"Not Found"}`, because the app has
no `/uploads/*` route by design — these are patients' medical records and must not be served from a
public static path.

Because the endpoint needs an `Authorization` header, a bare `<a href>` or `<img src>` will not work.
Fetch it and turn the response into a blob URL:

```js
const res = await fetch(`${API_BASE}${quote.document_urls[0]}`, {
  headers: { Authorization: `Bearer ${token}` },
});
if (!res.ok) throw new Error(`Download failed: ${res.status}`);
const url = URL.createObjectURL(await res.blob());
window.open(url);            // or <a href={url} download>
// URL.revokeObjectURL(url) once you are done with it
```

`404` if the quote does not exist, the filename is not one this quote stored, or the file is missing
from disk. A filename that is not a bare name (any path separator, `..`) is rejected, so one quote
can never read another quote's attachment or reach outside the upload directory.

### 2.5 Update status

`PATCH /api/v1/admin/quotes/{quote_id}/status`

```json
{
  "status": "qualified",
  "notes": "Documents verified, budget confirmed."
}
```

`status` is required (`new` | `contacted` | `qualified` | `converted`). `notes` is optional, max 2000
chars; omit it to leave existing notes untouched. Returns the full updated detail object.

Moving a quote off `new` also assigns it to the acting admin **if it is not already assigned** —
whoever works the lead owns it, without stealing it from an existing owner.

### 2.6 Assign to a team member

`PATCH /api/v1/admin/quotes/{quote_id}/assign`

```json
{ "assigned_to": "8c1d4b77-2f3e-4a0b-91cc-77e5a2d90411" }
```

Returns the full updated detail object. Use this to reassign or to assign without changing status.

### 2.7 Delete

`DELETE /api/v1/admin/quotes/{quote_id}`

Soft delete — the row stays with `is_deleted = true` and disappears from every list.

```json
{ "message": "Quote request deleted successfully" }
```

---

## Funnel stages

| Value | Label | Meaning |
|---|---|---|
| `new` | New | Submitted, nobody has worked it yet |
| `contacted` | Contacted | Team reached out to the patient |
| `qualified` | Qualified | Genuine lead — budget/condition confirmed |
| `converted` | Converted | Became a booking or treatment plan |

Rows with a missing status are treated as `new`.

---

## Differences from the contact API

Both APIs are deliberately the same shape, but three things differ because the underlying workflows
differ. Do not assume the contact behaviour carries over:

1. **Opening a quote does not change its status.** The contact API flips `pending → in_process` when an
   admin opens the detail view. Quotes do *not* auto-advance: `contacted` means someone actually called
   the patient, and auto-setting it on a page view would corrupt the funnel and the conversion rate.
   Admins set the stage explicitly via `PATCH .../status`.
2. **Different vocabulary.** Contacts use `pending`/`in_process`/`completed`; quotes use the sales funnel
   `new`/`contacted`/`qualified`/`converted`. Render from `status_label` and you don't have to care.
3. **Quotes have attachments and an assignment endpoint.** `documents`, `document_count`, the
   `has_documents` filter, and `PATCH .../assign` have no contact-side equivalent.

---

## curl examples

```bash
# Public submit with documents
curl -X POST http://localhost:8000/api/v1/pages/quote-form \
  -F "country=India" \
  -F "medical_condition=Orthopedics" \
  -F "email=john@example.com" \
  -F "documents=@/path/to/report.pdf"

# Admin: new requests only
curl "http://localhost:8000/api/v1/admin/quotes?new_only=true&page=1&page_size=20" \
  -H "Authorization: Bearer $TOKEN"

# Admin: leads with documents, from India, sorted by name
curl "http://localhost:8000/api/v1/admin/quotes?has_documents=true&country=india&sort_by=name" \
  -H "Authorization: Bearer $TOKEN"

# Admin: stats
curl http://localhost:8000/api/v1/admin/quotes/stats \
  -H "Authorization: Bearer $TOKEN"

# Admin: move through funnel
curl -X PATCH http://localhost:8000/api/v1/admin/quotes/$ID/status \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "qualified", "notes": "Documents verified."}'

# Admin: assign
curl -X PATCH http://localhost:8000/api/v1/admin/quotes/$ID/assign \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"assigned_to": "8c1d4b77-2f3e-4a0b-91cc-77e5a2d90411"}'

# Admin: download an attached document (filename comes from document_urls)
curl -OJ "http://localhost:8000/api/v1/admin/quotes/$ID/documents/9b1c-....pdf" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Things to watch out for

- **The older `/api/v1/admin/site/quotes*` endpoints still exist** and are superseded by these. Prefer
  `/api/v1/admin/quotes` — the old ones take `status`, `assigned_to`, and `notes` as **query
  parameters** instead of a JSON body, return no `status_label`/`is_new`, have no delete, and their
  detail endpoint matches only `form_source = "quote_form"` while their list also returns legacy
  `NULL`-source rows, so a row visible in that list can `404` when opened. The new endpoints apply one
  consistent filter everywhere.
- **`documents` holds server-side file paths, not public URLs.** Use `document_urls` and the
  [download endpoint](#24-download-an-attached-document). Prefixing the API base onto a `documents`
  entry produces `/apis/uploads/quote_submissions/....pdf`, which returns
  `404 {"detail":"Not Found"}` — the app deliberately has no `/uploads/*` route, since these are
  patients' medical records. The only static mount is `/static/uploads`, and quote documents are
  intentionally not served from it.
- **The download endpoint needs an `Authorization` header**, so `<a href>` and `<img src>` will not
  work. Fetch it and use a blob URL, as shown in section 2.4.
- **The admin notification email is best-effort.** If SMTP fails, the submission is still saved and the
  public request still succeeds — the failure is only logged. Never treat "no email arrived" as "the
  request was lost"; check the list endpoint.

---

## Source files

| Concern | File |
|---|---|
| Admin endpoints | [app/api/v1/admin_quote.py](app/api/v1/admin_quote.py) |
| Business logic | [app/services/quote_service.py](app/services/quote_service.py) |
| Request/response schemas | [app/schemas/quote.py](app/schemas/quote.py) |
| Public submit (multipart) | [app/api/v1/pages.py](app/api/v1/pages.py) (`submit_quote_form`) |
| Public submit (JSON) | [app/api/v1/leads.py](app/api/v1/leads.py) (`submit_quote_request`) |
| Admin notification email | [app/utils/email_sender.py](app/utils/email_sender.py) (`render_quote_lead_email_html`) |
| Database model | [app/models/site.py](app/models/site.py) (`LeadSubmission`) |
| Status enum | [app/utils/enums.py](app/utils/enums.py) (`QuoteStatus`) |
| Route registration | [app/api/v1/api_router.py](app/api/v1/api_router.py) |
| Tests | [tests/test_quote.py](tests/test_quote.py) |
