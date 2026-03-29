"""Frontend endpoints for Forex Currency Exchange."""

import os
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DatabaseSession
from app.core.config import settings
from app.models.forex import Currency, ForexRequest
from app.schemas.common import PaginatedResponse
from app.schemas.forex import CurrencyResponse, ForexRequestResponse

router = APIRouter()


@router.get("/currencies", response_model=List[CurrencyResponse])
async def list_active_currencies(db: DatabaseSession):
    """List all active currencies for the frontend."""
    query = select(Currency).where(Currency.is_deleted == False, Currency.is_active == True).order_by(Currency.code.asc())
    result = await db.execute(query)
    currencies = result.scalars().all()
    return currencies


@router.get("/calculate")
async def calculate_forex(
    from_currency_id: uuid.UUID,
    to_currency_id: uuid.UUID,
    amount: float = Query(..., gt=0),
    db: DatabaseSession = None,
):
    """Calculate the exchange rate amount."""
    # Note: Using CurrentUser creates dependency, here calculate can potentially be public.
    from_curr = await db.execute(select(Currency).where(Currency.id == from_currency_id, Currency.is_active == True))
    from_curr = from_curr.scalar_one_or_none()
    
    to_curr = await db.execute(select(Currency).where(Currency.id == to_currency_id, Currency.is_active == True))
    to_curr = to_curr.scalar_one_or_none()

    if not from_curr or not to_curr:
        raise HTTPException(status_code=404, detail="Currency not found or not active")

    # Assuming exchange_rate is relative to base currency (e.g. 1 USD)
    # Ex: USD to INR (from=1.0, to=83.0)
    # rate_applied = to_curr / from_curr = 83.0 / 1.0 = 83.0
    rate_applied = to_curr.exchange_rate / from_curr.exchange_rate
    calculated_amount = amount * rate_applied

    return {
        "from_currency": from_curr.code,
        "to_currency": to_curr.code,
        "amount": amount,
        "rate_applied": rate_applied,
        "calculated_amount": calculated_amount,
    }


@router.post("/requests", response_model=ForexRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_forex_request(
    current_user: CurrentUser,
    db: DatabaseSession,
    from_currency_id: uuid.UUID = Form(...),
    to_currency_id: uuid.UUID = Form(...),
    amount: float = Form(..., gt=0),
    purpose: str = Form(..., min_length=2, max_length=255),
    additional_notes: Optional[str] = Form(None),
    passport_doc: Optional[UploadFile] = File(None),
    visa_doc: Optional[UploadFile] = File(None),
    medical_doc: Optional[UploadFile] = File(None),
):
    """Submit a forex exchange request with documents."""
    
    # 1. Validate currencies
    from_curr_res = await db.execute(select(Currency).where(Currency.id == from_currency_id, Currency.is_active == True))
    from_curr = from_curr_res.scalar_one_or_none()
    
    to_curr_res = await db.execute(select(Currency).where(Currency.id == to_currency_id, Currency.is_active == True))
    to_curr = to_curr_res.scalar_one_or_none()

    if not from_curr or not to_curr:
        raise HTTPException(status_code=404, detail="Currency not found or not active")

    # 2. Calculate values
    rate_applied = to_curr.exchange_rate / from_curr.exchange_rate
    calculated_amount = amount * rate_applied

    # 3. Handle File Uploads
    async def save_upload(file: UploadFile) -> Optional[str]:
        if not file:
            return None
            
        allowed_types = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail=f"File {file.filename} must be an image or PDF.")
            
        contents = await file.read()
        if len(contents) > 5 * 1024 * 1024:  # 5MB limit
            raise HTTPException(status_code=400, detail=f"File {file.filename} must not exceed 5 MB.")
            
        upload_dir = Path("uploads/forex") / str(current_user.id)
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        file_ext = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "pdf"
        filename = f"{uuid.uuid4()}.{file_ext}"
        file_path = upload_dir / filename
        
        with open(file_path, "wb") as f:
            f.write(contents)
            
        return f"/api/v1/documents/{filename}/download"

    passport_url = await save_upload(passport_doc)
    visa_url = await save_upload(visa_doc)
    medical_url = await save_upload(medical_doc)

    # 4. Create request
    forex_request = ForexRequest(
        user_id=current_user.id,
        created_by=current_user.id,
        from_currency_id=from_currency_id,
        to_currency_id=to_currency_id,
        amount=amount,
        calculated_amount=calculated_amount,
        rate_applied=rate_applied,
        purpose=purpose,
        additional_notes=additional_notes,
        passport_doc_url=passport_url,
        visa_doc_url=visa_url,
        medical_doc_url=medical_url,
        status="pending"
    )
    
    db.add(forex_request)
    await db.commit()
    await db.refresh(forex_request)
    
    # Reload with relationships for response
    res = await db.execute(
        select(ForexRequest)
        .options(selectinload(ForexRequest.from_currency), selectinload(ForexRequest.to_currency))
        .where(ForexRequest.id == forex_request.id)
    )
    return res.scalar_one()


@router.get("/requests", response_model=PaginatedResponse[ForexRequestResponse])
async def list_my_forex_requests(
    current_user: CurrentUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List current user's forex requests (My Requests tab)."""
    query = select(ForexRequest).options(
        selectinload(ForexRequest.from_currency),
        selectinload(ForexRequest.to_currency),
    ).where(ForexRequest.is_deleted == False, ForexRequest.user_id == current_user.id)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    query = query.order_by(ForexRequest.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    requests = result.scalars().all()

    return PaginatedResponse.create(requests, total, page, page_size)
