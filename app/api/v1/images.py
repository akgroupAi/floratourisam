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
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",
    "text/csv",
    "application/zip",
    "application/x-rar-compressed",
    "application/dicom",
}

ALLOWED_EXTENSIONS = {
    "jpg", "jpeg", "png", "gif", "webp", "svg",
    "pdf", "doc", "docx", "xls", "xlsx", "txt", "csv",
    "zip", "rar", "dicom", "dcm",
}


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
    Upload a file. Requires authentication (any role).

    - Accepts: images (`jpg`, `jpeg`, `png`, `gif`, `webp`, `svg`),
      documents (`pdf`, `doc`, `docx`, `xls`, `xlsx`, `txt`, `csv`),
      archives (`zip`, `rar`), medical (`dicom`, `dcm`)
    - Max size: configured by `MAX_UPLOAD_SIZE_MB` (default 10 MB)
    - Returns the public URL that anyone can use to access the file.
    """
    # --- validate extension first (more reliable than content-type) ---
    original_filename = file.filename or "file"
    ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension '.{ext}'. "
                   f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # --- get content type ---
    content_type = file.content_type or "application/octet-stream"

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


# ── Public: serve hospital media ─────────────────────────────────────────────

@public_router.get(
    "/hospitals/{hospital_id}/{filename}",
    summary="Get hospital media file (public)",
    response_class=FileResponse,
)
async def get_hospital_media(hospital_id: str, filename: str):
    """Serve hospital cover/gallery media files."""
    safe_hospital_id = os.path.basename(hospital_id)
    safe_filename = os.path.basename(filename)
    if safe_hospital_id != hospital_id or safe_filename != filename or ".." in hospital_id or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid path.")

    ext = safe_filename.rsplit(".", 1)[-1].lower() if "." in safe_filename else ""
    allowed = {
        "jpg", "jpeg", "png", "gif", "webp", "svg",
        "mp4", "webm", "mov", "m4v",
    }
    if ext not in allowed:
        raise HTTPException(status_code=400, detail="Invalid file type.")

    file_path = os.path.join(settings.UPLOAD_DIR, "hospitals", safe_hospital_id, safe_filename)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found.")

    media_type_map = {
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
    return FileResponse(
        path=file_path,
        media_type=media_type_map.get(ext, "application/octet-stream"),
        filename=safe_filename,
    )


# ── Public: serve an image ───────────────────────────────────────────────────

@public_router.get(
    "/{filename}",
    summary="Get a file (public)",
    response_class=FileResponse,
)
async def get_image(filename: str):
    """
    Publicly accessible endpoint to retrieve an uploaded file by filename.

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
        raise HTTPException(status_code=404, detail="File not found.")

    media_type_map = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
        "svg": "image/svg+xml",
        "pdf": "application/pdf",
        "doc": "application/msword",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xls": "application/vnd.ms-excel",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "txt": "text/plain",
        "csv": "text/csv",
        "zip": "application/zip",
        "rar": "application/x-rar-compressed",
        "dicom": "application/dicom",
        "dcm": "application/dicom",
    }
    media_type = media_type_map.get(ext, "application/octet-stream")

    return FileResponse(path=file_path, media_type=media_type, filename=safe_filename)
