"""Travellers and documents on a booking.

Handles who is travelling (the patient plus any companions) and the files they upload —
passport photos, flight tickets, visas, insurance.

Access control matters here more than usual: these are passports and medical reports.
Reads and writes are gated to the patient who owns the booking, an admin, or the manager
of the property the booking is for.
"""

import os
import uuid as _uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.booking import Booking, BookingDocument, BookingGuest
from app.schemas.booking import DOCUMENT_TYPES, BookingGuestCreate, BookingGuestUpdate
from app.utils.constants import API_V1_PREFIX

logger = get_logger(__name__)

BOOKING_DOCUMENTS_SUBDIR = "booking_documents"

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}

MAX_DOCUMENT_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_DOCUMENTS_PER_BOOKING = 25


def booking_documents_dir() -> Path:
    """Where uploaded booking documents live.

    Derived from UPLOAD_DIR so writes and reads agree regardless of the process working
    directory — the mistake that made quote documents unreachable.
    """
    return Path(settings.UPLOAD_DIR) / BOOKING_DOCUMENTS_SUBDIR


def document_download_url(booking_id, document_id) -> str:
    """Authenticated API path for a document. `file_path` is never browser-reachable."""
    return f"{API_V1_PREFIX}/bookings/{booking_id}/documents/{document_id}"


class BookingGuestService:
    """Travellers and documents for one booking."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Travellers ────────────────────────────────────────────

    async def add_guests(
        self,
        booking_id,
        guests: List[BookingGuestCreate],
        created_by,
    ) -> List[BookingGuest]:
        """Attach travellers to a booking.

        Exactly one may be the patient. If the caller sends none, the first traveller is
        promoted — a booking with companions but nobody being treated is meaningless.
        """
        if not guests:
            return []

        patients = [g for g in guests if g.guest_type == "patient"]
        if len(patients) > 1:
            raise ValueError("A booking can only have one patient — mark the rest as companions")

        rows = []
        primary_assigned = False
        for index, guest in enumerate(guests):
            is_patient = guest.guest_type == "patient" or (not patients and index == 0)
            row = BookingGuest(
                booking_id=booking_id,
                guest_type="patient" if is_patient else "companion",
                is_primary=is_patient and not primary_assigned,
                full_name=guest.full_name,
                date_of_birth=guest.date_of_birth,
                gender=guest.gender,
                nationality=guest.nationality,
                passport_number=guest.passport_number,
                passport_expiry=guest.passport_expiry,
                phone=guest.phone,
                email=guest.email,
                relationship_to_patient=(
                    None if is_patient else guest.relationship_to_patient
                ),
                special_needs=guest.special_needs,
                created_by=created_by,
            )
            if row.is_primary:
                primary_assigned = True
            self.db.add(row)
            rows.append(row)

        await self.db.flush()
        logger.info("booking_guests_added", booking_id=str(booking_id), count=len(rows))
        return rows

    async def list_guests(self, booking_id) -> List[dict]:
        """Travellers on a booking, patient first."""
        guests = (
            await self.db.execute(
                select(BookingGuest)
                .where(
                    BookingGuest.booking_id == booking_id,
                    BookingGuest.is_deleted == False,
                )
                .order_by(BookingGuest.is_primary.desc(), BookingGuest.created_at)
            )
        ).scalars().all()

        counts = dict(
            (
                await self.db.execute(
                    select(BookingDocument.guest_id, func.count(BookingDocument.id))
                    .where(
                        BookingDocument.booking_id == booking_id,
                        BookingDocument.is_deleted == False,
                        BookingDocument.guest_id.isnot(None),
                    )
                    .group_by(BookingDocument.guest_id)
                )
            ).all()
        )

        return [
            {
                **{c.name: getattr(g, c.name) for c in g.__table__.columns},
                "document_count": counts.get(g.id, 0),
            }
            for g in guests
        ]

    async def get_guest(self, booking_id, guest_id) -> Optional[BookingGuest]:
        return (
            await self.db.execute(
                select(BookingGuest).where(
                    BookingGuest.id == guest_id,
                    BookingGuest.booking_id == booking_id,
                    BookingGuest.is_deleted == False,
                )
            )
        ).scalar_one_or_none()

    async def update_guest(
        self, booking_id, guest_id, data: BookingGuestUpdate, updated_by
    ) -> BookingGuest:
        guest = await self.get_guest(booking_id, guest_id)
        if not guest:
            raise ValueError("Traveller not found on this booking")

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(guest, field, value)
        guest.updated_by = updated_by

        await self.db.commit()
        await self.db.refresh(guest)
        return guest

    async def remove_guest(self, booking_id, guest_id, deleted_by) -> bool:
        """Soft-delete a companion. The patient cannot be removed from their own booking."""
        guest = await self.get_guest(booking_id, guest_id)
        if not guest:
            return False
        if guest.guest_type == "patient":
            raise ValueError(
                "The patient cannot be removed from a booking — edit their details instead"
            )
        guest.soft_delete(deleted_by)
        await self.db.commit()
        return True

    # ── Documents ─────────────────────────────────────────────

    async def add_document(
        self,
        booking: Booking,
        file: UploadFile,
        document_type: str,
        uploaded_by,
        guest_id=None,
        notes: Optional[str] = None,
    ) -> BookingDocument:
        """Store an uploaded file against a booking, optionally against one traveller."""
        if document_type not in DOCUMENT_TYPES:
            raise ValueError(
                f"document_type must be one of: {', '.join(sorted(DOCUMENT_TYPES))}"
            )

        content_type = (file.content_type or "").lower()
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise ValueError(
                "Unsupported file type. Accepted: JPG, PNG, WebP, PDF."
            )

        existing = (
            await self.db.execute(
                select(func.count(BookingDocument.id)).where(
                    BookingDocument.booking_id == booking.id,
                    BookingDocument.is_deleted == False,
                )
            )
        ).scalar() or 0
        if existing >= MAX_DOCUMENTS_PER_BOOKING:
            raise ValueError(
                f"This booking already has the maximum of {MAX_DOCUMENTS_PER_BOOKING} documents"
            )

        if guest_id is not None:
            guest = await self.get_guest(booking.id, guest_id)
            if not guest:
                raise ValueError("Traveller not found on this booking")

        contents = await file.read()
        if not contents:
            raise ValueError("The uploaded file is empty")
        if len(contents) > MAX_DOCUMENT_BYTES:
            raise ValueError("File too large. Maximum size is 10 MB.")

        target_dir = booking_documents_dir()
        target_dir.mkdir(parents=True, exist_ok=True)

        # Stored under a generated name — never the client's, which could contain a path.
        extension = ALLOWED_CONTENT_TYPES[content_type]
        stored_name = f"{_uuid.uuid4()}{extension}"
        (target_dir / stored_name).write_bytes(contents)

        document = BookingDocument(
            booking_id=booking.id,
            guest_id=guest_id,
            document_type=document_type,
            file_path=str(target_dir / stored_name),
            file_name=os.path.basename(file.filename or stored_name),
            content_type=content_type,
            file_size_bytes=len(contents),
            notes=notes,
            created_by=uploaded_by,
        )
        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)

        logger.info(
            "booking_document_uploaded",
            booking_id=str(booking.id),
            document_id=str(document.id),
            document_type=document_type,
            uploaded_by=str(uploaded_by),
        )
        return document

    async def list_documents(self, booking_id) -> List[dict]:
        """Documents on a booking, with the traveller's name where one is attached."""
        rows = (
            await self.db.execute(
                select(BookingDocument, BookingGuest.full_name)
                .outerjoin(BookingGuest, BookingDocument.guest_id == BookingGuest.id)
                .where(
                    BookingDocument.booking_id == booking_id,
                    BookingDocument.is_deleted == False,
                )
                .order_by(BookingDocument.created_at)
            )
        ).all()

        return [
            {
                "id": doc.id,
                "booking_id": doc.booking_id,
                "guest_id": doc.guest_id,
                "guest_name": guest_name,
                "document_type": doc.document_type,
                "file_name": doc.file_name,
                "content_type": doc.content_type,
                "file_size_bytes": doc.file_size_bytes,
                "notes": doc.notes,
                "download_url": document_download_url(doc.booking_id, doc.id),
                "created_at": doc.created_at,
            }
            for doc, guest_name in rows
        ]

    async def get_document(self, booking_id, document_id) -> Optional[BookingDocument]:
        return (
            await self.db.execute(
                select(BookingDocument).where(
                    BookingDocument.id == document_id,
                    BookingDocument.booking_id == booking_id,
                    BookingDocument.is_deleted == False,
                )
            )
        ).scalar_one_or_none()

    def resolve_document_path(self, document: BookingDocument) -> Optional[Path]:
        """The file on disk, or None if it is gone.

        Rebuilt from the stored basename rather than trusting file_path wholesale, so a
        tampered row cannot read outside the upload directory.
        """
        safe_name = os.path.basename(str(document.file_path).replace("\\", "/"))
        if not safe_name or safe_name in (".", ".."):
            return None
        path = booking_documents_dir() / safe_name
        return path if path.is_file() else None

    async def delete_document(self, booking_id, document_id, deleted_by) -> bool:
        """Soft-delete a document. The file is left on disk for auditability."""
        document = await self.get_document(booking_id, document_id)
        if not document:
            return False
        document.soft_delete(deleted_by)
        await self.db.commit()
        logger.info(
            "booking_document_deleted",
            document_id=str(document_id),
            deleted_by=str(deleted_by),
        )
        return True
