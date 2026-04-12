# Quick Reference: Creating New Endpoints

## Endpoint Creation Checklist

### 1. Router Pattern (in `app/api/v1/my_domain.py`)

```python
"""Domain functionality endpoints."""

from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.schemas.common import PaginatedResponse, PaginationParams, MessageResponse
from app.schemas.my_schema import MyCreate, MyResponse, MyUpdate
from app.services.my_service import MyService

router = APIRouter()

# ============== PUBLIC ENDPOINTS ==============

@router.get("", response_model=PaginatedResponse[MyResponse])
async def list_items(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
):
    """List items with pagination and search."""
    service = MyService(db)
    items, total = await service.get_list(
        PaginationParams(page=page, page_size=page_size),
        search=search
    )
    return PaginatedResponse.create(items, total, page, page_size)


@router.post("", response_model=MyResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    data: MyCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Create a new item."""
    service = MyService(db)
    try:
        return await service.create(data, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{item_id}", response_model=MyResponse)
async def get_item(item_id: UUID, db: DatabaseSession):
    """Get item by ID."""
    service = MyService(db)
    item = await service.get_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.put("/{item_id}", response_model=MyResponse)
async def update_item(
    item_id: UUID,
    data: MyUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Update item."""
    service = MyService(db)
    item = await service.get_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return await service.update(item, data, current_user.id)


@router.delete("/{item_id}", response_model=MessageResponse)
async def delete_item(item_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Delete item (soft delete)."""
    service = MyService(db)
    item = await service.get_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    await service.delete(item, current_user.id)
    return MessageResponse(message="Item deleted successfully")


# ============== ADMIN ENDPOINTS ==============

@router.get("/admin", response_model=PaginatedResponse[MyResponse], dependencies=[RequireAdmin])
async def admin_list(db: DatabaseSession, page: int = Query(1), page_size: int = Query(50)):
    """List all items (admin only)."""
    service = MyService(db)
    items, total = await service.get_list_admin(PaginationParams(page=page, page_size=page_size))
    return PaginatedResponse.create(items, total, page, page_size)
```

### 2. Service Pattern (in `app/services/my_service.py`)

```python
"""Business logic for my domain."""

from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.my_model import MyModel
from app.schemas.common import PaginationParams
from app.schemas.my_schema import MyCreate, MyResponse, MyUpdate
from app.core.logging import get_logger

logger = get_logger(__name__)


class MyService:
    """Service layer for MyModel operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, id: UUID) -> MyModel | None:
        """Get item by ID."""
        result = await self.db.execute(
            select(MyModel).where(MyModel.id == id, MyModel.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def get_list(
        self,
        pagination: PaginationParams,
        search: str | None = None,
    ) -> tuple[list[MyModel], int]:
        """Get paginated list of items."""
        query = select(MyModel).where(MyModel.is_deleted == False)

        if search:
            query = query.where(MyModel.name.ilike(f"%{search}%"))

        # Count total
        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        # Paginate
        query = query.order_by(MyModel.created_at.desc())
        query = query.offset((pagination.page - 1) * pagination.page_size).limit(
            pagination.page_size
        )

        result = await self.db.execute(query)
        items = result.scalars().all()

        return items, total

    async def create(self, data: MyCreate, created_by: UUID) -> MyModel:
        """Create a new item."""
        # Validation
        existing = await self.db.execute(
            select(MyModel).where(MyModel.name == data.name)
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Item with name '{data.name}' already exists")

        # Create
        item = MyModel(**data.model_dump(), created_by=created_by)
        self.db.add(item)
        await self.db.flush()

        logger.info("item_created", item_id=str(item.id), name=data.name)

        return item

    async def update(
        self, item: MyModel, data: MyUpdate, updated_by: UUID
    ) -> MyModel:
        """Update an item."""
        # Update only provided fields
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(item, field, value)

        item.updated_by = updated_by
        await self.db.flush()

        logger.info("item_updated", item_id=str(item.id))

        return item

    async def delete(self, item: MyModel, deleted_by: UUID) -> None:
        """Soft delete an item."""
        item.soft_delete(deleted_by=deleted_by)
        await self.db.flush()

        logger.info("item_deleted", item_id=str(item.id))

    async def get_list_admin(self, pagination: PaginationParams) -> tuple[list, int]:
        """Get all items including soft-deleted (admin only)."""
        query = select(MyModel)  # No is_deleted filter for admin
        
        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = query.order_by(MyModel.created_at.desc())
        query = query.offset((pagination.page - 1) * pagination.page_size).limit(
            pagination.page_size
        )

        result = await self.db.execute(query)
        return result.scalars().all(), total
```

### 3. Schema Pattern (in `app/schemas/my_schema.py`)

```python
"""Request/Response schemas for my domain."""

from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

from app.schemas.common import BaseSchema


class MyCreate(BaseModel):
    """Schema for creating an item."""
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    is_active: bool = True


class MyUpdate(BaseModel):
    """Schema for updating an item."""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    is_active: Optional[bool] = None


class MyResponse(BaseSchema):
    """Complete response schema."""
    id: UUID
    name: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MyListResponse(BaseModel):
    """Condensed list view schema."""
    id: UUID
    name: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

### 4. Model Pattern (in `app/models/my_model.py`)

```python
"""ORM model for my domain."""

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean, Text

from app.models.base import BaseModel


class MyModel(BaseModel):
    """My domain model."""

    __tablename__ = "my_table"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<MyModel(id={self.id}, name={self.name})>"
```

### 5. Register Router (in `app/api/v1/api_router.py`)

```python
from app.api.v1 import my_domain

api_router.include_router(
    my_domain.router,
    prefix="/my-domain",
    tags=["My Domain"]
)
```

---

## Key Patterns to Follow

### Error Handling

```python
# Use HTTPException with appropriate status codes
raise HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail="Descriptive error message"
)

# Validate in service, not router
try:
    result = await service.create(data)
except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc))
```

### Filtering & Search

```python
# Always support pagination
page: int = Query(1, ge=1)
page_size: int = Query(20, ge=1, le=100)

# Use Optional for filters
search: Optional[str] = None
category_id: Optional[UUID] = None
sort_by: Optional[str] = Query("created_at", pattern="^(created_at|name|rating)$")

# In service:
query = select(Model).where(Model.is_deleted == False)
if search:
    query = query.where(Model.name.ilike(f"%{search}%"))
if category_id:
    query = query.where(Model.category_id == category_id)
```

### Authentication Guards

```python
# Require Bearer token
@router.get("/me", response_model=MyResponse)
async def get_my_item(current_user: CurrentUser, db: DatabaseSession):
    """User must be authenticated."""
    pass

# Require specific role
@router.delete("/{id}", dependencies=[RequireAdmin])
async def delete_item(id: UUID, db: DatabaseSession):
    """Only admins can access."""
    pass

# Require doctor role
@router.post("/consultations", dependencies=[RequireDoctor])
async def create_consultation(data: ConsultationCreate, db: DatabaseSession):
    """Only doctors can create."""
    pass
```

### Always Use Soft Delete

```python
# Don't:
# await db.delete(item)

# Do:
await item.soft_delete(deleted_by=current_user.id)
await db.commit()

# Query exclusion:
query = select(MyModel).where(MyModel.is_deleted == False)
```

### Logging

```python
from app.core.logging import get_logger

logger = get_logger(__name__)

# Always use event names + key-value context
logger.info("appointment_scheduled", 
    patient_id=str(patient.id),
    doctor_id=str(doctor.id),
    reference=reference
)

logger.error("payment_failed",
    booking_id=str(booking.id),
    error=str(exception)
)
```

### Response Consistency

```python
# Single item
@router.get("/{id}", response_model=MyResponse)
async def get_item(id: UUID, db: DatabaseSession):
    item = await service.get_by_id(id)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    return item

# List with pagination
@router.get("", response_model=PaginatedResponse[MyResponse])
async def list_items(db: DatabaseSession, page: int = Query(1)):
    items, total = await service.get_list(PaginationParams(page=page))
    return PaginatedResponse.create(items, total, page, 20)

# Message response
@router.post("/{id}/approve")
async def approve(id: UUID, db: DatabaseSession) -> MessageResponse:
    await service.approve(id)
    return MessageResponse(message="Approved successfully")

# Simple response
@router.get("/stats")
async def get_stats(db: DatabaseSession):
    return {
        "total_items": 100,
        "active_items": 85,
        "pending_items": 15
    }
```

### Timezone Handling

```python
# Use UTC everywhere
from datetime import datetime, timezone

created_at = datetime.now(timezone.utc)

# Don't: created_at = datetime.now()
```

### Transaction Pattern

```python
# Services should not explicitly commit for read operations
async def get_list(self, pagination):
    result = await self.db.execute(select(MyModel))
    return result.scalars().all(), total
    # No commit needed, session dependency auto-commits on success

# For write operations, just flush
async def create(self, data):
    item = MyModel(**data.model_dump())
    self.db.add(item)
    await self.db.flush()  # Not commit - let session dependency handle it
    return item

# Exception: AppointmentService explicitly commits before side-effects
async def schedule_appointment(self, patient, data):
    consultation = Consultation(...)
    self.db.add(consultation)
    await self.db.commit()  # Explicit commit before email
    
    # Now send email (if fails, consultation still persisted)
    await send_email(...)
```

### Query Building

```python
from sqlalchemy import select, func, and_, or_

# Simple query
query = select(MyModel).where(MyModel.is_deleted == False)

# Multiple conditions
query = query.where(
    and_(
        MyModel.is_active == True,
        MyModel.category_id == category_id
    )
)

# OR conditions
query = query.where(
    or_(
        MyModel.name.ilike(f"%{search}%"),
        MyModel.description.ilike(f"%{search}%")
    )
)

# Ordering and pagination
query = query.order_by(MyModel.created_at.desc())
query = query.offset((page - 1) * page_size).limit(page_size)

# Count
count_result = await db.execute(
    select(func.count()).select_from(query.subquery())
)
total = count_result.scalar() or 0
```

### Filtering by Date Range

```python
from datetime import date, datetime, timedelta

@router.get("/items")
async def filter_by_date(
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: DatabaseSession
):
    query = select(MyModel).where(
        and_(
            MyModel.created_at >= datetime.combine(start_date, datetime.min.time()),
            MyModel.created_at <= datetime.combine(end_date, datetime.max.time()),
        )
    )
    result = await db.execute(query)
    return result.scalars().all()
```

### Relationships in Models

```python
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey

class MyModel(BaseModel):
    __tablename__ = "my_table"
    
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    user: Mapped["User"] = relationship(back_populates="my_items")
```

### JSONB Columns

```python
from sqlalchemy.dialects.postgresql import JSONB

class MyModel(BaseModel):
    __tablename__ = "my_table"
    
    metadata_: Mapped[dict] = mapped_column(
        JSONB,
        default={},
        nullable=False
    )

# Usage:
item.metadata_["key"] = "value"
await db.commit()
```

### Reference ID Generation

```python
from app.utils.helpers import generate_reference_id

# Generate reference numbers in format: PREFIX-YYYYMMDD-XXXXXX
reference = generate_reference_id("CNS")  # CNS-20240124-AB12CD
booking_ref = generate_reference_id("BKG")  # BKG-20240124-XY78ZW
```

---

## Testing Pattern

```python
# In tests/conftest.py (already exists)
@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

# In tests/test_my_domain.py
@pytest.mark.asyncio
async def test_list_items(client):
    response = await client.get("/api/v1/my-domain")
    assert response.status_code == 200
    assert "items" in response.json()

@pytest.mark.asyncio
async def test_create_item(client):
    response = await client.post(
        "/api/v1/my-domain",
        json={"name": "Test Item", "description": "..."}
    )
    assert response.status_code == 201
```

---

## File Checklist for New Domain

- [ ] `app/models/my_model.py` — ORM model
- [ ] `app/schemas/my_schema.py` — Pydantic schemas
- [ ] `app/services/my_service.py` — Business logic
- [ ] `app/api/v1/my_domain.py` — Endpoints router
- [ ] Update `app/api/v1/api_router.py` — Register router
- [ ] `tests/test_my_domain.py` — Tests
- [ ] Database migration: `alembic revision --autogenerate -m "add my_table"`

