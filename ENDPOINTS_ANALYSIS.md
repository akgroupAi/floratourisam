# Flora Medical Tourism Platform - Complete Endpoints Analysis

**Last Updated:** April 12, 2026  
**Platform:** FastAPI + SQLAlchemy 2.0 async + PostgreSQL  
**API Prefix:** `/api/v1`

---

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Authentication & Authorization](#authentication--authorization)
3. [Core Domain Endpoints](#core-domain-endpoints)
4. [Medical Services](#medical-services)
5. [Accommodation & Dining](#accommodation--dining)
6. [Bookings & Payments](#bookings--payments)
7. [Communication & AI](#communication--ai)
8. [CMS & Content](#cms--content)
9. [Admin Integration](#admin-integration)
10. [Data Models & Schemas](#data-models--schemas)
11. [Key Design Patterns](#key-design-patterns)

---

## 🏗️ Architecture Overview

### Layer Structure

```
HTTP Layer (API Routers)      → Request validation, auth checks, delegates to service
Business Logic Layer (Services) → DB queries, validation, side effects, transactions
ORM Layer (Models)             → SQLAlchemy model definitions, soft delete, audit fields
Schema Layer (Pydantic v2)    → Request/Response validation, type safety
Core Layer                     → Config, JWT security, dependencies, utilities
```

### Key Files/Folders

```
app/
├── api/v1/                   # All endpoint routers (42 public + admin routers)
├── models/                   # SQLAlchemy ORM models (23 domain models)
├── schemas/                  # Pydantic v2 request/response schemas
├── services/                 # Business logic services (core layer)
├── core/
│   ├── config.py            # .env configuration
│   ├── security.py          # JWT token handling
│   ├── dependencies.py      # DI + RBAC guards
│   └── middleware.py        # Exception handlers, CORS, etc.
├── db/
│   ├── session.py           # AsyncSession factory
│   ├── init_db.py           # DB initialization
│   └── base.py              # SQLAlchemy declarative base
└── utils/
    ├── enums.py            # Status enums, role enums
    ├── helpers.py          # Reference ID generators, etc.
    ├── email_sender.py     # SMTP email service
    └── google_meet.py      # Google Calendar/Meet integration
```

### Environment Configuration

**Required environment vars:**
```
DATABASE_URL=postgresql+asyncpg://user:pass@host/db
SECRET_KEY=<random-string>
```

**Optional (have defaults):**
- `APP_NAME`, `APP_VERSION`, `DEBUG`, `ENVIRONMENT`
- `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`
- `CORS_ORIGINS`, `LOG_LEVEL`, `REDIS_URL`
- `MAX_UPLOAD_SIZE_MB`, `UPLOAD_DIR`
- Email: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`
- Google: `GOOGLE_CALENDAR_ENABLED`, `GOOGLE_SERVICE_ACCOUNT_JSON`
- Stripe: `STRIPE_API_KEY`, `STRIPE_SECRET_KEY`

---

## 🔐 Authentication & Authorization

### Auth Endpoints (`/api/v1/auth`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| POST | `/auth/register` | None | Register new user (patient/doctor/etc) |
| POST | `/auth/login` | None | Login with email + password |
| POST | `/auth/refresh` | Bearer | Refresh expired access token |
| POST | `/auth/verify-email` | None | Confirm email via token |
| POST | `/auth/resend-verify` | None | Resend verification email |
| POST | `/auth/request-reset` | None | Request password reset email |
| POST | `/auth/reset-password` | None | Confirm reset with token |
| POST | `/auth/change-password` | Bearer | User changes own password |
| POST | `/auth/logout` | Bearer | Logout (optional - tokens are stateless) |

**Request Schemas:**
```python
LoginRequest(email, password)
RegisterRequest(email, password, full_name, role, phone?, emergency_contact?)
ChangePasswordRequest(old_password, new_password)
PasswordResetRequest(email)
PasswordResetConfirm(token, new_password)
VerifyEmailRequest(token)
```

**Response:**
```python
TokenResponse(access_token, refresh_token, token_type)
AuthResponse(user, token)
```

**Key Guards Available:**
- `RequireSuperAdmin` — Only super_admin role
- `RequireAdmin` — super_admin or admin
- `RequireDoctor` — doctor role
- `RequirePatient` — patient role
- `RequireHotelManager` — hotel_manager role
- `RequireRestaurantManager` — restaurant_manager role

**JWT Token Structure:**
- Bearer token with user ID, role, permissions
- `decode_token()` returns `None` on failure
- Use `current_user: CurrentUser` dependency to inject

---

## 👤 Core Domain Endpoints

### Users (`/api/v1/users`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/users/me` | Bearer | Get current user profile |
| PUT | `/users/me` | Bearer | Update current user |
| POST | `/users/me/avatar` | Bearer | Upload avatar image |
| GET | `/users` | Admin | List all users (paginated) |
| POST | `/users` | Admin | Create new user (admin) |
| GET | `/users/stats` | Admin | Get user statistics |
| GET | `/users/{user_id}` | Admin | Get user by ID (admin) |
| PUT | `/users/{user_id}` | Admin | Update user (admin) |
| DELETE | `/users/{user_id}` | Admin | Delete/soft-delete user (admin) |

**Query Params (list):**
- `page` (default=1), `page_size` (default=20, max=100)
- `role` (filter by UserRole enum)
- `is_active` (boolean)
- `search` (full-text search on name/email)

**Schemas:**
```python
UserResponse          # Full user with sensitive fields
UserListResponse      # Public list view
UserProfileResponse   # Admin view with stats
UserUpdate           # Profile updates (name, phone, etc.)
UserAdminUpdate      # Admin panel updates (role, is_active, etc.)
```

### Patients (`/api/v1/patients`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/patients/me` | Patient | Get own patient profile |
| PUT | `/patients/me` | Patient | Update own profile |
| GET | `/patients/me/insurance` | Patient | Get insurance details |
| PUT | `/patients/me/insurance` | Patient | Update insurance |
| GET | `/patients` | Admin | List all patients |
| GET | `/patients/{patient_id}` | Admin | Get patient details |

**Schemas:**
```python
PatientResponse         # Public patient info
PatientDetailResponse   # Full medical history, insurance
PatientUpdate          # Profile updates
```

**Notes:**
- Lazy-created on first access via `PatientService.get_or_create(user_id)`
- Contains medical history, emergency contacts, insurance

### Doctors (`/api/v1/doctors`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/doctors` | None | List doctors (paginated, searchable) |
| GET | `/doctors/basic` | None | Get basic doctor info (for dropdowns) |
| GET | `/doctors/me` | Doctor | Get own doctor profile |
| GET | `/doctors/me/stats` | Doctor | Get doctor dashboard stats |
| GET | `/doctors/{doctor_id}` | None | Get doctor details (public) |
| GET | `/doctors/{doctor_id}/reviews` | None | Get doctor reviews |
| GET | `/doctors/{doctor_id}/availability` | None | Check doctor availability |

**Query Params (list):**
- `page` (default=1), `page_size` (default=20)
- `specialization` (filter by specialty)
- `hospital_id` (filter by hospital)
- `search` (full-text)
- `sort_by` (recommended, experience, rating, etc.)

**Doctor Stats Response:**
```json
{
  "doctor_id": "uuid",
  "total_consultations": 42,
  "total_patients": 28,
  "rating": 4.8,
  "total_reviews": 15,
  "consultation_fee": 150.00,
  "years_of_experience": 12,
  "is_verified": true
}
```

**Schemas:**
```python
DoctorResponse          # Full details with specialization, fees
DoctorListResponse      # List view (condensed)
DoctorUpdate           # Update profile
```

### Hospitals (`/api/v1/hospitals`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/hospitals` | None | List hospitals (city, amenity filters) |
| GET | `/hospitals/{hospital_id}` | None | Get hospital details |
| GET | `/hospitals/{hospital_id}/departments` | None | Get departments |
| GET | `/hospitals/{hospital_id}/doctors` | None | Get doctors in hospital |
| GET | `/hospitals/{hospital_id}/reviews` | None | Get hospital reviews |

**Query Params:**
- `city` (filter)
- `specialization` (filter)
- `min_rating` (filter)
- `amenities` (array filter: wifi, pool, medical_support, etc.)

### Departments (`/api/v1/departments`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/departments` | None | List departments |
| GET | `/departments/{dept_id}` | None | Get department details |
| GET | `/departments/{dept_id}/doctors` | None | Get doctors in department |

---

## 🏥 Medical Services

### Consultations (`/api/v1/consultations`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/consultations` | Bearer | List user's consultations |
| POST | `/consultations` | Patient | Create consultation booking |
| GET | `/consultations/{id}` | Bearer | Get consultation details |
| POST | `/consultations/{id}/cancel` | Bearer | Cancel consultation |
| POST | `/consultations/{id}/join` | Bearer | Get session details for join |

**Schemas:**
```python
ConsultationCreate(doctor_id, consultation_type, reason, symptoms)
ConsultationResponse(id, doctor, patient, status, scheduled_at, meet_link, ...)
ConsultationListResponse(id, doctor_name, status, scheduled_at)
```

**Status Values:**
- `pending`, `scheduled`, `waiting`, `in_progress`, `completed`, `cancelled`, `no_show`

### Appointments (`/api/v1/appointments`)

**Patient-facing flow:**

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/appointments/doctors/{doctor_id}/available-slots` | None | Get open slots |
| POST | `/appointments` | Patient | Schedule appointment |
| GET | `/appointments/me` | Patient | Get own appointments |
| GET | `/appointments/{id}` | Bearer | Get appointment details |
| PUT | `/appointments/{id}/reschedule` | Patient | Reschedule appointment |
| POST | `/appointments/{id}/cancel` | Patient | Cancel appointment |

**Doctor schedule management:**

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/appointments/schedule/me` | Doctor | Get availability windows |
| POST | `/appointments/schedule` | Doctor | Add availability window |
| PUT | `/appointments/schedule/{id}` | Doctor | Update availability |
| DELETE | `/appointments/schedule/{id}` | Doctor | Remove availability |

**Available Slots Query:**
```
GET /appointments/doctors/{doctor_id}/available-slots?date=2024-01-24&consultation_type=video
```

Returns:
```python
{
  "doctor_id": "uuid",
  "date": "2024-01-24",
  "slots": [
    {"time": "09:00", "is_available": true},
    {"time": "09:30", "is_available": false},  # Already booked
    {"time": "10:00", "is_available": true},
  ],
  "consultation_types": ["video", "in_person"]
}
```

**Schedule Management:**
```python
DoctorAvailabilityCreate(
  day_of_week: int,      # 0=Monday, 6=Sunday
  start_time: time,      # 09:00
  end_time: time,        # 17:00
  slot_duration_minutes: int = 30,
  max_appointments: Optional[int] = None,
  break_start_time: Optional[time] = None,
  break_end_time: Optional[time] = None,
)
```

**Appointment Booking Flow:**
1. Browse doctors: `GET /doctors`
2. Get slots: `GET /appointments/doctors/{id}/available-slots?date=...&type=video`
3. Book: `POST /appointments` with `AppointmentCreate`
4. Confirmation email sent immediately (best-effort)
5. Google Meet link created (if video type + enabled)
6. Calendar events created for both patient & doctor

**Key Features:**
- Reference numbers: `CNS-YYYYMMDD-XXXXXX` (consultation), `BKG-YYYYMMDD-XXXXXX` (booking)
- Google Meet integration: `session_data` JSONB holds `{meet_link, google_event_id, platform}`
- Email templates: HTML with appointment details, doctor info, Meet link
- Race condition guard: Re-check slot availability at booking time

---

## 🏨 Accommodation & Dining

### Hotels (`/api/v1/hotels`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/hotels` | None | List hotels with filters |
| GET | `/hotels/{hotel_id}` | None | Get hotel details |
| GET | `/hotels/{hotel_id}/facilities` | None | Get hotel facilities |
| GET | `/hotels/{hotel_id}/policies` | None | Get hotel policies |
| GET | `/hotels/{hotel_id}/rooms` | None | List hotel rooms |
| GET | `/hotels/{hotel_id}/rooms/{room_id}/availability` | None | Check room availability |
| GET | `/hotels/{hotel_id}/reviews` | None | List hotel reviews |
| GET | `/hotels/{hotel_id}/reviews/summary` | None | Get review summary |
| POST | `/hotels/{hotel_id}/reviews` | Patient | Submit review |

**Query Params (list):**
- `page`, `page_size`
- `city`, `min_price`, `max_price`, `min_rating`
- `amenities` (array: wifi, pool, spa, gym, restaurant, kitchen, medical_support)
- `sort_by` (recommended, price_low_to_high, highest_rated, most_reviews)

**Room Availability Check:**
```
GET /hotels/{id}/rooms/{room_id}/availability?check_in=2024-01-24&check_out=2024-01-28

Response:
{
  "room_id": "uuid",
  "check_in": "2024-01-24",
  "check_out": "2024-01-28",
  "nights": 4,
  "available": true
}
```

### Apartments (`/api/v1/apartments`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/apartments` | None | List apartments |
| GET | `/apartments/{id}` | None | Get apartment details |
| GET | `/apartments/{id}/availability` | None | Check availability |
| GET | `/apartments/{id}/reviews` | None | List reviews |
| POST | `/apartments/{id}/reviews` | Patient | Submit review |

**Features:**
- Flexible pricing: Monthly, weekly, nightly rates
- Amenities: WiFi, kitchen, washer, etc.

### Stays (Apartment Booking) (`/api/v1/stays`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| POST | `/stays` | Patient | Book an apartment stay |
| GET | `/stays/me` | Patient | Get own stays |
| GET | `/stays/{id}` | Patient | Get stay details |
| POST | `/stays/{id}/cancel` | Patient | Cancel stay |

### Restaurants (`/api/v1/restaurants`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/restaurants/all` | None | List all restaurants (minimal) |
| GET | `/restaurants` | None | List restaurants (paginated, filtered) |
| GET | `/restaurants/{id}` | None | Get restaurant details |
| GET | `/restaurants/{id}/menu` | None | Get full menu |
| GET | `/restaurants/{id}/reviews` | None | List reviews |
| POST | `/restaurants/{id}/reviews` | Patient | Submit review |

**Dining Passes:**

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/restaurants/{id}/dining-passes` | None | List dining passes |
| POST | `/restaurants/{dining_pass_id}/purchase` | Patient | Purchase dining pass |
| GET | `/restaurants/passes/my-passes` | Patient | Get own purchased passes |
| POST | `/restaurants/passes/{purchase_id}/redeem` | Patient/Staff | Redeem pass tokens |

**Dining Pass Model:**
```python
{
  "id": "uuid",
  "reference_code": "DP-20240124-ABC123",
  "pass_name": "7-Day Breakfast Pass",
  "tokens_total": 7,
  "tokens_used": 2,
  "tokens_remaining": 5,
  "percentage_used": 28.6,
  "purchased_at": "2024-01-15T10:00:00Z",
  "expires_at": "2024-01-22T23:59:59Z",
  "days_left": 5,
  "amount_paid": 150.00,
  "currency": "USD",
  "status": "active"  # active, expired, fully_used
}
```

### Reviews & Ratings (`/api/v1/reviews`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/reviews/{entity_type}/{entity_id}` | None | Get entity reviews |
| GET | `/reviews/{entity_type}/{entity_id}/summary` | None | Get review summary |
| POST | `/reviews/{entity_type}/{entity_id}` | Patient | Submit review |
| PUT | `/reviews/{review_id}` | Reviewer | Update review |
| DELETE | `/reviews/{review_id}` | Reviewer/Admin | Delete review |
| POST | `/reviews/{review_id}/helpful` | Patient | Mark as helpful |

**Entity Types:** `hotel`, `apartment`, `doctor`, `restaurant`, `hospital`

**Review Summary:**
```json
{
  "entity_id": "uuid",
  "total_reviews": 42,
  "average_rating": 4.6,
  "distribution": {
    "5": 25,
    "4": 12,
    "3": 3,
    "2": 1,
    "1": 1
  },
  "recent_reviews": [...]
}
```

---

## 💳 Bookings & Payments

### Bookings (`/api/v1/bookings`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/bookings/rooms/{room_id}/availability` | None | Check room availability |
| POST | `/bookings/hotel` | Patient | Book hotel room |
| POST | `/bookings/apartment` | Patient | Book apartment |
| POST | `/bookings/restaurant` | Patient | Reserve restaurant table |
| GET | `/bookings/me` | Patient | Get own bookings |
| GET | `/bookings/{id}` | Bearer | Get booking details |
| POST | `/bookings/{id}/cancel` | Patient | Cancel booking |
| PUT | `/bookings/{id}/status` | Admin | Update booking status |

**Booking Model:**
```python
{
  "id": "uuid",
  "booking_type": "HOTEL",  # CONSULTATION, HOTEL, APARTMENT, RESTAURANT, PACKAGE
  "status": "CONFIRMED",    # PENDING, CONFIRMED, IN_PROGRESS, COMPLETED, CANCELLED
  "reference": "BKG-20240124-XY78ZW",
  "patient_id": "uuid",
  "total_price": 500.00,
  "currency": "USD",
  "confirmed_at": "2024-01-15T10:00:00Z",
  "confirmed_by": "uuid",
  "cancelled_at": null,
  "cancellation_reason": null,
  "refund_amount": 400.00,  # 80% of total by default
  "booking_metadata": {...},  # Type-specific data
  "guest_details": {...}     # JSONB guest info
}
```

**Hotel Booking:**
```python
HotelBookingCreate(
  room_id: UUID,
  check_in_date: date,
  check_out_date: date,
  guest_name: str,
  guest_email: str,
  guest_phone: str,
  special_requests: Optional[str]
)
```

**Apartment Booking:**
```python
ApartmentBookingCreate(
  apartment_id: UUID,
  check_in_date: date,
  check_out_date: date,
  guest_name: str,
  guest_email: str,
  guest_phone: str
)
```

**Restaurant Booking:**
```python
RestaurantBookingCreate(
  restaurant_id: UUID,
  reservation_date: date,
  reservation_time: time,
  num_guests: int,
  special_requests: Optional[str]
)
```

**Price Calculation:**
- Hotels: `price = room.price_per_night × nights + 10% tax`
- Apartments: Uses monthly rate (≥28 nights), weekly (≥7 nights), or nightly
- Restaurants: Table reservation free, but food pre-orders charged

### Payments (`/api/v1/payments`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/payments` | Patient | List own payments |
| GET | `/payments/{payment_id}` | Bearer | Get payment details |
| POST | `/payments/stripe/checkout` | Patient | Create Stripe checkout session |
| POST | `/payments/stripe/payment-intent` | Patient | Create Stripe PaymentIntent |
| POST | `/payments/stripe/webhook` | None | Stripe webhook handler |
| POST | `/payments/{payment_id}/refund` | Admin | Issue refund |

**Stripe Integration:**

```python
StripeCheckoutRequest(
  booking_id: UUID,
  amount: float,
  currency: str = "usd",
  description: Optional[str]
)

StripePaymentIntentRequest(
  booking_id: UUID,
  amount: float,
  currency: str = "usd"
)
```

**Response:**
```json
{
  "session_id": "cs_live_...",
  "url": "https://checkout.stripe.com/pay/cs_live_...",
  "client_secret": "pi_1234_secret_5678"
}
```

**Payment Statuses:**
- `pending`, `processing`, `completed`, `failed`, `refunded`, `partially_refunded`

---

## 💬 Communication & AI

### Chat (`/api/v1/chat`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/chat/rooms` | Bearer | List chat rooms |
| POST | `/chat/rooms` | Bearer | Create chat room |
| GET | `/chat/rooms/{room_id}/messages` | Bearer | Get messages (paginated) |
| POST | `/chat/rooms/{room_id}/messages` | Bearer | Send message |
| WEBSOCKET | `/chat/ws/{room_id}` | None | WebSocket real-time chat |

**WebSocket Endpoint:**
```
wss://api.flora.local/api/v1/chat/ws/{room_id}?token={jwt_token}
```

### AI Assistant (`/api/v1/ai`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| POST | `/ai/chat` | Bearer | Send message to AI |
| GET | `/ai/conversations` | Bearer | List conversations (paginated) |
| GET | `/ai/conversations/{conversation_id}` | Bearer | Get conversation |
| POST | `/ai/feedback` | Bearer | Submit feedback on response |

**AI Chat Request:**
```python
AIChatRequest(
  message: str,
  session_id: Optional[UUID],
  context_type: Optional[str]  # "treatment", "booking", "general"
)
```

**AI Chat Response:**
```python
AIChatResponse(
  response: str,
  session_id: UUID,
  intent: str,              # "booking", "inquiry", "greeting"
  confidence: float,        # 0.0-1.0
  suggestions: List[str]   # Follow-up options
)
```

**Features:**
- Stateful conversation tracking (session_id)
- Context-aware responses (treatment vs booking)
- Intent detection
- Confidence scoring
- Smart suggestions for next actions

---

## 📄 CMS & Content

### CMS Pages & Blocks (`/api/v1/cms`)

**Public Endpoints:**

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/cms/pages/{slug}` | None | Get published page by slug |
| GET | `/cms/menu` | None | Get navigation menu |

**Admin Endpoints:**

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/cms/admin/pages` | Admin | List pages (paginated) |
| POST | `/cms/admin/pages` | Admin | Create page |
| GET | `/cms/admin/pages/{page_id}` | Admin | Get page by ID |
| PUT | `/cms/admin/pages/{page_id}` | Admin | Update page |
| DELETE | `/cms/admin/pages/{page_id}` | Admin | Delete page |
| POST | `/cms/admin/pages/{page_id}/blocks` | Admin | Add block to page |
| PUT | `/cms/admin/blocks/{block_id}` | Admin | Update block |
| DELETE | `/cms/admin/blocks/{block_id}` | Admin | Delete block |
| POST | `/cms/admin/blocks/reorder` | Admin | Reorder blocks |

**CMS Page Model:**
```python
{
  "id": "uuid",
  "title": "Home",
  "slug": "home",
  "description": "Landing page",
  "template": "default",
  "status": "published",  # draft, published, archived
  "show_in_menu": true,
  "menu_order": 1,
  "meta_title": "Flora Medical - Home",
  "meta_description": "Best medical tourism platform",
  "meta_keywords": "medical, tourism, healthcare",
  "canonical_url": "https://flora.local/",
  "og_title": "Flora Medical",
  "og_description": "...",
  "og_image": "...",
  "blocks": [...]
}
```

**CMS Block Types:**

| Type | Config | Items | Purpose |
|------|--------|-------|---------|
| `hero` | HeroBlockConfig | N/A | Full-width hero banner with CTAs |
| `text` | N/A | N/A | Content (HTML) |
| `image` | {caption} | N/A | Single image |
| `gallery` | N/A | [{url, caption}] | Image grid |
| `faq` | N/A | [{question, answer}] | Accordion FAQs |
| `testimonial` | N/A | [{name, text, rating, avatar}] | Patient reviews |
| `cta` | {cta_text, cta_url, cta_style} | N/A | Call-to-action banner |
| `video` | {thumbnail} | N/A | Embedded video |
| `features` | N/A | [{icon, title, description}] | Feature grid |
| `pricing` | N/A | [{name, price, features[]}] | Pricing cards |
| `team` | N/A | [{name, title, photo, bio}] | Team member grid |
| `contact` | ContactInfo | N/A | Contact details |
| `custom` | Any | Any | Custom block |

### Public Pages (`/api/v1/pages`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/pages/home` | None | Get home page content |
| GET | `/pages/doctors` | None | Get doctors listing page |
| GET | `/pages/hospitals` | None | Get hospitals page |
| GET | `/pages/treatments` | None | Get treatments page |
| GET | `/pages/destinations` | None | Get destinations page |
| GET | `/pages/services` | None | Get services page |
| GET | `/pages/blog` | None | Get blog listing |
| GET | `/pages/blog/{blog_id}` | None | Get blog post |
| GET | `/pages/faq` | None | Get FAQ page |
| GET | `/pages/team` | None | Get team page |

**All pages return:** Hero sliders, featured content, stats, testimonials, CTAs, etc.

**Blog Endpoints:**

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/pages/blog` | None | List blog posts (paginated) |
| GET | `/pages/blog/{post_id}` | None | Get blog post |
| GET | `/pages/blog/{post_id}/comments` | None | Get comments |
| POST | `/pages/blog/{post_id}/comments` | Patient | Submit comment |
| PUT | `/pages/blog/comments/{comment_id}` | Commenter | Update comment |
| DELETE | `/pages/blog/comments/{comment_id}` | Commenter/Admin | Delete comment |

**Blog Post Model:**
```python
{
  "id": "uuid",
  "title": "Top 10 Medical Procedures",
  "slug": "top-10-procedures",
  "author_id": "uuid",
  "author_name": "Dr. John Doe",
  "content": "HTML content",
  "excerpt": "Summary",
  "featured_image": "url",
  "publication_date": "2024-01-20",
  "status": "published",  # draft, published, archived
  "tags": ["treatment", "surgery"],
  "view_count": 1234,
  "comment_count": 25,
  "average_rating": 4.5,
  "reading_time_minutes": 8
}
```

---

## 🛠️ Admin Integration

### Admin Site Management (`/admin/site`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/admin/site/settings` | Admin | Get overall settings |
| PUT | `/admin/site/settings` | Admin | Update settings |
| GET | `/admin/site/hero-sliders` | Admin | List hero sliders |
| POST | `/admin/site/hero-sliders` | Admin | Create hero slider |
| PUT | `/admin/site/hero-sliders/{id}` | Admin | Update slider |
| DELETE | `/admin/site/hero-sliders/{id}` | Admin | Delete slider |

### Admin Dashboard (`/admin/dashboard`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/admin/dashboard/kpis` | Admin | Get KPI summary |
| GET | `/admin/dashboard/revenue` | Admin | Revenue metrics |
| GET | `/admin/dashboard/bookings` | Admin | Booking metrics |
| GET | `/admin/dashboard/consultations` | Admin | Consultation metrics |

### Admin - Hospital Management (`/admin/hospitals`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/admin/hospitals` | Admin | List hospitals |
| POST | `/admin/hospitals` | Admin | Create hospital |
| GET | `/admin/hospitals/{id}` | Admin | Get hospital |
| PUT | `/admin/hospitals/{id}` | Admin | Update hospital |
| DELETE | `/admin/hospitals/{id}` | Admin | Delete hospital |
| GET | `/admin/hospitals/{id}/departments` | Admin | Get departments |
| POST | `/admin/hospitals/{id}/departments` | Admin | Create department |

### Admin - Doctor Management (`/admin/doctors`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/admin/doctors` | Admin | List doctors |
| POST | `/admin/doctors` | Admin | Create doctor |
| PUT | `/admin/doctors/{id}` | Admin | Update doctor |
| DELETE | `/admin/doctors/{id}` | Admin | Delete doctor |
| GET | `/admin/doctors/{id}/consultations` | Admin | Get doctor consultations |
| POST | `/admin/doctors/{id}/verify` | SuperAdmin | Verify doctor |
| POST | `/admin/doctors/{id}/suspend` | SuperAdmin | Suspend doctor |

### Admin - Hotel Management (`/admin/hotels`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/admin/hotels` | Admin | List hotels |
| POST | `/admin/hotels` | Admin | Create hotel |
| PUT | `/admin/hotels/{id}` | Admin | Update hotel |
| DELETE | `/admin/hotels/{id}` | Admin | Delete hotel |
| GET | `/admin/hotels/{id}/rooms` | Admin | Manage rooms |
| POST | `/admin/hotels/{id}/rooms` | Admin | Add room |
| PUT | `/admin/hotels/{id}/rooms/{room_id}` | Admin | Update room |
| DELETE | `/admin/hotels/{id}/rooms/{room_id}` | Admin | Delete room |

### Admin - Restaurant Management (`/admin/restaurants`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/admin/restaurants` | Admin | List restaurants |
| POST | `/admin/restaurants` | Admin | Create restaurant |
| PUT | `/admin/restaurants/{id}` | Admin | Update restaurant |
| DELETE | `/admin/restaurants/{id}` | Admin | Delete restaurant |
| GET | `/admin/restaurants/{id}/menu` | Admin | Manage menu |
| POST | `/admin/restaurants/{id}/menu-items` | Admin | Add menu item |
| POST | `/admin/restaurants/{id}/dining-passes` | Admin | Create dining pass |
| GET | `/admin/restaurants/{id}/pass-purchases` | Admin | View pass purchases |
| POST | `/admin/restaurants/{id}/redeem-token` | Admin | Redeem pass token |

### Admin - Forex Management (`/admin/forex`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/admin/forex/currencies` | Admin | List currencies |
| POST | `/admin/forex/currencies` | Admin | Create currency |
| PUT | `/admin/forex/currencies/{id}` | Admin | Update exchange rate |
| DELETE | `/admin/forex/currencies/{id}` | Admin | Delete currency |
| GET | `/admin/forex/requests` | Admin | View forex requests |
| POST | `/admin/forex/requests/{id}/approve` | Admin | Approve request |
| POST | `/admin/forex/requests/{id}/reject` | Admin | Reject request |

### Admin - Medical Packages (`/admin/packages`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/admin/packages` | Admin | List packages |
| POST | `/admin/packages` | Admin | Create package |
| PUT | `/admin/packages/{id}` | Admin | Update package |
| DELETE | `/admin/packages/{id}` | Admin | Delete package |
| GET | `/admin/packages/{id}/bookings` | Admin | View bookings |

### Admin - RBAC (`/admin/rbac`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/admin/rbac/permissions` | Admin | List permissions |
| POST | `/admin/rbac/permissions` | SuperAdmin | Create permission |
| GET | `/admin/rbac/roles` | Admin | List roles |
| POST | `/admin/rbac/roles` | SuperAdmin | Create role |
| PUT | `/admin/rbac/roles/{id}` | SuperAdmin | Update role |
| POST | `/admin/rbac/roles/{id}/permissions` | SuperAdmin | Assign permissions |
| GET | `/admin/rbac/users/{user_id}/roles` | Admin | Get user roles |
| POST | `/admin/rbac/users/{user_id}/roles` | SuperAdmin | Assign roles |

**Built-in Roles:**
- `super_admin` — Full system access
- `admin` — Most administrative functions
- `doctor` — Doctor-specific access
- `patient` — Patient-specific access
- `hotel_manager` — Hotel management only
- `restaurant_manager` — Restaurant management only

---

## 📊 Additional Endpoints

### Currency Exchange (`/api/v1/forex`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/forex/currencies` | None | List active currencies |
| GET | `/forex/all-currencies` | None | List all currencies |
| GET | `/forex/calculate` | None | Calculate exchange |
| POST | `/forex/requests` | Patient | Request forex conversion |

**Exchange Calculation:**
```
GET /forex/calculate?from_currency_id=UUID&to_currency_id=UUID&amount=100

Response:
{
  "from_currency": "USD",
  "to_currency": "INR",
  "amount": 100,
  "rate_applied": 83.0,
  "calculated_amount": 8300.0
}
```

### Notifications (`/api/v1/notifications`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/notifications` | Bearer | List notifications (paginated) |
| GET | `/notifications/unread-count` | Bearer | Get unread count |
| GET | `/notifications/{id}` | Bearer | Get notification |
| PUT | `/notifications/{id}/read` | Bearer | Mark as read |
| PUT | `/notifications/read-all` | Bearer | Mark all as read |
| DELETE | `/notifications/{id}` | Bearer | Delete notification |

### Email System (`/api/v1/email`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/email/logs` | Admin | View email logs |
| GET | `/email/templates` | Admin | List email templates |
| POST | `/email/test` | Admin | Send test email |

### Events & Calendar (`/api/v1/events`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/events/me` | Bearer | Get user's calendar events |
| GET | `/events/me/calendar` | Bearer | Get calendar view |
| POST | `/events` | Bearer | Create event |
| PUT | `/events/{id}` | Owner/Admin | Update event |
| DELETE | `/events/{id}` | Owner/Admin | Delete event |

### Favorites / Wishlist (`/api/v1/favorites`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/favorites` | Bearer | Get favorites list |
| POST | `/favorites` | Bearer | Add to favorites |
| DELETE | `/favorites/{id}` | Bearer | Remove from favorites |
| GET | `/favorites/{entity_type}/{entity_id}` | Bearer | Check if favorited |

### Documents (`/api/v1/documents`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/documents` | Admin | List documents |
| POST | `/documents/upload` | Admin | Upload document |
| GET | `/documents/{id}` | Bearer | Download document |

### Patient Medical Records (`/api/v1/patients`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/patients/{patient_id}/medical-records` | Bearer | Get records |
| POST | `/patients/{patient_id}/medical-records` | Patient/Doctor | Upload record |
| GET | `/patients/{patient_id}/medical-records/{id}` | Bearer | Get record details |
| DELETE | `/patients/{patient_id}/medical-records/{id}` | Patient/Admin | Delete record |

### Patient Medical Reports (`/api/v1/patients`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/patients/{patient_id}/medical-reports` | Bearer | Get reports |
| POST | `/patients/{patient_id}/medical-reports` | Doctor | Create report |
| GET | `/patients/{patient_id}/medical-reports/{id}` | Bearer | Get report |
| PUT | `/patients/{patient_id}/medical-reports/{id}` | Doctor | Update report |
| DELETE | `/patients/{patient_id}/medical-reports/{id}` | Doctor/Admin | Delete report |

### Lead Generation (`/api/v1/leads`)

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| POST | `/leads/quote` | None | Submit quote request |
| POST | `/leads/contact` | None | Submit contact form |
| POST | `/leads/newsletter` | None | Newsletter subscription |
| POST | `/leads/callback` | None | Request callback |

### Image Management (`/api/v1/images`)

**Admin:**

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| POST | `/admin/images/upload` | Admin | Upload image |
| GET | `/admin/images` | Admin | List images |
| DELETE | `/admin/images/{id}` | Admin | Delete image |

**Public:**

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/images/{image_id}` | None | Get image |

---

## 📦 Data Models & Schemas

### Core Models Based on BaseModel

All models include:
- `id: UUID` (primary key)
- `created_at, updated_at` (timestamps)
- `created_by, updated_by` (audit fields)
- `is_deleted, deleted_at, deleted_by` (soft delete)

**23 Domain Models:**
1. `User` — Authentication, roles
2. `Patient` — Medical history, insurance
3. `Doctor` — Specialization, rating, availability
4. `Hospital` — Medical facility information
5. `Department` — Specialization departments
6. `Consultation` — Appointment/consultation record
7. `Booking` — Polymorphic (hotel/apt/restaurant/etc)
8. `Hotel` — Accommodation facility
9. `HotelRoom` — Individual rooms
10. `RoomAvailability` — Room availability calendar
11. `Apartment` — Short-term rental
12. `Restaurant` — Dining facility
13. `MenuCategory` — Restaurant menu categories
14. `MenuItem` — Individual menu items
15. `DiningPass` — Dining pass template
16. `DiningPassPurchase` — User's pass purchase
17. `Payment` — Payment transaction
18. `Review` — Polymorphic review (hotel/doctor/etc)
19. `CMSPage` — CMS page
20. `CMSBlock` — CMS block/component
21. `BlogPost` — Blog articles
22. `BlogComment` — Blog comments
23. `EmailLog` — Email audit trail

### Pydantic Schemas (Request/Response)

**Common Schemas:**
```python
PaginationParams(page: int = 1, page_size: int = 20)
PaginatedResponse[T](items: List[T], total: int, page: int, page_size: int, pages: int)
BasicResponse(id: UUID, name: str)
MessageResponse(message: str)
```

---

## 🎯 Key Design Patterns

### 1. Service-Based Architecture

```python
# In routers (thin layer)
@router.get("/doctors")
async def list_doctors(db: DatabaseSession, pagination: PaginationParams):
    service = DoctorService(db)
    doctors, total = await service.get_list(pagination, filters=...)
    return PaginatedResponse.create(doctors, total, ...)

# In services (business logic)
class DoctorService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_list(self, pagination, filters):
        # All DB queries, filtering, validation here
        query = select(Doctor).where(...)
        return doctors, total
```

### 2. Dependency Injection & RBAC

```python
from app.api.deps import CurrentUser, RequireAdmin, DatabaseSession

@router.get("/admin/data", dependencies=[RequireAdmin])
async def admin_endpoint(current_user: CurrentUser, db: DatabaseSession):
    # Current user injected and verified to have admin role
    return {"data": "..."}
```

### 3. Soft Delete Pattern

```python
# Always filter soft-deleted records
query = select(Doctor).where(Doctor.is_deleted == False)

# Soft delete instead of hard delete
await doctor.soft_delete(deleted_by=current_user.id)
await db.commit()

# Restore if needed
doctor.restore()
```

### 4. Pagination Pattern

```python
# All list endpoints
pagination = PaginationParams(page=1, page_size=20)
items, total = await service.get_list(pagination, filters=...)
return PaginatedResponse.create(items, total, page, page_size)
```

### 5. Polymorphic Entities

```python
# Single Booking table for multiple booking types
class Booking(Base):
    booking_type: str  # CONSULTATION, HOTEL, APARTMENT, RESTAURANT
    booking_metadata: dict  # JSONB for type-specific data
    guest_details: dict     # JSONB for guest info
```

### 6. Async-First Everything

```python
# All I/O is async with AsyncSession
async def get_doctors(db: AsyncSession):
    result = await db.execute(select(Doctor))
    return result.scalars().all()
```

### 7. Reference Number Generation

```python
# Pattern: PREFIX-YYYYMMDD-XXXXXX
generate_reference_id("CNS")  # "CNS-20240124-AB12CD"
generate_reference_id("BKG")  # "BKG-20240124-XY78ZW"
generate_reference_id("DP")   # "DP-20240124-ABC123"
```

### 8. Email Best-Effort Pattern

```python
# Book appointment (saves to DB first)
await db.commit()  # Explicit commit before side-effects

# Then email (if fails, booking still exists)
try:
    await send_email(...)
except Exception as e:
    logger.error("email_send_failed", error=str(e))
```

### 9. Google Meet Integration

```python
# Appointment.session_data (JSONB) contains:
{
  "meet_link": "https://meet.google.com/abc-def-ghi",
  "google_event_id": "event123",
  "platform": "google_meet"
}
```

### 10. JSON Columns (JSONB)

```python
# Hotel amenities
hotel.amenities  # ["wifi", "pool", "spa", "gym"]

# Restaurant policies
restaurant.policies  # {"cancellation": "24h", "deposit": "No"}

# Booking metadata
booking.booking_metadata  # {"special_requests": "..."}
```

---

## 🚀 Quick Start for New Endpoints

### Step 1: Create Router File
```python
# app/api/v1/my_domain.py
from fastapi import APIRouter
from app.api.deps import CurrentUser, DatabaseSession
from app.services.my_service import MyService

router = APIRouter()

@router.get("", response_model=PaginatedResponse[MyResponse])
async def list_items(db: DatabaseSession, page: int = Query(1)):
    service = MyService(db)
    items, total = await service.get_list(PaginationParams(page=page))
    return PaginatedResponse.create(items, total, page, 20)
```

### Step 2: Register in API Router
```python
# app/api/v1/api_router.py
from app.api.v1 import my_domain
api_router.include_router(my_domain.router, prefix="/my-domain", tags=["My Domain"])
```

### Step 3: Create Service
```python
# app/services/my_service.py
from sqlalchemy import select
from app.models.my_model import MyModel

class MyService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_list(self, pagination):
        result = await self.db.execute(
            select(MyModel).where(MyModel.is_deleted == False)
        )
        items = result.scalars().all()
        total = len(items)
        return items, total
```

### Step 4: Create Schema
```python
# app/schemas/my_schema.py
from pydantic import BaseModel

class MyResponse(BaseModel):
    id: UUID
    name: str
    
    model_config = ConfigDict(from_attributes=True)
```

---

## 📝 Logging Pattern

```python
from app.core.logging import get_logger

logger = get_logger(__name__)

logger.info("appointment_scheduled", ref=ref, doctor_id=doctor.id)
logger.error("payment_failed", booking_id=booking.id, error=str(exc))
```

All logs include:
- Event name (snake_case)
- Key-value context
- Timestamps (auto-added)
- User ID (auto-added from JWT)
- Correlation ID (for tracing)

---

## Summary Statistics

| Category | Count |
|----------|-------|
| **API Routes** | 150+ endpoints |
| **Domain Models** | 23 models |
| **Services** | 18 services |
| **Schemas** | 30+ schema files |
| **Public Routers** | 42 routers |
| **Admin Routers** | 10 specialized admin routers |
| **CMS Block Types** | 13 types |
| **User Roles** | 6 built-in roles |
| **Booking Types** | 5 types |

