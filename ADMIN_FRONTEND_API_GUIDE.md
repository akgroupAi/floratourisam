# Admin Frontend API Guide

Base URL: `/api/v1`  
Auth header: `Authorization: Bearer <access_token>`

This document covers the admin APIs needed for:

1. Admin vs public login (session separation)
2. Doctor create/edit (overview, specializations, hospital, availability, credentials)
3. Hospital create/edit with cover image + gallery
4. Patient management (totals, detail, history, consultation track)

---

## 1. Authentication (critical)

Admin and public site must **not** share the same login endpoint or token storage.

| App | Endpoint | Allowed roles |
|-----|----------|---------------|
| Public website | `POST /auth/login` | Patients, doctors, managers — **rejects** `admin` / `super_admin` |
| Admin panel | `POST /auth/admin/login` | `admin` / `super_admin` only |

### Admin login

```http
POST /api/v1/auth/admin/login
Content-Type: application/json

{
  "email": "admin@medicaltourism.com",
  "password": "Admin@123456"
}
```

### Public login

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "patient@example.com",
  "password": "..."
}
```

### Frontend rules

1. Admin app → only `/auth/admin/login`
2. Public site → only `/auth/login`
3. Use **separate storage keys**, e.g.:
   - Public: `localStorage.user_token`
   - Admin: `localStorage.admin_token`
4. On public site, never redirect to admin dashboard just because `is_admin` is true
5. JWT includes `"portal": "admin"` or `"portal": "public"`

---

## 2. Admin Doctors

Prefix: `/admin/doctors`

### Endpoints overview

| Action | Method | Endpoint |
|--------|--------|----------|
| Create doctor (user + profile) | `POST` | `/admin/doctors` |
| Resend set-password email | `POST` | `/admin/doctors/{doctor_id}/resend-invite` |
| List doctors | `GET` | `/admin/doctors` |
| Get doctor detail | `GET` | `/admin/doctors/{doctor_id}` |
| Update doctor (all edit tabs) | `PUT` | `/admin/doctors/{doctor_id}` |
| Delete doctor | `DELETE` | `/admin/doctors/{doctor_id}` |
| Assign doctor to hospital/department | `POST` | `/admin/doctors/assignments` |
| List assignments | `GET` | `/admin/doctors/assignments` |
| Remove assignment | `DELETE` | `/admin/doctors/assignments/{assignment_id}` |
| Verify doctor | `POST` | `/doctors/{doctor_id}/verify` |

### UI tab → API map

| Admin UI tab | API |
|--------------|-----|
| Create doctor | `POST /admin/doctors` |
| Overview / personal info | `PUT /admin/doctors/{id}` |
| Education & certifications | `PUT /admin/doctors/{id}` (`education`, `certifications`) |
| Specializations | `PUT /admin/doctors/{id}` (`specializations`) |
| Availability | `PUT /admin/doctors/{id}` (`availability`) |
| Hospital | `hospital_id` on create/update **and/or** `/admin/doctors/assignments` |
| Verify | `POST /doctors/{id}/verify` |

### Create doctor

Full walkthrough of this flow, including the email the doctor receives:
[ADMIN_DOCTOR_ONBOARDING.md](ADMIN_DOCTOR_ONBOARDING.md).

```http
POST /api/v1/admin/doctors
Authorization: Bearer <admin_token>
Content-Type: application/json
```

`password` is **optional**. Omit it and the doctor receives an emailed
set-password link instead — no plaintext password is transmitted.

```json
{
  "email": "doctor@example.com",
  "password": "Doctor@123456",
  "full_name": "Dr. Example Name",
  "phone": "+919999999999",
  "hospital_id": "uuid-or-null",
  "title": "Dr.",
  "primary_specialty": "Cardiology",
  "years_of_experience": 10,
  "qualifications": ["MBBS", "MD"],
  "education": [
    {
      "degree": "MBBS",
      "college": "Example University",
      "year": 2012,
      "location": "India"
    }
  ],
  "certifications": [
    {
      "name": "Fellowship Example",
      "location": "USA"
    }
  ],
  "bio": "Short professional bio...",
  "languages_spoken": ["English", "Hindi"],
  "consultation_fee": 1000,
  "consultation_duration_minutes": 30,
  "video_consultation_enabled": true,
  "chat_consultation_enabled": true,
  "in_person_enabled": true,
  "address_line1": "Clinic address",
  "city": "Ahmedabad",
  "state": "Gujarat",
  "country": "India",
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

Notes:

- Creates user with `role=doctor`
- Skips email verification (`is_verified=true` on user)
- `password` optional — omit it to send an invite link instead of a password
- Password rules (when supplied): min 8 chars, upper, lower, digit, special character
- `send_welcome_email: false` creates the account silently; use `resend-invite` later
- `is_verified: false` puts the doctor in the pending queue instead of publishing them
- `day_of_week`: `0=Monday` … `6=Sunday`

### Update doctor

```http
PUT /api/v1/admin/doctors/{doctor_id}
Authorization: Bearer <admin_token>
Content-Type: application/json
```

Supported fields include:

- Personal: `full_name`, `email`, `phone`, `title`, `bio`, address, fees, consultation flags
- Credentials: `education`, `certifications`, `qualifications`, `license_number`, `years_of_experience`
- Specializations: `specializations` (**replaces full list**)
- Availability: `availability` (**replaces full schedule**)
- Hospital link: `hospital_id`
- Verify flag: `is_verified`

### Response shape (important for UI)

```json
{
  "specializations": ["Cardiology", "Interventional Cardiology"],
  "specialization_details": [
    {
      "id": "uuid",
      "specialization": "Cardiology",
      "is_primary": true,
      "certification": null
    }
  ],
  "availability": [],
  "education": [],
  "certifications": [],
  "full_name": "...",
  "email": "...",
  "hospital_id": "...",
  "hospital_name": "..."
}
```

Render `specializations` as **strings** (chips/tags).  
Use `specialization_details` when you need IDs / primary flags.

---

## 3. Admin Hospitals

Prefix: `/admin/hospitals`

### CRUD

| Action | Method | Endpoint |
|--------|--------|----------|
| List | `GET` | `/admin/hospitals` |
| Create | `POST` | `/admin/hospitals` |
| Get | `GET` | `/admin/hospitals/{hospital_id}` |
| Update | `PUT` | `/admin/hospitals/{hospital_id}` |
| Delete | `DELETE` | `/admin/hospitals/{hospital_id}` |

### Cover image + gallery fields

Create/update accept **either** naming style:

| Form field | Also accepted |
|------------|---------------|
| `cover_image` | `cover_image_url` |
| `image_gallery` | `gallery` |

Response returns both pairs.

### Create hospital (JSON)

```http
POST /api/v1/admin/hospitals
Authorization: Bearer <admin_token>
Content-Type: application/json
```

```json
{
  "name": "Example Hospital",
  "slug": "example-hospital",
  "description": "Hospital description",
  "email": "info@example.com",
  "phone": "+919999999999",
  "website": "https://example.com",
  "address_line1": "Street address",
  "city": "Ahmedabad",
  "state": "Gujarat",
  "country": "India",
  "postal_code": "380001",
  "cover_image": "/api/v1/images/....jpg",
  "image_gallery": [
    "/api/v1/images/....jpg",
    "/api/v1/images/....mp4"
  ],
  "logo_url": null,
  "is_active": true
}
```

### Media upload endpoints (recommended for admin form)

| Action | Method | Endpoint | Body |
|--------|--------|----------|------|
| Upload cover | `POST` | `/admin/hospitals/{id}/cover-image` | `multipart/form-data` → field `file` |
| Add gallery photos/videos | `POST` | `/admin/hospitals/{id}/gallery` | `multipart/form-data` → field `files` (multiple) |
| Replace full gallery (URLs) | `PUT` | `/admin/hospitals/{id}/gallery` | `{"image_gallery": ["url1","url2"]}` |
| Remove one gallery item | `DELETE` | `/admin/hospitals/{id}/gallery` | `{"url": "..."}` |

Allowed media:

- Images: `jpg`, `jpeg`, `png`, `gif`, `webp`, `svg`
- Videos: `mp4`, `webm`, `mov`, `m4v`

### Recommended frontend flow

1. `POST /admin/hospitals` with basic details
2. `POST /admin/hospitals/{id}/cover-image` with cover file
3. `POST /admin/hospitals/{id}/gallery` with multiple files

Alternative:

1. Upload via `POST /admin/images/upload`
2. Pass returned URLs as `cover_image` / `image_gallery` in create/update

### Doctor ↔ hospital assignment

| Action | Method | Endpoint |
|--------|--------|----------|
| Assign | `POST` | `/admin/doctors/assignments` |
| List | `GET` | `/admin/doctors/assignments` |
| Remove | `DELETE` | `/admin/doctors/assignments/{assignment_id}` |

```json
{
  "doctor_id": "uuid",
  "hospital_id": "uuid",
  "department_id": null,
  "is_primary_department": true
}
```

Also available:

- `GET/POST/PUT /doctors/{doctor_id}/hospital`

---

## 4. Admin Patients

Prefix: `/admin/patients`

### KPIs

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/admin/patients/total` | Total patients |
| `GET` | `/admin/patients/active` | Active patient accounts |
| `GET` | `/admin/patients/with-consultations` | Patients who consulted a doctor |
| `GET` | `/admin/patients/new?days=30` | New registrations |

### Patient list & detail

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/admin/patients` | Paginated list (`search`, `country`, `is_active`) |
| `GET` | `/admin/patients/{patient_id}` | Full profile + stats |

### Consultation track (patient ↔ doctor)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/admin/patients/consultations` | All consultations (filters: `status`, `doctor_id`, `patient_id`, `search`) |
| `GET` | `/admin/patients/{id}/consultations` | Patient consultation list |
| `GET` | `/admin/patients/{id}/consultations/{consultation_id}` | One consultation end-to-end |
| `GET` | `/admin/patients/{id}/history` | Ordered consultation history |

### Records & timeline

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/admin/patients/{id}/records` | Conditions, allergies, medications |
| `GET` | `/admin/patients/{id}/reports` | Medical reports/documents |
| `GET` | `/admin/patients/{id}/bookings` | Hotel/apartment/etc bookings |
| `GET` | `/admin/patients/{id}/timeline` | End-to-end track |

### Suggested frontend pages

1. Dashboard cards → `/total`, `/active`, `/with-consultations`
2. Patients table → `GET /admin/patients`
3. Patient detail → `GET /admin/patients/{id}`
4. Tabs:
   - History → `/history` or `/consultations`
   - Records → `/records`
   - Timeline → `/timeline`
   - Reports → `/reports`
   - Bookings → `/bookings`

---

## 5. Public doctor specialty categories

Used by public doctor pages:

```http
GET /api/v1/doctors/category
```

Also available: `/api/v1/doctors/categories`

Response example:

```json
[
  { "id": "Cardiology", "name": "Cardiology", "count": 3 }
]
```

---

## 6. Seeded doctor login credentials (local/dev seed)

If doctors were created via the seed script:

**Password for all:** `Doctor@123456`

| Doctor | Email |
|--------|--------|
| Dr. Shadab R. Doi | `drdoisns@gmail.com` |
| Dr. Shiraz Ahmed Munshi | `shiraz.munshi@cheershospitals.com` |
| Dr. Manish Dhawan | `manish.dhawan@fusionkidney.com` |
| Dr. Pranjel Pipara | `pranjel.pipara@orthosport.com` |
| Dr. Farhanahmed F. Pirzada | `DRFARHAN_PIRZADA@YAHOO.COM` |
| Dr. Jayesh Amin | `jayesh.amin@novaivffertility.com` |

---

## 7. Quick integration checklist

- [ ] Admin login uses `/auth/admin/login` only
- [ ] Public login uses `/auth/login` only
- [ ] Separate token storage for admin vs public
- [ ] Doctor create uses `POST /admin/doctors`
- [ ] Doctor edit tabs all use `PUT /admin/doctors/{id}`
- [ ] Specializations rendered as strings (not objects)
- [ ] Hospital form supports `cover_image` + `image_gallery`
- [ ] Hospital media uploaded via cover/gallery endpoints
- [ ] Patient admin screens wired to `/admin/patients/*`

---

## 8. Swagger

After deploy/restart, check:

- **Authentication** → `/auth/admin/login`
- **Admin - Doctors**
- **Admin - Hospitals**
- **Admin - Patients**
- **Doctors** → `/doctors/category`
