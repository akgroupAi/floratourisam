"""Image upload (super-admin only) and public image serving endpoints."""

import os
import uuid as uuid_lib

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import CurrentUser
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Two separate routers so admin upload and public serve never cross-contaminate.
admin_router = APIRouter()
public_router = APIRouter()

IMAGES_DIR = os.path.join(settings.UPLOAD_DIR, "images")

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/svg+xml",
}

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp", "svg"}


def _ensure_images_dir() -> None:
    os.makedirs(IMAGES_DIR, exist_ok=True)


# ── Admin: upload an image ────────────────────────────────────────────────────

@admin_router.post(
    "/upload",
    summary="Upload an image",
)
async def upload_image(
    current_user: CurrentUser,
    file: UploadFile = File(..., description="Image file to upload"),
):
    """
    Upload an image file. Requires authentication (any role).

    - Accepts: `jpg`, `jpeg`, `png`, `gif`, `webp`, `svg`
    - Max size: configured by `MAX_UPLOAD_SIZE_MB` (default 10 MB)
    - Returns the public URL that anyone can use to access the image.
    """
    # --- validate content-type ---
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{content_type}'. "
                   f"Allowed types: {', '.join(sorted(ALLOWED_IMAGE_TYPES))}",
        )

    # --- validate extension ---
    original_filename = file.filename or "image"
    ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension '.{ext}'. "
                   f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # --- read & validate size ---
    content = await file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum allowed size is {settings.MAX_UPLOAD_SIZE_MB} MB.",
        )

    # --- persist ---
    _ensure_images_dir()
    unique_filename = f"{uuid_lib.uuid4()}.{ext}"
    file_path = os.path.join(IMAGES_DIR, unique_filename)
    with open(file_path, "wb") as fh:
        fh.write(content)

    public_url = f"/api/v1/images/{unique_filename}"

    logger.info(
        "image_uploaded",
        filename=unique_filename,
        original=original_filename,
        size=len(content),
        url=public_url,
    )

    return {
        "filename": unique_filename,
        "original_filename": original_filename,
        "url": public_url,
        "size": len(content),
        "content_type": content_type,
    }


# ── Public: serve an image ───────────────────────────────────────────────────

@public_router.get(
    "/{filename}",
    summary="Get an image (public)",
    response_class=FileResponse,
)
async def get_image(filename: str):
    """
    Publicly accessible endpoint to retrieve an uploaded image by filename.

    No authentication required.
    """
    # Prevent directory traversal
    safe_filename = os.path.basename(filename)
    if safe_filename != filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    ext = safe_filename.rsplit(".", 1)[-1].lower() if "." in safe_filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Invalid file type.")

    file_path = os.path.join(IMAGES_DIR, safe_filename)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Image not found.")

    media_type_map = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
        "svg": "image/svg+xml",
    }
    media_type = media_type_map.get(ext, "application/octet-stream")

    return FileResponse(path=file_path, media_type=media_type, filename=safe_filename)
