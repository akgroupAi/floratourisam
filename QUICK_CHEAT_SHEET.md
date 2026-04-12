# Flora Medical Platform - Quick Cheat Sheet

## 🚀 Common Commands

```bash
# Start dev server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest tests/ -v
pytest tests/test_auth.py::test_login_invalid_credentials -v

# Create migration
alembic revision --autogenerate -m "add field description"

# Apply migrations
alembic upgrade head

# Lint & format
black app/ tests/
isort app/ tests/
flake8 app/ tests/
mypy app/
```

---

## 📍 API Base URL

**Development:** `http://localhost:8000/api/v1`  
**Production:** `https://api.flora.local/api/v1`

---

## 🔐 Authentication Header

```
Authorization: Bearer <jwt_token_from_login>
```

**Get token:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password123"}'

# Response:
# {
#   "access_token": "eyJ0...",
#   "refresh_token": "eyJ1...",
#   "token_type": "bearer"
# }
```

---

## 📊 Common Query Parameters

```python
# Pagination
?page=1&page_size=20
?page=2&page_size=50

# Filtering
?city=Bangkok
?specialization=Cardiology
?min_rating=4.0
?is_active=true

# Search
?search=keyword

# Sorting
?sort_by=created_at
?sort_by=price_low_to_high
?sort_by=highest_rated

# Date range
?date=2024-01-24
?check_in=2024-01-24&check_out=2024-01-28
?start_date=2024-01-01&end_date=2024-01-31
```

---

## 📋 Response Format

### Success (200, 201)
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Example",
  "created_at": "2024-01-20T10:00:00Z"
}
```

### List with Pagination (200)
```json
{
  "items": [
    {"id": "...", "name": "..."},
    {"id": "...", "name": "..."}
  ],
  "total": 100,
  "page": 1,
  "page_size": 20,
  "pages": 5
}
```

### Error (4xx, 5xx)
```json
{
  "detail": "Descriptive error message"
}
```

### Message Response
```json
{
  "message": "Operation completed successfully"
}
```

---

## 🎯 Endpoint Categories Quick Reference

| Category | Base URL | Public | Auth | Admin |
|----------|----------|--------|------|-------|
| Authentication | `/auth` | ✓ | ✗ | ✗ |
| Users | `/users` | ✗ | ✓ | ✓ |
| Patients | `/patients` | ✗ | ✓ | ✓ |
| Doctors | `/doctors` | ✓ | ✓ | ✓ |
| Consultations | `/consultations` | ✗ | ✓ | ✓ |
| Appointments | `/appointments` | ✓ | ✓ | ✓ |
| Hotels | `/hotels` | ✓ | ✓ | ✓ |
| Bookings | `/bookings` | ✗ | ✓ | ✓ |
| Payments | `/payments` | ✗ | ✓ | ✓ |
| Restaurants | `/restaurants` | ✓ | ✓ | ✓ |
| AI | `/ai` | ✗ | ✓ | ✗ |
| Chat | `/chat` | ✗ | ✓ | ✗ |
| CMS | `/cms` | ✓ | ✗ | ✓ |
| Admin | `/admin/*` | ✗ | ✓ | ✓ |

---

## 🔑 Common Role Guards

```python
# Public - no auth required
@router.get("/doctors")

# Require authentication
@router.get("/me", dependencies=[RequireAuth])

# Require patient
@router.post("/bookings", dependencies=[RequirePatient])

# Require doctor
@router.post("/availability", dependencies=[RequireDoctor])

# Require admin
@router.delete("/{id}", dependencies=[RequireAdmin])

# Require super admin
@router.post("/permissions", dependencies=[RequireSuperAdmin])
```

Available guards:
- `RequireAuth` (any authenticated user)
- `RequirePatient` (patient role)
- `RequireDoctor` (doctor role)
- `RequireAdmin` (admin or super_admin)
- `RequireSuperAdmin` (super_admin only)

---

## 🏗️ File Structure for New Domain

```
Create these files:

app/models/my_domain.py
├─ from app.models.base import BaseModel
├─ class MyModel(BaseModel):
│  └─ __tablename__ = "my_table"

app/schemas/my_domain.py
├─ class MyCreate(BaseModel):
├─ class MyUpdate(BaseModel):
└─ class MyResponse(BaseSchema):

app/services/my_domain_service.py
├─ class MyDomainService:
│  ├─ async def get_by_id()
│  ├─ async def get_list()
│  ├─ async def create()
│  └─ async def update()

app/api/v1/my_domain.py
├─ router = APIRouter()
├─ @router.get("")
├─ @router.post("")
├─ @router.get("/{id}")
└─ @router.put("/{id}")

Update:
  app/api/v1/api_router.py
```

---

## 🔍 Common Decorators & Dependencies

```python
from app.api.deps import (
    CurrentUser,           # Current authenticated user
    DatabaseSession,       # DB connection
    RequireAdmin,          # Admin role guard
    RequirePatient,        # Patient role guard
    RequireDoctor,         # Doctor role guard
)

@router.get("", response_model=PaginatedResponse[MyResponse])
async def list_items(
    db: DatabaseSession,                    # Injected
    page: int = Query(1, ge=1),            # Query param
    current_user: CurrentUser = None        # Optional user
):
    pass

@router.post("", status_code=201, dependencies=[RequireAdmin])
async def create_item(db: DatabaseSession):
    pass
```

---

## 📝 Common Schema Components

```python
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.common import BaseSchema, PaginatedResponse
from datetime import datetime
from uuid import UUID

class MyCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    is_active: bool = True

class MyResponse(BaseSchema):
    id: UUID
    name: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class MyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
```

---

## 💾 Common Service Patterns

```python
class MyService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_by_id(self, id: UUID) -> MyModel | None:
        result = await self.db.execute(
            select(MyModel).where(
                MyModel.id == id,
                MyModel.is_deleted == False
            )
        )
        return result.scalar_one_or_none()
    
    async def get_list(self, pagination: PaginationParams) -> tuple:
        query = select(MyModel).where(MyModel.is_deleted == False)
        
        # Count
        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0
        
        # Paginate
        query = query.order_by(MyModel.created_at.desc())
        query = query.offset(
            (pagination.page - 1) * pagination.page_size
        ).limit(pagination.page_size)
        
        result = await self.db.execute(query)
        items = result.scalars().all()
        
        return items, total
    
    async def create(self, data: MyCreate, created_by: UUID):
        item = MyModel(**data.model_dump(), created_by=created_by)
        self.db.add(item)
        await self.db.flush()
        return item
    
    async def update(self, item: MyModel, data: MyUpdate, updated_by: UUID):
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        item.updated_by = updated_by
        await self.db.flush()
        return item
    
    async def delete(self, item: MyModel, deleted_by: UUID):
        item.soft_delete(deleted_by=deleted_by)
        await self.db.flush()
```

---

## 🔄 Common Enums

```python
from enum import Enum

class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    DOCTOR = "doctor"
    PATIENT = "patient"
    HOTEL_MANAGER = "hotel_manager"
    RESTAURANT_MANAGER = "restaurant_manager"

class ConsultationType(str, Enum):
    VIDEO = "video"
    IN_PERSON = "in_person"
    CHAT = "chat"
    PHONE = "phone"

class BookingStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"

class BookingType(str, Enum):
    CONSULTATION = "consultation"
    HOTEL = "hotel"
    APARTMENT = "apartment"
    RESTAURANT = "restaurant"
    PACKAGE = "package"

class CMSPageStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"
```

---

## 📧 Email Patterns

```python
from app.utils.email_sender import send_email

# Send appointment confirmation
await send_email(
    to=patient.email,
    subject="Appointment Confirmation",
    template="appointment_confirmation",
    context={
        "patient_name": patient.name,
        "doctor_name": doctor.name,
        "appointment_date": consultation.scheduled_at,
        "meet_link": consultation.session_data.get("meet_link"),
    }
)

# Send booking confirmation
await send_email(
    to=patient.email,
    subject=f"Booking Confirmed - Reference {booking.reference}",
    template="booking_confirmation",
    context={
        "guest_name": guest_name,
        "hotel_name": hotel.name,
        "check_in_date": booking.check_in_date,
        "check_out_date": booking.check_out_date,
        "reference": booking.reference,
    }
)

# Send password reset
await send_email(
    to=user.email,
    subject="Password Reset Request",
    template="password_reset",
    context={
        "full_name": user.full_name,
        "reset_token": token,
        "reset_url": f"{settings.FRONTEND_URL}/reset-password?token={token}",
    }
)
```

---

## 🔐 Password & Token Patterns

```python
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)

# Hash password
hashed = await get_password_hash("password123")

# Verify password
is_valid = await verify_password("password123", hashed)

# Create JWT tokens
access_token = await create_access_token(
    data={"sub": str(user.id)},
    expires_delta=timedelta(minutes=30)
)

refresh_token = await create_refresh_token(
    data={"sub": str(user.id)},
    expires_delta=timedelta(days=7)
)

# Decode token
payload = await decode_token(token)
# Returns {"sub": "user_id"} or None if invalid
```

---

## 📚 Reference Number Patterns

```python
from app.utils.helpers import generate_reference_id

# Consultation reference
consultation_ref = generate_reference_id("CNS")
# → "CNS-20240124-AB12CD"

# Booking reference
booking_ref = generate_reference_id("BKG")
# → "BKG-20240124-XY78ZW"

# Dining pass reference
pass_ref = generate_reference_id("DP")
# → "DP-20240124-ABC123"

# Forex request reference
forex_ref = generate_reference_id("FX")
# → "FX-20240124-DEF456"
```

---

## 🧪 Testing Patterns

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_list_items(client: AsyncClient):
    response = await client.get("/api/v1/my-domain")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data

@pytest.mark.asyncio
async def test_create_item(client: AsyncClient):
    response = await client.post(
        "/api/v1/my-domain",
        json={"name": "Test Item"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Item"

@pytest.mark.asyncio
async def test_not_found(client: AsyncClient):
    response = await client.get(
        "/api/v1/my-domain/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_unauthorized(client: AsyncClient):
    # Without auth header
    response = await client.get("/api/v1/protected-endpoint")
    assert response.status_code == 401
```

---

## 🔗 Useful Links in Codebase

| What | Where |
|------|-------|
| All dependencies | `app/api/deps.py` |
| All enums | `app/utils/enums.py` |
| Config settings | `app/core/config.py` |
| Security (JWT) | `app/core/security.py` |
| Logging | `app/core/logging.py` |
| Email templates | `app/utils/email_sender.py` |
| Google Meet | `app/utils/google_meet.py` |
| Database setup | `app/db/session.py` |
| Base model | `app/models/base.py` |
| App entry | `app/main.py` |

---

## 🐛 Debugging Tips

```bash
# Enable SQL logging
DEBUG=True
DATABASE_ECHO=True

# View logs
tail -f logs/app.log

# Test endpoint with curl
curl -X GET \
  'http://localhost:8000/api/v1/doctors?page=1' \
  -H 'Authorization: Bearer <token>'

# Test with invalid token
curl -X GET \
  'http://localhost:8000/api/v1/me' \
  -H 'Authorization: Bearer invalid'

# Check database directly
psql $DATABASE_URL
SELECT * FROM users LIMIT 5;

# Run single test with output
pytest tests/test_auth.py::test_login -vvs

# Print variable in service
import json
print(json.dumps(obj, default=str, indent=2))
```

---

## ⚠️ Common Mistakes to Avoid

```python
# ❌ Don't use blocking operations
await db.execute(query)  # Wait for result

# ❌ Don't forget to filter soft deletetes
# Wrong:
result = await db.execute(select(MyModel))

# ✓ Correct:
result = await db.execute(
    select(MyModel).where(MyModel.is_deleted == False)
)

# ❌ Don't hard delete
await db.delete(item)  # Will break referential integrity

# ✓ Correct:
item.soft_delete(deleted_by=user_id)

# ❌ Don't commit manually in services
await db.commit()  # Let session dependency handle it

# ✓ Correct:
self.db.add(item)
await self.db.flush()  # Just flush, not commit

# ❌ Don't expose sensitive errors
raise HTTPException(detail=str(exception))  # Exposes internals

# ✓ Correct:
logger.error("operation_failed", error=str(exc))
raise HTTPException(detail="Operation failed")

# ❌ Don't forget .value for enum comparisons
if user.role == UserRole.ADMIN  # Compares Enum object

# ✓ Correct:
if user.role == UserRole.ADMIN.value  # Compares string
```

---

## 📞 Getting Help

| Issue | Solution |
|-------|----------|
| 404 error | Check endpoint path in router registration |
| 401 Unauthorized | Verify JWT token is valid and not expired |
| 403 Forbidden | Check user role/permissions in dependencies |
| 500 Internal Error | Check logs for exact error message |
| Slow queries | Add `.filter(is_deleted == False)`, check indexes |
| CORS error | Verify frontend URL in `CORS_ORIGINS` env var |
| Database connection error | Check `DATABASE_URL` env var |
| Email not sending | Check `SMTP_*` env vars, see email logs |

---

## 📚 Documentation Files

- `ENDPOINTS_ANALYSIS.md` — Complete endpoint reference
- `ENDPOINT_CREATION_GUIDE.md` — How to create new endpoints
- `ARCHITECTURE_FLOWS.md` — System architecture & data flows
- `API_DOCUMENTATION.md` — Detailed API docs
- `README.md` — Project overview

