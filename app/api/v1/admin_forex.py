"""Admin endpoints for Forex Currency Exchange."""

from datetime import date, datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel as PydanticBaseModel
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.models.forex import Currency, ForexRequest
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.forex import (
    CurrencyCreate,
    CurrencyResponse,
    CurrencyUpdate,
    ForexRequestResponse,
    ForexRequestStatusUpdate,
)

router = APIRouter()


# ============== CURRENCIES ADMIN ==============


@router.get("/currencies", response_model=PaginatedResponse[CurrencyResponse], dependencies=[RequireAdmin])
async def list_currencies(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_active: Optional[bool] = None,
):
    """List all currencies (admin)."""
    query = select(Currency).where(Currency.is_deleted == False)

    if is_active is not None:
        query = query.where(Currency.is_active == is_active)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    query = query.order_by(Currency.code.asc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    currencies = result.scalars().all()

    return PaginatedResponse.create(currencies, total, page, page_size)


@router.post(
    "/currencies",
    response_model=CurrencyResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[RequireAdmin],
)
async def create_currency(data: CurrencyCreate, current_user: CurrentUser, db: DatabaseSession):
    """Create a new currency."""
    existing = await db.execute(select(Currency).where(Currency.code == data.code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Currency with code '{data.code}' already exists")

    currency = Currency(**data.model_dump(), created_by=current_user.id)
    db.add(currency)
    await db.commit()
    await db.refresh(currency)
    return currency


@router.get("/currencies/{currency_id}", response_model=CurrencyResponse, dependencies=[RequireAdmin])
async def get_currency(currency_id: UUID, db: DatabaseSession):
    """Get currency details."""
    result = await db.execute(select(Currency).where(Currency.id == currency_id, Currency.is_deleted == False))
    currency = result.scalar_one_or_none()
    if not currency:
        raise HTTPException(status_code=404, detail="Currency not found")
    return currency


@router.put("/currencies/{currency_id}", response_model=CurrencyResponse, dependencies=[RequireAdmin])
async def update_currency(
    currency_id: UUID,
    data: CurrencyUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Update a currency."""
    result = await db.execute(select(Currency).where(Currency.id == currency_id, Currency.is_deleted == False))
    currency = result.scalar_one_or_none()
    if not currency:
        raise HTTPException(status_code=404, detail="Currency not found")

    if data.code and data.code != currency.code:
        existing = await db.execute(select(Currency).where(Currency.code == data.code, Currency.id != currency_id))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"Currency with code '{data.code}' already exists")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(currency, field, value)

    currency.updated_by = current_user.id
    await db.commit()
    await db.refresh(currency)
    return currency


@router.delete("/currencies/{currency_id}", response_model=MessageResponse, dependencies=[RequireAdmin])
async def delete_currency(currency_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Soft delete a currency."""
    result = await db.execute(select(Currency).where(Currency.id == currency_id, Currency.is_deleted == False))
    currency = result.scalar_one_or_none()
    if not currency:
        raise HTTPException(status_code=404, detail="Currency not found")

    currency.is_deleted = True
    currency.deleted_by = current_user.id
    await db.commit()
    return MessageResponse(message="Currency deleted successfully")


# ============== FOREX REQUESTS ADMIN ==============


@router.get("/requests", response_model=PaginatedResponse[ForexRequestResponse], dependencies=[RequireAdmin])
async def list_forex_requests(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    search: Optional[str] = Query(None, description="Search by user name, email, purpose, or currency code"),
    created_from: Optional[date] = Query(None, description="Filter requests created on or after this date"),
    created_to: Optional[date] = Query(None, description="Filter requests created on or before this date"),
):
    """List all forex exchange requests (admin) with search and date filtering."""
    query = select(ForexRequest).options(
        selectinload(ForexRequest.from_currency),
        selectinload(ForexRequest.to_currency),
    ).join(User, ForexRequest.user_id == User.id
    ).outerjoin(Currency, ForexRequest.from_currency_id == Currency.id
    ).where(ForexRequest.is_deleted == False)

    if status:
        query = query.where(ForexRequest.status == status)

    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                User.full_name.ilike(search_term),
                User.email.ilike(search_term),
                ForexRequest.purpose.ilike(search_term),
            )
        )

    if created_from:
        query = query.where(
            ForexRequest.created_at >= datetime.combine(created_from, datetime.min.time()).replace(tzinfo=timezone.utc)
        )
    if created_to:
        query = query.where(
            ForexRequest.created_at <= datetime.combine(created_to, datetime.max.time()).replace(tzinfo=timezone.utc)
        )

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    query = query.order_by(ForexRequest.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    requests = result.scalars().all()

    return PaginatedResponse.create(requests, total, page, page_size)


@router.put("/requests/{request_id}/status", response_model=ForexRequestResponse, dependencies=[RequireAdmin])
async def update_request_status(
    request_id: UUID,
    data: ForexRequestStatusUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Approve, reject, or mark forex request as completed."""
    result = await db.execute(
        select(ForexRequest)
        .options(
            selectinload(ForexRequest.from_currency),
            selectinload(ForexRequest.to_currency),
        )
        .where(ForexRequest.id == request_id, ForexRequest.is_deleted == False)
    )
    request_obj = result.scalar_one_or_none()
    if not request_obj:
        raise HTTPException(status_code=404, detail="Forex request not found")

    request_obj.status = data.status
    if data.admin_remarks is not None:
        request_obj.admin_remarks = data.admin_remarks
    request_obj.updated_by = current_user.id
    await db.commit()
    await db.refresh(request_obj)
    return request_obj


# ============== FOREX DASHBOARD ==============


class ForexDashboardResponse(PydanticBaseModel):
    """Forex dashboard KPI stats."""
    total_requests: int = 0
    pending: int = 0
    under_review: int = 0
    approved: int = 0
    rejected: int = 0
    completed: int = 0


@router.get("/dashboard", response_model=ForexDashboardResponse, dependencies=[RequireAdmin])
async def forex_dashboard(db: DatabaseSession):
    """Get forex request statistics for admin dashboard."""
    result = await db.execute(
        select(
            func.count().label("total_requests"),
            func.count().filter(ForexRequest.status == "pending").label("pending"),
            func.count().filter(ForexRequest.status == "under_review").label("under_review"),
            func.count().filter(ForexRequest.status == "approved").label("approved"),
            func.count().filter(ForexRequest.status == "rejected").label("rejected"),
            func.count().filter(ForexRequest.status == "completed").label("completed"),
        ).where(ForexRequest.is_deleted == False)
    )
    row = result.one()

    return ForexDashboardResponse(
        total_requests=row.total_requests,
        pending=row.pending,
        under_review=row.under_review,
        approved=row.approved,
        rejected=row.rejected,
        completed=row.completed,
    )
