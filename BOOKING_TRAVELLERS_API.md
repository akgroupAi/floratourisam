# Booking Travellers & Documents — API

Capture who is travelling (the patient plus any companions) and the documents they upload —
flight tickets, passport photos, visas, insurance.

Base URL: `/api/v1`

---

## What this replaces

Bookings previously stored a `guest_count` and a free-form `guest_details` dict — an unvalidated
blob with no structure, no per-person detail, and nowhere to attach a document.

Now:

- **`booking_guests`** — one row per traveller, with passport details and contact information
- **`booking_documents`** — uploaded files, optionally attached to a specific traveller

`guest_details` is untouched, so anything already stored there still reads back.

---

## 1. Adding travellers

### Inline, when creating a booking

```json
POST /api/v1/bookings/hotel
{
  "room_id": "…", "check_in_date": "2026-09-01", "check_out_date": "2026-09-05",
  "guest_count": 2,
  "guests": [
    {
      "full_name": "John Doe",
      "guest_type": "patient",
      "date_of_birth": "1980-03-15",
      "nationality": "United Kingdom",
      "passport_number": "GB1234567",
      "passport_expiry": "2030-01-01",
      "phone": "+441234567890",
      "email": "john@example.com",
      "special_needs": "Wheelchair access required"
    },
    {
      "full_name": "Jane Doe",
      "relationship_to_patient": "spouse",
      "passport_number": "GB7654321"
    }
  ]
}
```

Works on `POST /bookings/hotel`, `POST /bookings/apartment`, and `POST /packages/{id}/book`.

### Coverage by booking type

| Booking type | Travellers inline at creation | `/guests` and `/documents` endpoints |
|---|---|---|
| Hotel | Yes | Yes |
| Apartment | Yes | Yes |
| Medical package | Yes | Yes |
| Restaurant | No — a table reservation needs no passport | Yes |
| Consultation | No | Yes |

The endpoints hang off `/bookings/{booking_id}`, so they work for **any** booking type once the
booking exists. Only the inline field is limited, and only where it makes sense: a restaurant
reservation does not need a passport, but you can still attach documents to one if you want to.

> Attaching travellers inline is **best-effort**: if the list is malformed the booking is still
> created and the error logged, rather than losing a booking the customer has already committed to.
> Add them afterwards with the endpoint below.

### Afterwards

```
GET    /bookings/{booking_id}/guests
POST   /bookings/{booking_id}/guests           add travellers
PUT    /bookings/{booking_id}/guests/{id}      edit — only fields sent are changed
DELETE /bookings/{booking_id}/guests/{id}      remove a companion
```

### Who is the patient

Every booking has exactly **one** `patient`; everyone else is a `companion`.

- Two travellers marked `patient` → `400`
- Nobody marked → the **first traveller is promoted**, since a booking with companions but nobody
  being treated is meaningless
- `relationship_to_patient` is cleared on the patient — "spouse of the patient" is meaningless on
  the patient themselves
- **The patient cannot be deleted** from their own booking; edit their details instead

---

## 2. Documents

```
GET    /bookings/{booking_id}/documents
POST   /bookings/{booking_id}/documents          multipart upload
GET    /bookings/{booking_id}/documents/{id}     download
DELETE /bookings/{booking_id}/documents/{id}
```

### Upload

`multipart/form-data`:

| Field | Required | Notes |
|---|---|---|
| `file` | yes | JPG, PNG, WebP, or PDF — max 10 MB |
| `document_type` | yes | `passport`, `flight_ticket`, `visa`, `insurance`, `medical_report`, `id_proof`, `other` |
| `guest_id` | no | Attach to one traveller — a passport belongs to a person |
| `notes` | no | |

```bash
curl -X POST "$API/api/v1/bookings/$BOOKING_ID/documents" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@passport.jpg" \
  -F "document_type=passport" \
  -F "guest_id=$GUEST_ID"
```

Leave `guest_id` out for booking-level documents like a shared flight booking. Maximum 25 documents
per booking.

### Download needs a blob, not an `<a href>`

The response gives you `download_url`, an authenticated API path. **`file_path` is a server-side
location and is never browser-reachable** — the same design as quote documents, and for the same
reason: these are passports and medical reports.

```js
const res = await fetch(`${API_BASE}${doc.download_url}`, {
  headers: { Authorization: `Bearer ${token}` },
});
const url = URL.createObjectURL(await res.blob());
window.open(url);
// URL.revokeObjectURL(url) when done
```

Deleting is a soft delete — the row is hidden but the file stays on disk, so an audit can still
establish what was uploaded and when.

---

## 3. Who can see them

Every traveller and document route resolves the caller first. Access is limited to:

- **The patient** who owns the booking
- **Admins** and super admins
- **The manager** of the property the booking is for

Anyone else gets **`404`, not `403`**. A 403 would confirm the booking exists; 404 reveals nothing,
so the endpoints cannot be used to probe for valid references.

Two further guards:

- Uploaded files are stored under a **generated name**, never the client's — a filename cannot carry
  a path.
- The download path is **rebuilt from the stored basename** rather than trusting `file_path`
  wholesale, so a tampered row cannot read outside the upload directory.

---

## 4. Deployment

```bash
alembic upgrade z0a1b2c3d4e5
```

Creates `booking_guests` and `booking_documents`. **Existing bookings are untouched** — they simply
have no traveller or document rows.

Files are written to `UPLOAD_DIR/booking_documents/`. That path derives from the setting rather than
the process working directory, which is what made quote documents unreachable earlier. Make sure the
directory is on **persistent storage** — if `uploads/` sits on ephemeral container disk, passports
vanish on every deploy.

---

## 5. Worth knowing

- **Passport numbers are stored in plain text.** That is normal for a booking system, but they are
  personal data under GDPR: they belong in your privacy policy, and a retention rule (delete N days
  after checkout) would be worth adding. Flagged in [SITE_PAGES_AUDIT.md](SITE_PAGES_AUDIT.md), which
  notes there is currently no privacy policy at all.
- **`guest_count` is not enforced against the traveller list.** A booking can say 2 guests and carry
  3 travellers. Deliberate for now — the count drives pricing and the list is informational — but
  worth reconciling if the property uses it for room allocation.
- **No virus scanning** on uploads. Type and size are checked; content is not.

---

## Source

| Concern | File |
|---|---|
| Models | [booking.py](app/models/booking.py) (`BookingGuest`, `BookingDocument`) |
| Service | [booking_guest_service.py](app/services/booking_guest_service.py) |
| Endpoints | [bookings.py](app/api/v1/bookings.py) |
| Schemas | [booking.py](app/schemas/booking.py) |
| Migration | `alembic/versions/z0a1b2c3d4e5_add_booking_guests_and_documents.py` |
| Tests | [test_booking_guests.py](tests/test_booking_guests.py) — 25 tests |
