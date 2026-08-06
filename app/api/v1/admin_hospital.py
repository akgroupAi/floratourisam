"""Hospital management endpoints for admin panel."""

import os
import uuid as uuid_lib
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select, func, or_

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.core.config import settings
from app.models.hospital import Hospital, Department
from app.models.doctor import Doctor
from app.schemas.common import PaginatedResponse, MessageResponse

router = APIRouter()

HOSPITAL_MEDIA_DIR = os.path.join(settings.UPLOAD_DIR, "hospitals")
ALLOWED_MEDIA_EXTENSIONS = {
    # images
    "jpg", "jpeg", "png", "gif", "webp", "svg",
    # videos
    "mp4", "webm", "mov", "m4v",
}
MEDIA_TYPE_MAP = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
    "svg": "image/svg+xml",
    "mp4": "video/mp4",
    "webm": "video/webm",
    "mov": "video/quicktime",
    "m4v": "video/x-m4v",
}


def _ensure_hospital_media_dir(hospital_id: UUID) -> str:
    path = os.path.join(HOSPITAL_MEDIA_DIR, str(hospital_id))
    os.makedirs(path, exist_ok=True)
    return path


async def _save_hospital_media(hospital_id: UUID, file: UploadFile) -> dict:
    """Save an uploaded image/video and return public URL metadata."""
    original_filename = file.filename or "file"
    ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else ""
    if ext not in ALLOWED_MEDIA_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '.{ext}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_MEDIA_EXTENSIONS))}"
            ),
        )

    content = await file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    # Allow larger media for videos (up to 50MB)
    if ext in {"mp4", "webm", "mov", "m4v"}:
        max_bytes = max(max_bytes, 50 * 1024 * 1024)
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum allowed size is {max_bytes // (1024 * 1024)} MB.",
        )

    folder = _ensure_hospital_media_dir(hospital_id)
    unique_filename = f"{uuid_lib.uuid4()}.{ext}"
    file_path = os.path.join(folder, unique_filename)
    with open(file_path, "wb") as fh:
        fh.write(content)

    public_url = f"/api/v1/images/hospitals/{hospital_id}/{unique_filename}"
    return {
        "filename": unique_filename,
        "original_filename": original_filename,
        "url": public_url,
        "size": len(content),
        "content_type": file.content_type or MEDIA_TYPE_MAP.get(ext, "application/octet-stream"),
        "media_type": "video" if ext in {"mp4", "webm", "mov", "m4v"} else "image",
    }


# ============== SCHEMAS ==============

class HospitalCreate(BaseModel):
    """Schema for creating a hospital."""
    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address_line1: str = Field(..., min_length=2)
    address_line2: Optional[str] = None
    city: str = Field(..., min_length=2)
    state: Optional[str] = None
    country: str = Field(..., min_length=2)
    postal_code: Optional[str] = None
    # Canonical fields
    cover_image_url: Optional[str] = None
    logo_url: Optional[str] = None
    gallery: Optional[List[str]] = None
    # Frontend form aliases
    cover_image: Optional[str] = Field(
        default=None,
        description="Alias for cover_image_url (admin form field name)",
    )
    image_gallery: Optional[List[str]] = Field(
        default=None,
        description="Alias for gallery — list of photo/video URLs",
    )
    is_active: bool = True

    @model_validator(mode="after")
    def merge_media_aliases(self):
        if self.cover_image and not self.cover_image_url:
            self.cover_image_url = self.cover_image
        if self.image_gallery is not None and self.gallery is None:
            self.gallery = self.image_gallery
        return self


class HospitalUpdate(BaseModel):
    """Schema for updating a hospital."""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    slug: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    cover_image_url: Optional[str] = None
    logo_url: Optional[str] = None
    gallery: Optional[List[str]] = None
    cover_image: Optional[str] = Field(
        default=None,
        description="Alias for cover_image_url (admin form field name)",
    )
    image_gallery: Optional[List[str]] = Field(
        default=None,
        description="Alias for gallery — list of photo/video URLs",
    )
    is_active: Optional[bool] = None

    @model_validator(mode="after")
    def merge_media_aliases(self):
        if self.cover_image is not None and self.cover_image_url is None:
            self.cover_image_url = self.cover_image
        if self.image_gallery is not None and self.gallery is None:
            self.gallery = self.image_gallery
        return self


class HospitalResponse(BaseModel):
    """Schema for hospital response."""
    id: UUID
    name: str
    slug: str
    description: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: Optional[str] = None
    country: str
    postal_code: Optional[str] = None
    cover_image_url: Optional[str] = None
    logo_url: Optional[str] = None
    gallery: Optional[List[str]] = None
    # Aliases for admin frontend form binding
    cover_image: Optional[str] = None
    image_gallery: Optional[List[str]] = None
    is_active: bool
    total_doctors: int = 0

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def populate_aliases(self):
        self.cover_image = self.cover_image_url
        self.image_gallery = self.gallery or []
        return self


class DepartmentCreate(BaseModel):
    """Schema for creating a department."""
    hospital_id: UUID
    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    is_active: bool = True


class DepartmentUpdate(BaseModel):
    """Schema for updating a department."""
    hospital_id: Optional[UUID] = None
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    slug: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class DepartmentResponse(BaseModel):
    """Schema for department response."""
    id: UUID
    hospital_id: UUID
    hospital_name: str
    name: str
    slug: str
    description: Optional[str] = None
    is_active: bool

    model_config = {"from_attributes": True}


class GalleryRemoveRequest(BaseModel):
    url: str = Field(..., description="Gallery media URL to remove")


class GalleryReplaceRequest(BaseModel):
    image_gallery: List[str] = Field(default_factory=list)


# ============== HOSPITAL KPIs ==============

@router.get("/totalhospitals", dependencies=[RequireAdmin])
async def get_total_hospitals(db: DatabaseSession):
    """Get total hospitals count."""
    result = await db.execute(
        select(func.count(Hospital.id)).where(Hospital.is_deleted == False)
    )
    return {"total_hospitals": result.scalar() or 0}


@router.get("/totalactive", dependencies=[RequireAdmin])
async def get_total_active_hospitals(db: DatabaseSession):
    """Get total active hospitals count."""
    result = await db.execute(
        select(func.count(Hospital.id)).where(
            Hospital.is_deleted == False,
            Hospital.is_active == True
        )
    )
    return {"active_hospitals": result.scalar() or 0}


@router.get("/totaldepartments", dependencies=[RequireAdmin])
async def get_total_departments(db: DatabaseSession):
    """Get total departments count across all hospitals."""
    result = await db.execute(
        select(func.count(Department.id)).where(Department.is_deleted == False)
    )
    return {"total_departments": result.scalar() or 0}


@router.get("/totaldoctors", dependencies=[RequireAdmin])
async def get_total_doctors(db: DatabaseSession):
    """Get total doctors assigned to hospitals."""
    result = await db.execute(
        select(func.count(Doctor.id)).where(
            Doctor.is_deleted == False,
            Doctor.hospital_id.isnot(None)
        )
    )
    return {"total_doctors": result.scalar() or 0}


# ============== HOSPITAL CRUD ==============


@router.get("", response_model=PaginatedResponse[HospitalResponse], dependencies=[RequireAdmin])
async def list_hospitals(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    city: Optional[str] = None,
):
    """List all hospitals with filtering."""
    query = select(Hospital).where(Hospital.is_deleted == False)

    if search:
        query = query.where(
            or_(
                Hospital.name.ilike(f"%{search}%"),
                Hospital.city.ilike(f"%{search}%"),
                Hospital.country.ilike(f"%{search}%")
            )
        )

    if is_active is not None:
        query = query.where(Hospital.is_active == is_active)

    if city:
        query = query.where(Hospital.city.ilike(f"%{city}%"))

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    query = query.order_by(Hospital.name)
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    hospitals = result.scalars().all()

    return PaginatedResponse.create(hospitals, total, page, page_size)


@router.post("", response_model=HospitalResponse, dependencies=[RequireAdmin])
async def create_hospital(data: HospitalCreate, current_user: CurrentUser, db: DatabaseSession):
    """Create a new hospital (supports cover_image / image_gallery aliases)."""
    existing = await db.execute(
        select(Hospital).where(Hospital.slug == data.slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Hospital with slug '{data.slug}' already exists"
        )

    payload = data.model_dump(exclude={"cover_image", "image_gallery"})
    hospital = Hospital(
        **payload,
        created_by=current_user.id,
    )

    db.add(hospital)
    await db.commit()
    await db.refresh(hospital)

    return hospital


@router.get("/{hospital_id}", response_model=HospitalResponse, dependencies=[RequireAdmin])
async def get_hospital(hospital_id: UUID, db: DatabaseSession):
    """Get hospital details."""
    result = await db.execute(
        select(Hospital).where(Hospital.id == hospital_id, Hospital.is_deleted == False)
    )
    hospital = result.scalar_one_or_none()

    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    return hospital


@router.put("/{hospital_id}", response_model=HospitalResponse, dependencies=[RequireAdmin])
async def update_hospital(
    hospital_id: UUID,
    data: HospitalUpdate,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Update hospital (supports cover_image / image_gallery aliases)."""
    result = await db.execute(
        select(Hospital).where(Hospital.id == hospital_id, Hospital.is_deleted == False)
    )
    hospital = result.scalar_one_or_none()

    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    if data.slug and data.slug != hospital.slug:
        existing = await db.execute(
            select(Hospital).where(Hospital.slug == data.slug, Hospital.id != hospital_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Hospital with slug '{data.slug}' already exists"
            )

    update_data = data.model_dump(
        exclude_unset=True,
        exclude={"cover_image", "image_gallery"},
    )
    for field, value in update_data.items():
        setattr(hospital, field, value)

    hospital.updated_by = current_user.id
    await db.commit()
    await db.refresh(hospital)

    return hospital


@router.delete("/{hospital_id}", response_model=MessageResponse, dependencies=[RequireAdmin])
async def delete_hospital(hospital_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Soft delete hospital."""
    result = await db.execute(
        select(Hospital).where(Hospital.id == hospital_id, Hospital.is_deleted == False)
    )
    hospital = result.scalar_one_or_none()

    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    hospital.is_deleted = True
    hospital.deleted_by = current_user.id
    await db.commit()

    return MessageResponse(message="Hospital deleted successfully")


# ============== HOSPITAL MEDIA (COVER + GALLERY) ==============


@router.post(
    "/{hospital_id}/cover-image",
    response_model=HospitalResponse,
    dependencies=[RequireAdmin],
)
async def upload_hospital_cover_image(
    hospital_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
    file: UploadFile = File(..., description="Cover image or video"),
):
    """Upload and set hospital cover image (admin form cover_image field)."""
    result = await db.execute(
        select(Hospital).where(Hospital.id == hospital_id, Hospital.is_deleted == False)
    )
    hospital = result.scalar_one_or_none()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    media = await _save_hospital_media(hospital_id, file)
    hospital.cover_image_url = media["url"]
    hospital.updated_by = current_user.id
    await db.commit()
    await db.refresh(hospital)
    return hospital


@router.post(
    "/{hospital_id}/gallery",
    response_model=HospitalResponse,
    dependencies=[RequireAdmin],
)
async def upload_hospital_gallery_media(
    hospital_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
    files: List[UploadFile] = File(..., description="Gallery photos and/or videos"),
):
    """Upload one or more photos/videos into hospital image_gallery."""
    result = await db.execute(
        select(Hospital).where(Hospital.id == hospital_id, Hospital.is_deleted == False)
    )
    hospital = result.scalar_one_or_none()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    gallery = list(hospital.gallery or [])
    for file in files:
        media = await _save_hospital_media(hospital_id, file)
        gallery.append(media["url"])

    hospital.gallery = gallery
    hospital.updated_by = current_user.id
    await db.commit()
    await db.refresh(hospital)
    return hospital


@router.delete(
    "/{hospital_id}/gallery",
    response_model=HospitalResponse,
    dependencies=[RequireAdmin],
)
async def remove_hospital_gallery_item(
    hospital_id: UUID,
    data: GalleryRemoveRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Remove one URL from hospital image_gallery."""
    result = await db.execute(
        select(Hospital).where(Hospital.id == hospital_id, Hospital.is_deleted == False)
    )
    hospital = result.scalar_one_or_none()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    gallery = list(hospital.gallery or [])
    if data.url not in gallery:
        raise HTTPException(status_code=404, detail="Gallery item not found")

    hospital.gallery = [u for u in gallery if u != data.url]
    hospital.updated_by = current_user.id
    await db.commit()
    await db.refresh(hospital)
    return hospital


@router.put(
    "/{hospital_id}/gallery",
    response_model=HospitalResponse,
    dependencies=[RequireAdmin],
)
async def replace_hospital_gallery(
    hospital_id: UUID,
    data: GalleryReplaceRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Replace the full hospital gallery with a list of media URLs."""
    result = await db.execute(
        select(Hospital).where(Hospital.id == hospital_id, Hospital.is_deleted == False)
    )
    hospital = result.scalar_one_or_none()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    hospital.gallery = data.image_gallery
    hospital.updated_by = current_user.id
    await db.commit()
    await db.refresh(hospital)
    return hospital
