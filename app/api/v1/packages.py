"""Public medical packages endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DatabaseSession, RequirePatient
from app.models.hospital import Department, Hospital
from app.models.package import MedicalPackage
from app.schemas.booking import BookingResponse
from app.schemas.common import BasicResponse, PaginatedResponse
from app.schemas.package import PackageBookingCreate, PackageListResponse, PackageResponse
from app.services.package_service import PackageService
from app.services.patient_service import PatientService
from app.utils.enums import PackageCategory

router = APIRouter()


def _build_list_response(package: MedicalPackage, hospital_name: Optional[str]) -> PackageListResponse:
    return PackageListResponse(
        id=package.id,
        name=package.name,
        slug=package.slug,
        short_description=package.short_description,
        category=package.category,
        price=package.price,
        discounted_price=package.discounted_price,
        discount_percentage=package.discount_percentage,
        currency=package.currency,
        duration_days=package.duration_days,
        image_url=package.image_url,
        is_featured=package.is_featured,
        hospital_id=package.hospital_id,
        hospital_name=hospital_name,
        created_at=package.created_at,
    )


@router.get("/categories", response_model=list[BasicResponse])
async def list_categories():
    """Return all available package categories."""
    return [BasicResponse(id=c.value, name=c.value.replace("_", " ").title()) for c in PackageCategory]


@router.get("", response_model=PaginatedResponse[PackageListResponse])
async def list_packages(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[PackageCategory] = Query(default=None),
    hospital_id: Optional[UUID] = Query(default=None),
    featured: Optional[bool] = Query(default=None),
    search: Optional[str] = Query(default=None),
):
    """List active medical packages with optional filters."""
    from app.schemas.common import PaginationParams

    service = PackageService(db)
    packages, total = await service.get_list(
        pagination=PaginationParams(page=page, page_size=page_size),
        category=category,
        hospital_id=hospital_id,
        featured=featured,
        search=search,
        active_only=True,
    )

    # Batch-load hospital names
    hospital_ids = {p.hospital_id for p in packages if p.hospital_id}
    hospital_map: dict[UUID, str] = {}
    if hospital_ids:
        rows = await db.execute(
            select(Hospital.id, Hospital.name).where(Hospital.id.in_(hospital_ids))
        )
        hospital_map = {row.id: row.name for row in rows.all()}

    items = [_build_list_response(p, hospital_map.get(p.hospital_id)) for p in packages]
    return PaginatedResponse.create(items, total, page, page_size)


@router.get("/{package_id}", response_model=PackageResponse)
async def get_package(package_id: UUID, db: DatabaseSession):
    """Get full package detail including items."""
    service = PackageService(db)
    package = await service.get_by_id(package_id)
    if not package or not package.is_active:
        raise HTTPException(status_code=404, detail="Package not found")

    hospital_name: Optional[str] = None
    department_name: Optional[str] = None

    if package.hospital_id:
        result = await db.execute(select(Hospital.name).where(Hospital.id == package.hospital_id))
        row = result.one_or_none()
        hospital_name = row[0] if row else None

    if package.department_id:
        result = await db.execute(select(Department.name).where(Department.id == package.department_id))
        row = result.one_or_none()
        department_name = row[0] if row else None

    return PackageResponse(
        **{k: getattr(package, k) for k in PackageResponse.model_fields if hasattr(package, k)},
        hospital_name=hospital_name,
        department_name=department_name,
        discount_percentage=package.discount_percentage,
        items=[
            {
                "id": item.id,
                "package_id": item.package_id,
                "item_type": item.item_type,
                "name": item.name,
                "description": item.description,
                "quantity": item.quantity,
                "unit": item.unit,
                "display_order": item.display_order,
                "created_at": item.created_at,
            }
            for item in package.items
            if not item.is_deleted
        ],
    )


@router.get("/slug/{slug}", response_model=PackageResponse)
async def get_package_by_slug(slug: str, db: DatabaseSession):
    """Get full package detail by slug."""
    service = PackageService(db)
    package = await service.get_by_slug(slug)
    if not package or not package.is_active:
        raise HTTPException(status_code=404, detail="Package not found")
    # Delegate to get_package to keep logic DRY
    return await get_package(package.id, db)


@router.post("/{package_id}/book", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def book_package(
    package_id: UUID,
    data: PackageBookingCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
    _: None = RequirePatient,
):
    """Book a medical package (authenticated patients only)."""
    if data.package_id != package_id:
        data = data.model_copy(update={"package_id": package_id})

    patient_service = PatientService(db)
    patient = await patient_service.get_or_create(current_user.id)

    pkg_service = PackageService(db)
    try:
        booking = await pkg_service.book_package(
            patient_id=patient.id,
            data=data,
            created_by=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return BookingResponse(
        id=booking.id,
        patient_id=booking.patient_id,
        reference_number=booking.reference_number,
        booking_type=booking.booking_type,
        status=booking.status,
        package_id=booking.package_id,
        booking_date=booking.booking_date,
        guest_count=booking.guest_count,
        guest_details=booking.guest_details,
        base_price=booking.base_price,
        taxes=booking.taxes,
        discount=booking.discount,
        total_price=booking.total_price,
        currency=booking.currency,
        discount_code=booking.discount_code,
        is_paid=booking.is_paid,
        special_requests=booking.special_requests,
        notes=booking.notes,
        confirmed_at=booking.confirmed_at,
        created_at=booking.created_at,
        updated_at=booking.updated_at,
    )
