# Copilot Instructions

## What This Is

A production-grade **Medical Tourism Platform** backend — FastAPI + SQLAlchemy 2.0 async + PostgreSQL. It provides REST APIs for patient/doctor management, appointment scheduling, hospital bookings, CMS, RBAC, WebSocket chat, AI assistant integration, and forex exchange. All routes are versioned under `/api/v1`.

---

## Commands

```bash
# Run dev server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run all tests
pytest tests/ -v

# Run a single test file
pytest tests/test_auth.py -v

# Run a single test
pytest tests/test_auth.py::test_login_invalid_credentials -v

# Run migrations
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "description"

# Lint / format
black app/ tests/
isort app/ tests/
flake8 app/ tests/
mypy app/
```

Tests use SQLite (`test.db`) — no PostgreSQL required for running the test suite.

### Test Fixtures (`tests/conftest.py`)

- `db_session` — creates all tables in `test.db`, yields an `AsyncSession`, drops all tables after each test (function scope)
- `client` — overrides `get_db` with `db_session` and yields an `httpx.AsyncClient` against the app

```python
@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
```

---

## Architecture

### Layer Hierarchy

```
app/api/v1/       → HTTP layer: request parsing, auth deps, calls service
app/services/     → Business logic: all DB queries, validation, side effects
app/models/       → SQLAlchemy ORM models (PostgreSQL)
app/schemas/      → Pydantic v2 request/response schemas
app/core/         → Config, security (JWT), middleware, dependencies (DI/RBAC)
app/db/           → Engine, session factory, DB seeding
app/utils/        → Enums, constants, helpers (incl. google_meet.py, email_sender.py)
```

Routers are thin — they only parse/validate input, resolve dependencies, and delegate to a service. All business logic lives in `app/services/`.

### Route Registration

All routers are registered in `app/api/v1/api_router.py` and mounted at `/api/v1` in `main.py`. To add a new domain: create `app/api/v1/my_domain.py`, import and register it in `api_router.py`.

**Public routers:** `auth`, `users`, `patients`, `doctors`, `hospitals`, `departments`, `consultations`, `appointments`, `hotels`, `apartments`, `stays`, `restaurants`, `bookings`, `payments`, `chat`, `ai`, `cms`, `pages`, `forex`, `leads`, `notifications`, `email`, `events`, `config`, `documents`, `patient_documents`, `patient_medical_records`, `patient_medical_reports`, `reviews`, `rbac`

**Admin routers (prefix `/admin/`):** `site`, `rbac`, `dashboard`, `hospitals`, `departments`, `doctors`, `hotels`, `apartments`, `restaurants`, `forex`

Admin routers in separate files: `admin_doctor.py` ≠ `doctors.py`, `admin_hotel.py` ≠ `hotels.py`, etc.

### Startup Behavior

On startup (`main.py` lifespan):
- If `DEBUG=True`, runs `Base.metadata.create_all` (dev only — use Alembic in production)
- Always runs `init_database()` which seeds the default superuser from env vars

---

## Appointment Scheduling Flow

Patient-facing endpoints live at `/api/v1/appointments` (`app/api/v1/appointments.py`).  
Core logic is in `app/services/appointment_service.py`.

### Step-by-step flow

```
1. Browse doctors         GET /api/v1/doctors
2. Get available slots    GET /api/v1/appointments/doctors/{doctor_id}/available-slots
                              ?date=2024-01-24&consultation_type=video
3. Book appointment       POST /api/v1/appointments
4. View my appointments   GET /api/v1/appointments/me
5. View one appointment   GET /api/v1/appointments/{id}
6. Cancel appointment     POST /api/v1/appointments/{id}/cancel
```

### Slot availability (`GET …/available-slots`)

The service uses `DoctorAvailability` (table `doctor_availability`) to find the doctor's working window for the requested day of week, then:
1. Generates all time slots: `start_time → end_time` in `slot_duration_minutes` steps
2. Removes slots that fall inside the doctor's break (`break_start_time` / `break_end_time`)
3. Queries `consultations` for the same doctor and date where `status IN (scheduled, waiting, in_progress)`
4. Marks those slots `is_available: false` — frontend should grey them out / disable selection

### `POST /appointments` — what happens on submit

```
AppointmentCreate body:
  doctor_id, consultation_type (video | chat | in_person | phone),
  scheduled_date, scheduled_time, duration_minutes,
  reason, symptoms, symptom_duration, timezone

Service (AppointmentService.schedule_appointment):
  1. Validate doctor exists + supports requested consultation_type
  2. Re-check slot availability (race-condition guard)
  3. INSERT Consultation (status=scheduled, reference CNS-YYYYMMDD-XXXXXX)
  4. INSERT Booking     (status=confirmed,  reference BKG-YYYYMMDD-XXXXXX,
                         linked via Booking.consultation_id)
  5. If consultation_type == VIDEO:
       → create_meet_event() in app/utils/google_meet.py
       → stores meet_link + google_event_id in Consultation.session_data (JSONB)
  6. INSERT Event for patient (entity_type="consultation", meeting_url=meet_link)
  7. INSERT Event for doctor  (entity_type="consultation", meeting_url=meet_link)
  8. COMMIT
  9. send_email() to patient  (HTML template with Meet link, date, doctor name)
 10. send_email() to doctor   (HTML template with patient name, reason, Meet link)

Returns: AppointmentResponse (includes meet_link, booking_reference, event IDs)
```

Emails and the Google Meet call are **best-effort** — a failure does not roll back the booking.

### Google Meet integration (`app/utils/google_meet.py`)

Requires a Google **service account** with Calendar API enabled and domain-wide delegation:

```
GOOGLE_CALENDAR_ENABLED=True
GOOGLE_SERVICE_ACCOUNT_JSON=./google-service-account.json
GOOGLE_CALENDAR_TIMEZONE=UTC
```

When disabled (default), `create_meet_event()` returns `{}` — the appointment is still created without a Meet link.

### Email (`app/utils/email_sender.py`)

Uses `smtplib` via `asyncio.to_thread`. Configure via env:

```
SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_USE_TLS
EMAIL_FROM_ADDRESS, EMAIL_FROM_NAME
```

Every send (success or failure) writes an `EmailLog` record to the database. HTML templates are rendered in `app/utils/email_sender.py` (`render_appointment_confirmation_html`, `render_doctor_appointment_html`).

### Key models involved

| Model | Table | Purpose |
|---|---|---|
| `Consultation` | `consultations` | Core appointment record; `session_data` JSONB holds `meet_link` |
| `Booking` | `bookings` | Financial/status tracking; linked via `consultation_id` |
| `DoctorAvailability` | `doctor_availability` | Weekly schedule per doctor; `day_of_week` 0=Mon |
| `Event` | `events` | Calendar entry for both doctor and patient users |
| `EmailLog` | `email_logs` | Audit trail for every email sent |

---

## Booking Flow (General)

`Booking` is a **polymorphic** record linking to consultation, hotel room, or restaurant.

```
BookingType: CONSULTATION | HOTEL | APARTMENT | RESTAURANT | PACKAGE
BookingStatus: PENDING → CONFIRMED → IN_PROGRESS → COMPLETED
                      └→ CANCELLED | NO_SHOW
```

All booking creation sets `status=PENDING` (except appointments which set `CONFIRMED` immediately). `confirmed_at` / `confirmed_by` are stamped on confirmation. Cancellation stores `cancelled_at`, `cancellation_reason`, `cancelled_by`, and optionally computes `refund_amount` (80% default).

`Booking.booking_metadata` (JSONB) and `guest_details` (JSONB) hold type-specific extra data.

---

## CMS Structure

Two tables: `cms_pages` → `cms_blocks` (one-to-many, ordered by `position`).

### `CMSPage` key fields

```
slug          Unique URL key (e.g. "home", "services", "doctors")
template      Page layout hint for frontend ("default", "landing", …)
status        draft | published | archived
parent_id     UUID FK to self — enables hierarchical page trees
settings      JSONB — arbitrary page-level config
```

SEO fields: `meta_title`, `meta_description`, `meta_keywords`, `canonical_url`, `og_title`, `og_description`, `og_image`.

### `CMSBlock` key fields

```
block_type    See enum below
position      Integer ordering within the page (lowest first)
section       header | main | sidebar | footer
config        JSONB — block-type-specific settings (typed configs in cms_extended.py)
items         JSONB array — used for FAQ, testimonials, features, team lists
is_visible    Bool; also supports visible_from / visible_until date windows
hide_on_mobile / hide_on_desktop  Responsive visibility flags
```

### Block types (`CMSBlockType` enum)

| Type | `items` / `config` shape | Use |
|---|---|---|
| `hero` | `HeroBlockConfig` | Full-width hero banner with CTAs |
| `text` | `content` field (HTML) | Rich-text paragraphs |
| `image` | `image_url`, `config.caption` | Single image |
| `gallery` | `items: [{url, caption}]` | Image grid |
| `faq` | `items: [{question, answer}]` | Accordion FAQs |
| `testimonial` | `items: [{name, text, rating, avatar}]` | Patient reviews |
| `cta` | `cta_text`, `cta_url`, `cta_style` | Call-to-action banner |
| `video` | `video_url`, `config.thumbnail` | Embedded video |
| `features` | `items: [{icon, title, description}]` | Feature grid |
| `pricing` | `items: [{name, price, features[]}]` | Pricing cards |
| `team` | `items: [{name, title, photo, bio}]` | Team member grid |
| `contact` | `config: ContactInfo` | Contact details block |
| `custom` | Any JSONB | Escape hatch for custom blocks |

Extended typed configs for Flora Medical (`app/schemas/cms_extended.py`):  
`HeroBlockConfig`, `StatsGridConfig`, `ServiceCardItem`, `ListingGridConfig`,  
`DoctorCardItem`, `HospitalCardItem`, `FAQItem`, `TestimonialsConfig`, `TeamConfig`.

---

## Key Conventions

### Required Environment Variables

Only two vars have no defaults and **must** be set:
```
DATABASE_URL=postgresql+asyncpg://user:pass@host/db
SECRET_KEY=<random-secret>
```
All other settings have defaults (see `app/core/config.py`).

### Database Sessions

The session dependency auto-commits on success and auto-rolls back on exception. Never manually commit inside a service — just raise on error.

```python
async def my_endpoint(db: DatabaseSession):
    service = MyService(db)
    return await service.do_something()
```

The `AppointmentService` is an exception: it calls `await self.db.commit()` explicitly before triggering side-effects (email/calendar) so the booking is persisted even if a side-effect fails.

### Service Pattern

Every domain has a service class injected with `AsyncSession`:

```python
class MyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, id: UUID) -> Optional[MyModel]:
        result = await self.db.execute(
            select(MyModel).where(MyModel.id == id, MyModel.is_deleted == False)
        )
        return result.scalar_one_or_none()
```

### Authentication & RBAC

Import pre-built dependency constants from `app.api.deps` (re-exports `app.core.dependencies`):

```python
from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin, RequireDoctor

@router.get("/admin/data", dependencies=[RequireAdmin])
async def admin_only(db: DatabaseSession): ...

@router.get("/me")
async def get_me(current_user: CurrentUser, db: DatabaseSession): ...
```

Available guards: `RequireSuperAdmin`, `RequireAdmin`, `RequireDoctor`, `RequirePatient`, `RequireHotelManager`, `RequireRestaurantManager`.  
Role hierarchy: `super_admin > admin > role-specific`.

JWT tokens are Bearer tokens. `decode_token()` in `app/core/security.py` returns `None` on invalid — never raises.

### Models

All models extend `BaseModel` from `app/models/base.py`:
- `id: UUID` (PK, auto-generated)
- `created_at`, `updated_at` (auto-managed)
- `created_by`, `updated_by` (FK → `users.id`)
- `is_deleted`, `deleted_at`, `deleted_by` (soft delete)

Use `SimpleBaseModel` only for system/config tables without audit needs.

**Always filter soft-deleted records**: `where(Model.is_deleted == False)`.  
Use `.soft_delete(deleted_by=user.id)` instead of `db.delete()`.

### Pagination

All list endpoints return `PaginatedResponse[Schema]`:

```python
items, total = await service.get_list(page=page, page_size=page_size)
return PaginatedResponse.create(items, total, page, page_size)
```

`PaginationParams` and `PaginatedResponse` are in `app/schemas/common.py`.

### Schemas

Pydantic v2 schemas in `app/schemas/`. Separate from models — no mixing. Common bases (`BaseSchema`, `PaginationParams`, `MessageResponse`, `BasicResponse`) in `app/schemas/common.py`.

### Enums

All status/type enums in `app/utils/enums.py`. Always use `.value` when comparing:  
`User.role == UserRole.ADMIN.value`.

### Logging

```python
from app.core.logging import get_logger
logger = get_logger(__name__)

logger.info("appointment_scheduled", ref=ref, type=type_)
logger.error("email_send_failed", to=email, error=str(exc))
```

Event names: `snake_case` strings. Key-value pairs for context — never f-strings.

### File Uploads

Stored in `settings.UPLOAD_DIR` (`./uploads/`), served at `/static/uploads/`. Max size: `settings.MAX_UPLOAD_SIZE_MB` (default 10 MB).

### Configuration

All settings from `.env` via `app/core/config.py` (pydantic-settings). Use `from app.core.config import settings`.

---

## Project-Specific Notes

- `app/api/deps.py` is a re-export shim for `app/core/dependencies.py` — always import from `app.api.deps` in routers.
- Patient profiles are lazily created: `PatientService.get_or_create(user_id)`.
- Admin endpoints (`/admin/*`) are separate routers from public ones — `admin_doctor.py` ≠ `doctors.py`.
- Alembic is configured for async migrations — `alembic/env.py` uses `run_async_migrations()`.
- `CORS_ORIGINS` in `.env` accepts a JSON array string or comma-separated — the validator handles both.
- `Consultation.session_data` (JSONB) stores `{meet_link, google_event_id, platform}` for video appointments.
- Reference numbers follow `PREFIX-YYYYMMDD-XXXXXX` format (e.g. `CNS-20240124-AB12CD`, `BKG-20240124-XY78ZW`) via `generate_reference_id()` in `app/utils/helpers.py`.
- `BaseModel.restore()` reverses a soft delete (clears `is_deleted`, `deleted_at`, `deleted_by`).
- `scripts/create_super_admin.py` — one-off script to seed a superuser; `scripts/seed_rbac.py` — seeds default RBAC roles/permissions.

