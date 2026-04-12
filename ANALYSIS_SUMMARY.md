# 📊 Flora Medical Tourism Platform - Analysis Summary

**Date:** April 12, 2026  
**Status:** ✅ Complete Endpoint Analysis Done

---

## 📖 What I've Created For You

I've analyzed the **entire Flora Medical Tourism Platform** and created **4 comprehensive documentation files** to help you understand and extend it:

### 1. **ENDPOINTS_ANALYSIS.md** ← Start here
   - 📋 **150+ API endpoints** documented
   - 🏗️ **Architecture overview** (5-layer structure)
   - 🔐 **Auth & RBAC** system explained
   - 📊 **All endpoints by category** (42 public + admin routers)
   - 💾 **23 domain models** with relationships
   - 🎯 **Key design patterns** explained
   - ⚙️ **Environment configuration** reference

   **Best for:** Understanding the complete system architecture

### 2. **ENDPOINT_CREATION_GUIDE.md** ← For creating new endpoints
   - 🚀 **Step-by-step** endpoint creation (5 steps)
   - 📝 **Complete code examples** for each layer
   - 🎯 **Router pattern** (HTTP layer)
   - 💼 **Service pattern** (business logic)
   - 📋 **Schema pattern** (Pydantic v2)
   - 🗄️ **Model pattern** (SQLAlchemy ORM)
   - 🧪 **Testing patterns**
   - ⚠️ **Common mistakes to avoid**

   **Best for:** Creating new endpoints following project conventions

### 3. **ARCHITECTURE_FLOWS.md** ← For understanding system flows
   - 🏗️ **System architecture diagram**
   - 🔄 **Request/Response lifecycle**
   - 📋 **Appointment booking flow** (detailed step-by-step)
   - 🏨 **Hotel booking flow**
   - 🗂️ **Data model relationships** (visual)
   - 🔐 **Authentication flow**
   - 💾 **Database schema** (complete)
   - ⚡ **Performance considerations**

   **Best for:** Understanding how data flows and systems interact

### 4. **QUICK_CHEAT_SHEET.md** ← For quick reference
   - 🚀 **Common commands** (dev, testing, migrations)
   - 📍 **API base URLs**
   - 🔐 **Auth header format**
   - 📊 **Common query parameters**
   - 📋 **Response format examples**
   - 🎯 **All endpoints by category** (reference table)
   - 🔑 **Role guards** (what's available)
   - 💾 **File structure** for new domains
   - 📝 **Common patterns** (schemas, services, enums)
   - 🐛 **Debugging tips**
   - ⚠️ **Common mistakes**

   **Best for:** Quick lookup while coding

---

## 🎯 System Overview

### What This Platform Does

```
Medical Tourism Platform
├─ Patient Management
│  ├─ Profile + medical history
│  ├─ Insurance tracking
│  └─ Medical records/reports
│
├─ Doctor Management
│  ├─ Profile + specialization
│  ├─ Availability scheduling
│  └─ Consultation booking
│
├─ Consultations & Appointments
│  ├─ Video consultations (Google Meet)
│  ├─ In-person visits
│  ├─ Chat/Phone consultations
│  └─ Appointment scheduling
│
├─ Hospital & Department Management
│  ├─ Hospital profiles
│  ├─ Department listings
│  └─ Doctor assignments
│
├─ Accommodation Booking
│  ├─ Hotels with room management
│  ├─ Apartments/Stays
│  ├─ Availability checking
│  └─ Pricing (nightly/weekly/monthly)
│
├─ Dining Management
│  ├─ Restaurant listings
│  ├─ Menu management
│  ├─ Dining pass system
│  └─ Table reservations
│
├─ Booking & Payments
│  ├─ Polymorphic bookings (hotel/apt/restaurant)
│  ├─ Stripe payment integration
│  ├─ Refund management
│  └─ Booking references (CNS-, BKG-, DP-)
│
├─ Reviews & Ratings
│  ├─ Polymorphic review system
│  ├─ Rating summaries
│  └─ Verified booking checks
│
├─ CMS & Content
│  ├─ Page management
│  ├─ 13 block types (Hero, FAQ, Pricing, etc.)
│  ├─ Blog with comments
│  └─ Navigation menus
│
├─ Communication
│  ├─ WebSocket chat
│  ├─ AI assistant chatbot
│  ├─ Email notifications
│  └─ Real-time notifications
│
├─ Financial
│  ├─ Forex currency exchange
│  ├─ Multi-currency support
│  └─ Conversion calculations
│
└─ Administration
   ├─ Role-based access control (RBAC)
   ├─ Permission management
   ├─ Dashboard KPIs
   ├─ Content moderation
   └─ System settings
```

### Technology Stack

```
Backend:
├─ FastAPI (Python web framework)
├─ SQLAlchemy 2.0 (async ORM)
├─ PostgreSQL (database)
├─ asyncpg (async PostgreSQL driver)
├─ Pydantic v2 (validation)
└─ asyncio (async runtime)

Integration:
├─ Google Calendar/Meet (video consultations)
├─ Stripe (payments)
├─ SMTP (email notifications)
└─ WebSocket (real-time chat)

DevOps:
├─ Alembic (database migrations)
├─ pytest (testing)
├─ Docker (containerization)
└─ Redis (optional caching)

Frontend: React/Vue (separate repository)
```

---

## 🏆 Key Statistics

| Metric | Count |
|--------|-------|
| **API Endpoints** | 150+ |
| **Public Routers** | 42 |
| **Admin Routers** | 10 |
| **Domain Models** | 23 |
| **Services** | 18 |
| **Pydantic Schemas** | 30+ |
| **User Roles** | 6 |
| **CMS Block Types** | 13 |
| **Booking Types** | 5 |
| **Authentication Methods** | JWT Bearer Token |

---

## 🚀 To Get Started

### Step 1: Read the Overview
```
Read: ENDPOINTS_ANALYSIS.md
Time: 10-15 minutes
Goal: Understand overall architecture
```

### Step 2: Understand the Flows
```
Read: ARCHITECTURE_FLOWS.md
Time: 15-20 minutes
Goal: See how appointment & booking flows work
```

### Step 3: Learn How to Create Endpoints
```
Read: ENDPOINT_CREATION_GUIDE.md
Time: 20-30 minutes
Goal: Understand the pattern for new endpoints
```

### Step 4: Keep as Reference
```
Bookmark: QUICK_CHEAT_SHEET.md
Time: On-demand lookup
Goal: Quick reference while coding
```

---

## 💡 Key Patterns to Remember

### 1. **4-Layer Architecture**

```python
# Layer 1: Router (HTTP)
@router.get("/doctors")
async def list_doctors(db: DatabaseSession):
    service = DoctorService(db)
    return await service.get_list()

# Layer 2: Service (Business Logic)
class DoctorService:
    async def get_list(self):
        result = await self.db.execute(select(Doctor))
        return result.scalars().all()

# Layer 3: ORM (Models)
class Doctor(BaseModel):
    __tablename__ = "doctors"
    specialization: str

# Layer 4: Database
SELECT * FROM doctors;
```

### 2. **Pagination Pattern**

```python
# Every list endpoint
@router.get("", response_model=PaginatedResponse[MyResponse])
async def list_items(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    service = MyService(db)
    items, total = await service.get_list(
        PaginationParams(page=page, page_size=page_size)
    )
    return PaginatedResponse.create(items, total, page, page_size)
```

### 3. **Soft Delete Pattern**

```python
# Always filter soft-deleted
query = select(Doctor).where(Doctor.is_deleted == False)

# Delete via soft-delete
doctor.soft_delete(deleted_by=user_id)
await db.commit()
```

### 4. **Authentication Pattern**

```python
# Current user + role guards
@router.get("/admin-data", dependencies=[RequireAdmin])
async def admin_endpoint(current_user: CurrentUser, db: DatabaseSession):
    # current_user injected with verified role
    return {"data": "..."}
```

### 5. **Polymorphic Entities**

```python
# Single table with type indicator
class Booking(Base):
    booking_type: str  # CONSULTATION, HOTEL, APARTMENT
    booking_metadata: dict  # Type-specific data (JSONB)
```

---

## 🔄 Workflow for Creating New Endpoint

1. **Create Model** (`app/models/my_domain.py`)
   - Extend `BaseModel` (gets audit fields)
   - Define SQLAlchemy columns
   - Add relationships

2. **Create Schemas** (`app/schemas/my_domain.py`)
   - `MyCreate` — For POST/PUT requests
   - `MyUpdate` — For PATCH/PUT partial updates
   - `MyResponse` — For responses (with all fields)

3. **Create Service** (`app/services/my_domain_service.py`)
   - Handle all database queries
   - Validate business logic
   - Return raw models (not dicts)

4. **Create Router** (`app/api/v1/my_domain.py`)
   - Call services
   - Convert models to schemas
   - Handle HTTP status codes

5. **Register Router** (`app/api/v1/api_router.py`)
   - `api_router.include_router(my_domain.router, ...)`

6. **Create Migration**
   - `alembic revision --autogenerate -m "add my_table"`
   - `alembic upgrade head`

7. **Test It**
   - `pytest tests/test_my_domain.py`

---

## 🧪 Testing Basics

```python
@pytest.mark.asyncio
async def test_list_items(client: AsyncClient):
    response = await client.get("/api/v1/my-domain")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert data["total"] >= 0

# Tests use SQLite test.db (no PostgreSQL needed)
# Session created fresh for each test
# Automatically rolled back after each test
```

---

## 🔍 Where to Find Things

| What | Where |
|------|-------|
| All endpoints | `app/api/v1/` (routers) |
| Business logic | `app/services/` |
| Data validation | `app/schemas/` |
| Database models | `app/models/` |
| Configuration | `app/core/config.py` |
| Security/JWT | `app/core/security.py` |
| RBAC/Auth | `app/core/dependencies.py` |
| Email templates | `app/utils/email_sender.py` |
| Google Meet | `app/utils/google_meet.py` |
| Database setup | `app/db/session.py` |
| Migrations | `alembic/versions/` |
| Tests | `tests/` |

---

## 🐛 Common Debug Scenarios

### Query not returning results
→ Check: `is_deleted == False` filter

### 401 Unauthorized
→ Check: `Authorization: Bearer <token>` header

### 403 Forbidden  
→ Check: Role requirements in `dependencies=[RequireAdmin]`

### 404 Not Found
→ Check: Endpoint path in router registration

### 500 Internal Error
→ Check: Application logs for exact error

### Email not sending
→ Check: SMTP env vars, see `email_logs` table

### Slow queries
→ Check: Missing database indexes, add filtering

---

## 📞 Need Help?

### Check These First:
1. Look in `QUICK_CHEAT_SHEET.md` for common patterns
2. Search `ENDPOINTS_ANALYSIS.md` for similar endpoint
3. Check test files in `tests/` for examples
4. View similar service/router for pattern reference

### Common Issues:
- Page not found → Check URL in browser console & router registration
- Can't authenticate → Verify JWT token with `/auth/login`
- Permission denied → Check `dependencies=[RequireAdmin]` requirement
- Database error → Check migration ran with `alembic upgrade head`

---

## 📚 Reading Guide

**5 minutes:**
- Read this file (summary)

**30 minutes (essential):**
- Read: Architecture section of ENDPOINTS_ANALYSIS.md
- Read: Key endpoints in ENDPOINTS_ANALYSIS.md

**1 hour (important):**
- Read: Selected flows in ARCHITECTURE_FLOWS.md
- Read: Pattern sections in ENDPOINT_CREATION_GUIDE.md

**As needed:**
- Use QUICK_CHEAT_SHEET.md for lookups
- Reference ENDPOINTS_ANALYSIS.md for specific endpoints
- Reference ARCHITECTURE_FLOWS.md for data relationships

---

## ✅ Checklist Before Creating Endpoint

- [ ] Read ENDPOINT_CREATION_GUIDE.md completely
- [ ] Create model with `class MyModel(BaseModel):`
- [ ] Create request schema `class MyCreate(BaseModel):`
- [ ] Create response schema `class MyResponse(BaseSchema):`
- [ ] Create service with `get_by_id()`, `get_list()`, `create()`, `update()`, `delete()`
- [ ] Create router with decoration `@router.get/post/put/delete`
- [ ] Register router in `api_router.py`
- [ ] Create migration with Alembic
- [ ] Run migration: `alembic upgrade head`
- [ ] Write tests in `tests/`
- [ ] Test with Postman/curl
- [ ] Test with pytest: `pytest tests/test_my_domain.py`
- [ ] Check endpoints in Swagger: `http://localhost:8000/docs`

---

## 🎉 You're Ready!

You now have:
- ✅ Complete understanding of system architecture
- ✅ 150+ endpoints documented
- ✅ Step-by-step guide for creating new endpoints
- ✅ Design patterns explained
- ✅ Quick reference for common tasks
- ✅ Database schema explained
- ✅ Authentication & authorization patterns

**Next Step:** Pick a domain you want to extend and follow the ENDPOINT_CREATION_GUIDE.md

Good luck! 🚀

