# Flora Medical Tourism Platform - Architecture & Flows

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React/Vue)                     │
│              http://localhost:3000 (CORS enabled)                │
└────────────────────────────────┬────────────────────────────────┘
                                 │ HTTPS Bearer Token
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│                    FastAPI Application                            │
│                    (Port 8000)                                    │
├──────────────────────────────────────────────────────────────────┤
│                         API Gateway                               │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ Middleware: CORS, Auth, Error Handling, Logging, Rate Limit │ │
│  └─────────────────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────────┤
│ /api/v1/ – 42 Public Routers + 10 Admin Routers                  │
│  ├─ auth/                    ← JWT tokens                        │
│  ├─ users/, patients/, doctors/                                 │
│  ├─ hospitals/, departments/                                    │
│  ├─ consultations/, appointments/  ← Google Meet integration     │
│  ├─ hotels/, apartments/, stays/   ← Stripe payments            │
│  ├─ restaurants/ (dining passes)                                │
│  ├─ bookings/, payments/                                        │
│  ├─ chat/, ai/  ← WebSocket + AI                                │
│  ├─ cms/, pages/ (CMS blocks)                                   │
│  ├─ reviews/, favorites/, leads/                                │
│  ├─ forex/, notifications/, events/                             │
│  ├─ /admin/hospitals/, /admin/doctors/, /admin/hotels/  etc.   │
│  └─ /admin/rbac/, /admin/dashboard/                             │
├──────────────────────────────────────────────────────────────────┤
│                          Services Layer                           │
│  (Business logic, queries, validation, side effects)             │
│  ├─ UserService, PatientService, DoctorService                 │
│  ├─ AppointmentService (w/ Google Meet)                         │
│  ├─ BookingService, PaymentService, StripeService               │
│  ├─ HotelService, RestaurantService, ApartmentService           │
│  ├─ ReviewService, NotificationService, AIService               │
│  └─ ... 18 services total                                        │
├──────────────────────────────────────────────────────────────────┤
│                        SQLAlchemy ORM Layer                       │
│  (23 domain models with soft delete, audit fields)               │
│  ├─ User, Patient, Doctor, Hospital, Department                │
│  ├─ Consultation, Booking, Appointment                          │
│  ├─ Hotel, HotelRoom, Apartment, Restaurant                    │
│  ├─ Review, CMSPage, CMSBlock, BlogPost                         │
│  ├─ Payment, DiningPass, Notification                           │
│  └─ ... models with: id, created_at, updated_at, created_by,   │
│       updated_by, is_deleted, soft delete methods                │
├──────────────────────────────────────────────────────────────────┤
│                   Core Infrastructure                             │
│  ├─ Security: JWT token generation/validation                   │
│  ├─ Config: Environment-based configuration                     │
│  ├─ Dependencies: DI, RBAC role-based access control            │
│  ├─ Logging: Structured JSON logging with context               │
│  ├─ Email: SMTP async email sender                              │
│  ├─ File Upload: Static files served at /static/uploads/        │
│  └─ WebSocket: Real-time chat manager                           │
└────────────────────────────────┬────────────────────────────────┘
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│                     External Integrations                         │
├──────────────────────────────────────────────────────────────────┤
│ ├─ PostgreSQL Database (asyncpg driver)                         │
│ ├─ Redis (optional, for caching/sessions)                      │
│ ├─ Google Calendar/Meet (for video consultations)               │
│ ├─ Stripe (for payments)                                        │
│ ├─ SMTP Email Server (for notifications)                        │
│ └─ AWS S3 / Local Storage (for file uploads)                    │
└──────────────────────────────────────────────────────────────────┘
```

---

## Request/Response Lifecycle

```
Client Request (Bearer Token)
         │
         ▼
┌─────────────────────────────────┐
│   Router (HTTP Layer)           │
│ ├─ Parse request body/query     │
│ ├─ Inject dependencies          │
│ │  (current_user, db, etc.)     │
│ ├─ Validate with Pydantic       │
│ └─ Call service method          │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│   Service (Business Logic)      │
│ ├─ Validate inputs              │
│ ├─ Build SQL query              │
│ ├─ Execute with AsyncSession    │
│ ├─ Process results              │
│ ├─ Apply business rules         │
│ └─ Trigger side-effects         │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│   ORM Query Execution           │
│ ├─ select() + where() filters   │
│ ├─ Execute async                │
│ ├─ Fetch + map to models        │
│ └─ Return models                │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│   Database                      │
│   (PostgreSQL)                  │
└─────────────────────────────────┘
    Response (return to Service)
         │
         ▼
┌─────────────────────────────────┐
│   Serialize with Pydantic       │
│   (model_dump, from_attributes) │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│   Session Auto-Commit           │
│ ├─ Success: Auto-commit         │
│ ├─ Exception: Auto-rollback     │
└─────────────────────────────────┘
         │
         ▼
   JSON Response (200/201)
```

---

## Appointment Booking Flow - Detailed

```
                         ┌─────────────────────────────┐
                         │   Patient Mobile App        │
                         └────────────┬────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
           Step 1: Browse      Step 2: Check        Step 3: Book
           Doctors             Availability         Appointment
                │                      │                  │
                ▼                      ▼                  ▼
    GET /api/v1/doctors   GET /appointments/doctors/
                             {id}/available-slots
                             ?date=2024-01-24
                             &type=video
                │                      │
                └──────────┬───────────┘
                           ▼
        ┌──────────────────────────────────────┐
        │  AppointmentService.get_available   │
        │  _slots(doctor_id, date, type)       │
        │                                      │
        │  1. Get DoctorAvailability           │
        │  2. Generate all time slots          │
        │  3. Remove break times               │
        │  4. Query booked consultations       │
        │  5. Mark slots as available/booked   │
        └──────────────────────────────────────┘
                           │
                           ▼
               Response: Available Slots
               ┌─────────────────────────┐
               │ slots: [                │
               │   {time: "09:00", yes}  │
               │   {time: "09:30", no}   │
               │   {time: "10:00", yes}  │
               │ ]                       │
               └─────────────────────────┘
                           │
                    User selects slot
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │ POST /api/v1/appointments            │
        │ AppointmentCreate {                  │
        │   doctor_id,                         │
        │   consultation_type: "video",        │
        │   scheduled_date: "2024-01-24",      │
        │   scheduled_time: "10:00",           │
        │   reason, symptoms, timezone         │
        │ }                                    │
        └──────────────────────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │  AppointmentService.schedule_       │
        │  appointment()                       │
        │                                      │
        │  1. Validate doctor + consultation   │
        │  2. RE-CHECK slot availability ◄─┐  │
        │     (race condition guard)        │  │
        │  3. CREATE Consultation record    │  │
        │     (status=scheduled,            │  │
        │      reference=CNS-20240124-...)  │  │
        │  4. CREATE Booking record         │  │
        │     (reference=BKG-20240124-...) │  │
        │  5. IF video type:                │  │
        │     └─ create_meet_event()        │  │
        │        → store in Consultation    │  │
        │           .session_data JSONB     │  │
        │  6. CREATE Event records          │  │
        │     (for patient + doctor)        │  │
        │  7. await db.commit() ◄─────────┐ │  │
        │                               │ │  │
        └───────────────────────────────┼─┼──┘
                           │            │ │
                           ▼            │ │
        ┌──────────────────────────────┴─┘──────┐
        │  Side Effects (best-effort)          │
        │  └─ send_email(patient)              │
        │     • Meet link                      │
        │     • Doctor info                    │
        │     • Appointment details            │
        │  └─ send_email(doctor)               │
        │     • Patient name                   │
        │     • Reason for visit               │
        │     • Meet link                      │
        │  └─ Create email logs (DB)           │
        │  (If fails: booking still persists)  │
        └──────────────────────────────────────┘
                           │
                           ▼
         ┌─────────────────────────────────┐
         │  Response: AppointmentResponse   │
         │  {                              │
         │    id: "uuid",                  │
         │    reference: "CNS-...",        │
         │    status: "scheduled",         │
         │    doctor: {...},               │
         │    scheduled_at: "2024-01-24..." │
         │    meet_link: "https://meet..." │
         │    booking_reference: "BKG-..." │
         │  }                              │
         └─────────────────────────────────┘
                           │
                    Return to Patient App
                           │
    ┌──────────────────────┼──────────────────────┐
    ▼                      ▼                      ▼
 Redirect to        Calendar reminder       Notification
 Meet link          scheduled                sent to
                                            doctor's app
```

---

## Hotel Booking Flow - Simplified

```
Search for Hotels
        │
        ▼
GET /api/v1/hotels?city=Bangkok&min_price=50&max_price=300
        │
        ▼
Display Hotel List + Rooms
        │
        ▼
Select Room → Check Availability
        │
        ▼
GET /api/v1/bookings/rooms/{room_id}/availability
    ?check_in=2024-01-24&check_out=2024-01-28
        │
        ▼
Display Price Breakdown
  Base: $100/night × 4 nights = $400
  Tax: 10% = $40
  Total: $440
        │
        ▼
POST /api/v1/bookings/hotel
  {
    room_id: UUID,
    check_in_date: "2024-01-24",
    check_out_date: "2024-01-28",
    guest_name, guest_email, guest_phone,
    special_requests: "..."
  }
        │
        ▼
BookingService.create_hotel_booking()
  ├─ Validate room exists
  ├─ Check availability (no conflicts)
  ├─ Calculate price
  ├─ Create Booking record (status=PENDING)
  ├─ Create RoomReservation
  └─ Send confirmation email
        │
        ▼
Send Booking Reference
  Reference: BKG-20240124-XY78ZW
        │
        ▼
Payment Process
  POST /api/v1/payments/stripe/checkout
    → Redirect to Stripe
    → Complete payment
    → Webhook: Update booking status to CONFIRMED
        │
        ▼
Booking Confirmed!
```

---

## Data Model Relationships

```
┌─────────────┐
│    User     │  ← 6 role types: super_admin, admin, doctor, 
│             │    patient, hotel_manager, restaurant_manager
└────┬────────┘
     │
     ├─→ Patient (1-to-1)      ← Medical records, insurance
     │
     ├─→ Doctor (0-1)          ← Specialization, availability
     │    │
     │    ├─→ DoctorAvailability (1-to-many)
     │    └─→ Consultation (1-to-many)
     │
     ├─→ Notification (1-to-many)
     │
     ├─→ Review (1-to-many)           ← Polymorphic: hotel/doctor/etc
     │
     ├─→ Booking (1-to-many)           ← Polymorphic type
     │    │
     │    ├─→ Consultation            ← For doctor appointments
     │    ├─→ HotelReservation        ← For hotel room booking
     │    ├─→ ApartmentReservation    ← For apartment booking
     │    └─→ RestaurantReservation   ← For dining
     │
     └─→ Event (1-to-many)            ← Calendar events

┌─────────────┐
│  Hospital   │ ← Medical facility
│             │
└────┬────────┘
     │
     ├─→ Department (1-to-many)
     │    │
     │    └─→ Doctor (many-to-many)
     │
     ├─→ DoctorHospitalLink (1-to-many)
     │    └─→ Doctor
     │
     └─→ Review (1-to-many)

┌─────────────┐
│    Hotel    │ ← Accommodation
│             │
└────┬────────┘
     │
     ├─→ HotelRoom (1-to-many)
     │    │
     │    ├─→ RoomAvailability (1-to-many)
     │    ├─→ RoomPrice (1-to-many)
     │    └─→ Booking (many via booking.reference)
     │
     └─→ Review (1-to-many)

┌──────────────┐
│ Restaurant   │ ← Dining facility
│              │
└────┬─────────┘
     │
     ├─→ MenuCategory (1-to-many)
     │    └─→ MenuItem (1-to-many)
     │
     ├─→ DiningPass (1-to-many)        ← Pass template
     │    │
     │    └─→ DiningPassPurchase       ← User's purchased pass
     │         (many-to-many with User)
     │
     └─→ Review (1-to-many)

┌──────────────┐
│   CMSPage    │ ← Content management
│              │
└────┬─────────┘
     │
     └─→ CMSBlock (1-to-many)         ← Ordered components
          ├─ Hero, Text, Image, Gallery
          ├─ FAQ, Testimonial, CTA
          ├─ Video, Features, Pricing
          ├─ Team, Contact, Custom
          └─ Properties: content, config, items (JSONB)

┌──────────────┐
│   BlogPost   │ ← Articles
│              │
└────┬─────────┘
     │
     └─→ BlogComment (1-to-many)
```

---

## Authentication & Authorization Flow

```
Client → Login: POST /auth/login
              {email, password}
                    │
                    ▼
         ┌────────────────────────┐
         │ AuthService.login()    │
         │ ├─ Hash password      │
         │ ├─ Verify vs DB      │
         │ └─ Generate JWT      │
         └────────────────────────┘
                    │
                    ▼
         Response: {
           access_token: "eyJ0...",
           refresh_token: "eyJ1...",
           token_type: "bearer"
         }
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
    Store          Include in Requests
    in Local       Authorization: Bearer eyJ0...
    Storage
                    │
                    ▼
         ┌────────────────────────┐
         │ Request to Protected   │
         │ GET /api/v1/me        │
         │ Authorization: Bearer  │
         │ eyJ0...               │
         └────────────────────────┘
                    │
                    ▼
         ┌────────────────────────┐
         │ Middleware:            │
         │ extract_token()        │
         │ decode_token()         │
         │ (JWT signature)        │
         └────────────────────────┘
                    │
                    ▼
         ┌────────────────────────┐
         │ Dependency:            │
         │ CurrentUser ──→        │
         │ (inject user_id,      │
         │  role, permissions)   │
         └────────────────────────┘
                    │
         ┌──────────┴──────────┬──────────┐
         ▼                     ▼          ▼
    Check RBAC      Optional    Check
    (if needed)     User        specific
                               @RequireAdmin
                               @RequireDoctor
                               
    ✓ Pass         ✗ Fail
         │           │
         ▼           ▼
   Proceed to    403 Forbidden
   Handler       OR
                 401 Unauthorized

┌─────────────────────────────────────┐
│   Role Hierarchy                    │
├─────────────────────────────────────┤
│ super_admin > admin > role-specific │
│  (full access)  (most admin ops)    │
│                                     │
│ Specific roles:                     │
│  └─ doctor           (consultations)│
│  └─ patient          (bookings)     │
│  └─ hotel_manager    (hotels)       │
│  └─ restaurant_manager (restaurants)│
└─────────────────────────────────────┘

┌──────────────────────────────────────┐
│   Permission Structure               │
├──────────────────────────────────────┤
│ Permission = resource + action       │
│                                      │
│ Examples:                            │
│  "doctor:create"                     │
│  "doctor:update"                     │
│  "doctor:delete"                     │
│  "doctor:verify"                     │
│  "consultation:view"                 │
│  "consultation:schedule"             │
│  "appointment:cancel"                │
│  "booking:view"                      │
│  "payment:refund"                    │
└──────────────────────────────────────┘
```

---

## Database Schema Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Audit & Base Fields                      │
│  Inherited by ALL 23 models:                               │
│  • id: UUID (PK)                                           │
│  • created_at, updated_at (auto-timestamps)                │
│  • created_by, updated_by (FK→users.id)                    │
│  • is_deleted, deleted_at, deleted_by (soft delete)        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    Core User Tables                         │
├─────────────────────────────────────────────────────────────┤
│ users                                                       │
│  ├─ id (PK)                                               │
│  ├─ email (UNIQUE)                                        │
│  ├─ password_hash                                         │
│  ├─ full_name, phone, date_of_birth                      │
│  ├─ role (enum: super_admin, admin, doctor, ...)         │
│  ├─ is_active, is_email_verified                         │
│  ├─ avatar_url, last_login                               │
│  └─ [audit fields...]                                    │
│                                                           │
│ patients                                                  │
│  ├─ id (PK), user_id (FK→users, 1-1)                    │
│  ├─ blood_type, allergies, medical_history              │
│  ├─ emergency_contact, insurance_provider                │
│  ├─ insurance_policy_number, insurance_details (JSONB)  │
│  └─ [audit fields...]                                    │
│                                                           │
│ doctors                                                   │
│  ├─ id (PK), user_id (FK→users, 1-1)                    │
│  ├─ specialization, primary_specialty                    │
│  ├─ license_number, years_of_experience                 │
│  ├─ consultation_fee, rating, total_reviews             │
│  ├─ is_verified, is_suspended                           │
│  ├─ address, city, country                               │
│  └─ [audit fields...]                                    │
│                                                           │
│ doctor_availability                                       │
│  ├─ id (PK), doctor_id (FK→doctors)                      │
│  ├─ day_of_week (0-6: Mon-Sun)                          │
│  ├─ start_time, end_time, slot_duration_minutes         │
│  ├─ break_start_time, break_end_time                    │
│  ├─ max_appointments, is_available                      │
│  └─ [audit fields...]                                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              Medical Services Tables                        │
├─────────────────────────────────────────────────────────────┤
│ hospitals                                                   │
│  ├─ id, name, slug, email, phone, website               │
│  ├─ address_line1/2, city, state, country, postal_code  │
│  ├─ facilities, policies (JSONB)                         │
│  ├─ is_active, rating                                    │
│  └─ [audit fields...]                                    │
│                                                           │
│ departments                                               │
│  ├─ id, hospital_id (FK→hospitals)                       │
│  ├─ name, slug, description                             │
│  ├─ is_active                                           │
│  └─ [audit fields...]                                    │
│                                                           │
│ consultations                                             │
│  ├─ id, patient_id (FK→patients)                         │
│  ├─ doctor_id (FK→doctors)                               │
│  ├─ consultation_type (video/in_person/chat/phone)       │
│  ├─ status (pending/scheduled/waiting/in_progress/...)   │
│  ├─ reference (CNS-YYYYMMDD-XXXXXX)                      │
│  ├─ reason, symptoms, symptom_duration                   │
│  ├─ scheduled_date, scheduled_time                       │
│  ├─ session_data (JSONB: meet_link, google_event_id)    │
│  ├─ duration_minutes, timezone                           │
│  └─ [audit fields...]                                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│           Accommodation Tables (Hotel/Apt)                  │
├─────────────────────────────────────────────────────────────┤
│ hotels                                                      │
│  ├─ id, name, slug, city, country, address              │
│  ├─ email, phone, website, check_in_time, check_out_time│
│  ├─ amenities (JSONB array)                              │
│  ├─ facilities, policies, nearby_restaurants (JSONB)    │
│  ├─ is_active, is_featured, rating                       │
│  └─ [audit fields...]                                    │
│                                                           │
│ hotel_rooms                                               │
│  ├─ id, hotel_id (FK→hotels)                            │
│  ├─ room_number, room_type                               │
│  ├─ capacity, price_per_night                            │
│  ├─ amenities, highlights (JSONB array)                  │
│  ├─ images (JSONB array of URLs)                         │
│  ├─ is_available, is_active                              │
│  └─ [audit fields...]                                    │
│                                                           │
│ room_availability                                         │
│  ├─ id, room_id (FK→hotel_rooms)                         │
│  ├─ available_date, is_available                         │
│  ├─ price (if different from room.price)                │
│  └─ [audit fields...]                                    │
│                                                           │
│ apartments                                                │
│  ├─ id, name, slug, city, address                        │
│  ├─ bedrooms, bathrooms, capacity                         │
│  ├─ price_per_night, price_per_week, price_per_month    │
│  ├─ amenities (JSONB)                                    │
│  ├─ is_active, is_featured, rating                       │
│  └─ [audit fields...]                                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│             Booking Tables                                 │
├─────────────────────────────────────────────────────────────┤
│ bookings (Polymorphic)                                       │
│  ├─ id, patient_id (FK→patients)                          │
│  ├─ booking_type (enum: CONSULTATION/HOTEL/APARTMENT/...)│
│  ├─ status (PENDING/CONFIRMED/IN_PROGRESS/COMPLETED/...) │
│  ├─ reference (BKG-YYYYMMDD-XXXXXX)                      │
│  ├─ Linked to:                                           │
│  │  ├─ consultation_id (if CONSULTATION type)            │
│  │  ├─ hotel_reservation_id (if HOTEL type)              │
│  │  ├─ apartment_reservation_id (if APARTMENT type)      │
│  │  └─ restaurant_reservation_id (if RESTAURANT type)    │
│  ├─ total_price, currency, tax_amount                    │
│  ├─ confirmed_at, confirmed_by                           │
│  ├─ cancelled_at, cancellation_reason, cancelled_by      │
│  ├─ refund_amount (default 80%)                          │
│  ├─ booking_metadata (JSONB: type-specific data)         │
│  ├─ guest_details (JSONB: name, email, phone)            │
│  └─ [audit fields...]                                    │
│                                                           │
│ hotel_reservations                                        │
│  ├─ id, booking_id (FK→bookings)                         │
│  ├─ room_id (FK→hotel_rooms)                             │
│  ├─ check_in_date, check_out_date                        │
│  ├─ number_of_nights, price_per_night                    │
│  └─ [audit fields...]                                    │
│                                                           │
│ apartment_reservations                                    │
│  ├─ id, booking_id (FK→bookings)                         │
│  ├─ apartment_id (FK→apartments)                         │
│  ├─ check_in_date, check_out_date                        │
│  ├─ number_of_nights, rate_type                          │
│  └─ [audit fields...]                                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│           Restaurant/Dining Tables                         │
├─────────────────────────────────────────────────────────────┤
│ restaurants                                                │
│  ├─ id, name, slug, city, address, phone, email          │
│  ├─ cuisine_type, avg_cost_per_person                    │
│  ├─ is_active, is_featured, rating                       │
│  ├─ opening_hours, policies (JSONB)                      │
│  └─ [audit fields...]                                    │
│                                                           │
│ menu_categories                                           │
│  ├─ id, restaurant_id (FK→restaurants)                   │
│  ├─ name (e.g., "Appetizers", "Main Courses")           │
│  ├─ description, display_order                           │
│  └─ [audit fields...]                                    │
│                                                           │
│ menu_items                                                │
│  ├─ id, category_id (FK→menu_categories)                 │
│  ├─ name, description, price                             │
│  ├─ currency, is_vegan, is_gluten_free                   │
│  ├─ badge_tags (JSONB array: spicy, vegetarian, etc.)   │
│  ├─ display_order, is_active                             │
│  └─ [audit fields...]                                    │
│                                                           │
│ dining_passes                                             │
│  ├─ id, restaurant_id (FK→restaurants)                   │
│  ├─ name (e.g., "7-Day Breakfast Pass")                 │
│  ├─ description, price, currency                         │
│  ├─ tokens_total, validity_days                          │
│  └─ [audit fields...]                                    │
│                                                           │
│ dining_pass_purchases (User's passes)                     │
│  ├─ id, user_id (FK→users)                              │
│  ├─ dining_pass_id (FK→dining_passes)                    │
│  ├─ reference_code (DP-YYYYMMDD-XXXXXX)                 │
│  ├─ tokens_total, tokens_used                            │
│  ├─ purchased_at, expires_at, status                     │
│  ├─ amount_paid, currency                                │
│  ├─ availability_dates (JSONB: start/end dates)          │
│  └─ [audit fields...]                                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              Payment Tables                                │
├─────────────────────────────────────────────────────────────┤
│ payments                                                    │
│  ├─ id, user_id (FK→users)                               │
│  ├─ booking_id (FK→bookings)                             │
│  ├─ amount, currency, status                             │
│  ├─ gateway (stripe, paypal, etc.)                       │
│  ├─ transaction_id, receipt_url                          │
│  ├─ refund_amount, refund_date                           │
│  ├─ paid_at, failed_at, failure_reason                   │
│  └─ [audit fields...]                                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│           Review/Rating Tables                             │
├─────────────────────────────────────────────────────────────┤
│ reviews (Polymorphic)                                       │
│  ├─ id, user_id (FK→users)                               │
│  ├─ entity_type (hotel/doctor/restaurant/apartment/...)  │
│  ├─ entity_id (UUID of the entity being reviewed)        │
│  ├─ rating (1-5 stars)                                   │
│  ├─ title, body (review text)                            │
│  ├─ status (pending/approved/rejected)                   │
│  ├─ helpful_count, unhelpful_count                       │
│  ├─ verified_booking (bool: user actually booked it)    │
│  └─ [audit fields...]                                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              CMS Tables                                    │
├─────────────────────────────────────────────────────────────┤
│ cms_pages                                                  │
│  ├─ id, title, slug (UNIQUE)                             │
│  ├─ description, template                                │
│  ├─ status (draft/published/archived)                    │
│  ├─ parent_id (self-reference for hierarchy)             │
│  ├─ show_in_menu, menu_order                             │
│  ├─ requires_auth (bool)                                 │
│  ├─ meta_title, meta_description, meta_keywords         │
│  ├─ canonical_url, og_title, og_description, og_image   │
│  ├─ settings (JSONB)                                    │
│  └─ [audit fields...]                                    │
│                                                           │
│ cms_blocks (Components within pages)                     │
│  ├─ id, page_id (FK→cms_pages)                           │
│  ├─ block_type (hero/text/image/gallery/faq/...)         │
│  ├─ section (header/main/sidebar/footer)                 │
│  ├─ title, content (HTML for text blocks)                │
│  ├─ position (order within page)                         │
│  ├─ config (JSONB: block-type-specific config)          │
│  ├─ items (JSONB array: for galleries, FAQs, etc.)      │
│  ├─ is_visible, hide_on_mobile, hide_on_desktop         │
│  ├─ visible_from, visible_until (datetime)               │
│  └─ [audit fields...]                                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              System Tables                                 │
├─────────────────────────────────────────────────────────────┤
│ notifications                                              │
│  ├─ id, user_id (FK→users)                               │
│  ├─ type (appointment_reminder, payment_confirmed, ...)  │
│  ├─ title, message, action_url                           │
│  ├─ is_read, read_at                                     │
│  └─ [audit fields...]                                    │
│                                                           │
│ email_logs                                                │
│  ├─ id, user_id (FK→users)                               │
│  ├─ to_email, subject, template                          │
│  ├─ status (sent/failed)                                 │
│  ├─ error_message                                        │
│  ├─ sent_at, attempts                                    │
│  └─ [audit fields...]                                    │
│                                                           │
│ events                                                    │
│  ├─ id, user_id (FK→users)                               │
│  ├─ entity_type (consultation/booking/etc.)              │
│  ├─ entity_id, title, description                        │
│  ├─ start_time, end_time, location                       │
│  ├─ google_event_id (for synced events)                  │
│  ├─ meeting_url                                          │
│  └─ [audit fields...]                                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              RBAC Tables                                   │
├─────────────────────────────────────────────────────────────┤
│ roles                                                      │
│  ├─ id, name (super_admin, admin, doctor, ...)           │
│  ├─ description, is_system                               │
│  └─ [audit fields...]                                    │
│                                                           │
│ permissions                                               │
│  ├─ id, name, resource, action                           │
│  ├─ description                                          │
│  └─ [audit fields...]                                    │
│                                                           │
│ role_permissions (association)                           │
│  ├─ role_id (FK→roles)                                   │
│  ├─ permission_id (FK→permissions)                       │
│  └─ [composite key]                                      │
│                                                           │
│ user_roles (association)                                 │
│  ├─ user_id (FK→users)                                   │
│  ├─ role_id (FK→roles)                                   │
│  └─ [composite key]                                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Error Handling Strategy

```
Exception Occurs
      │
      ▼
┌─────────────────────────────┐
│ Router Error Handler        │
│ ├─ Catch ValueError        │
│ ├─ Catch SQLAlchemy        │
│ ├─ Catch Exception         │
│ ├─ Log with context        │
│ └─ Return JSON response    │
└─────────────────────────────┘
      │
      ├─ ValueError (Business Logic)
      │  └─→ 400 Bad Request
      │      {detail: "Description"}
      │
      ├─ HTTPException
      │  └─→ Custom status code
      │      (409 Conflict, 403 Forbidden, etc.)
      │
      ├─ Authentication Error
      │  └─→ 401 Unauthorized
      │
      ├─ Authorization Error
      │  └─→ 403 Forbidden
      │
      ├─ Not Found
      │  └─→ 404 Not Found
      │
      ├─ Database Error
      │  └─→ 500 Internal Server Error
      │      (logged but not exposed to client)
      │
      └─ Unexpected Error
         └─→ 500 Internal Server Error
             (logged, generic message)
```

---

## Performance Considerations

```
Optimization Strategies
├─ Pagination (all list endpoints)
│  └─ Default: 20 items, max: 100 per request
│
├─ Query optimization
│  ├─ Filtering at DB layer (not application)
│  ├─ Indexes on frequently searched fields
│  └─ Eager loading relationships (selectinload)
│
├─ Caching (optional Redis)
│  └─ Doctor availability, public data
│
├─ Async-first
│  ├─ All I/O is async (no blocking)
│  ├─ Email sent via asyncio.to_thread
│  └─ Multiple requests handled concurrently
│
├─ SQL indexes
│  ├─ user.email (UNIQUE)
│  ├─ consultation.status, consultation.patient_id
│  ├─ booking.status, booking.patient_id
│  ├─ hotel.city, hotel.is_active
│  └─ Soft delete: is_deleted (indexed)
│
├─ File uploads
│  └─ Max 10 MB per file
│      Served at /static/uploads/
│
└─ Rate limiting (optional)
   └─ 100 requests per 60 seconds per IP
```

