"""Medical report service.

Handles CRUD + file upload/download for MedicalReport records.
File storage mirrors DocumentService: uploads/<patient_id>/medical_reports/<report_id>.<ext>
"""

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.medical_report import MedicalReport
from app.schemas.medical_report import MedicalReportCreate, MedicalReportUpdate
from app.utils.helpers import generate_reference_id

logger = get_logger(__name__)

# 20 MB hard limit for medical reports (larger than generic docs for imaging)
_MAX_SIZE_BYTES = 20 * 1024 * 1024

_ALLOWED_MIME = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/dicom",
    "application/dicom",
    "text/plain",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class MedicalReportService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.upload_dir = Path(settings.UPLOAD_DIR) / "medical_reports"
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    async def list_reports(
        self,
        patient_id: UUID,
        report_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[MedicalReport], int]:
        query = select(MedicalReport).where(
            MedicalReport.patient_id == patient_id,
            MedicalReport.is_deleted == False,
        )
        if report_type:
            query = query.where(MedicalReport.report_type == report_type)

        total = (
            await self.db.execute(select(func.count()).select_from(query.subquery()))
        ).scalar() or 0

        query = (
            query.order_by(MedicalReport.report_date.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = await self.db.execute(query)
        return list(rows.scalars().all()), total

    # ------------------------------------------------------------------
    # Get single
    # ------------------------------------------------------------------

    async def get_report(self, report_id: UUID, patient_id: UUID) -> Optional[MedicalReport]:
        result = await self.db.execute(
            select(MedicalReport).where(
                MedicalReport.id == report_id,
                MedicalReport.patient_id == patient_id,
                MedicalReport.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Create (no file — structured data only)
    # ------------------------------------------------------------------

    async def create_report(
        self,
        patient_id: UUID,
        data: MedicalReportCreate,
        created_by: UUID,
    ) -> MedicalReport:
        report = MedicalReport(
            patient_id=patient_id,
            doctor_id=data.doctor_id,
            consultation_id=data.consultation_id,
            title=data.title,
            report_type=data.report_type,
            description=data.description,
            report_date=data.report_date,
            facility_name=data.facility_name,
            facility_address=data.facility_address,
            performing_doctor=data.performing_doctor,
            content=data.content,
            interpretation=data.interpretation,
            is_abnormal=data.is_abnormal,
            requires_followup=data.requires_followup,
            is_private=data.is_private,
            reference_number=generate_reference_id("RPT"),
            created_by=created_by,
        )
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        logger.info("medical_report_created", report_id=str(report.id), type=data.report_type)
        return report

    # ------------------------------------------------------------------
    # Upload with file
    # ------------------------------------------------------------------

    async def upload_report(
        self,
        patient_id: UUID,
        file: UploadFile,
        title: str,
        report_type: str,
        report_date: datetime,
        description: Optional[str] = None,
        facility_name: Optional[str] = None,
        performing_doctor: Optional[str] = None,
        interpretation: Optional[str] = None,
        is_abnormal: bool = False,
        requires_followup: bool = False,
        is_private: bool = False,
        consultation_id: Optional[UUID] = None,
        doctor_id: Optional[UUID] = None,
        created_by: Optional[UUID] = None,
    ) -> MedicalReport:
        # Validate mime type
        if file.content_type and file.content_type not in _ALLOWED_MIME:
            raise ValueError(
                f"File type '{file.content_type}' is not allowed. "
                f"Accepted: PDF, JPG, PNG, DICOM, DOCX, TXT"
            )

        # Read and size-check
        content = await file.read()
        if len(content) > _MAX_SIZE_BYTES:
            raise ValueError(f"File exceeds the 20 MB limit ({len(content) // 1024 // 1024} MB)")

        report_id = uuid.uuid4()
        ext = Path(file.filename or "file").suffix or ".bin"
        patient_dir = self.upload_dir / str(patient_id)
        patient_dir.mkdir(parents=True, exist_ok=True)
        file_path = patient_dir / f"{report_id}{ext}"

        file_path.write_bytes(content)
        logger.info("medical_report_file_saved", path=str(file_path), size=len(content))

        report = MedicalReport(
            id=report_id,
            patient_id=patient_id,
            doctor_id=doctor_id,
            consultation_id=consultation_id,
            title=title,
            report_type=report_type,
            description=description,
            report_date=report_date,
            facility_name=facility_name,
            performing_doctor=performing_doctor,
            interpretation=interpretation,
            is_abnormal=is_abnormal,
            requires_followup=requires_followup,
            is_private=is_private,
            file_url=str(file_path),
            file_name=file.filename,
            file_type=file.content_type,
            file_size_bytes=len(content),
            reference_number=generate_reference_id("RPT"),
            created_by=created_by,
        )
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        logger.info("medical_report_uploaded", report_id=str(report_id), type=report_type)
        return report

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update_report(
        self,
        report_id: UUID,
        patient_id: UUID,
        data: MedicalReportUpdate,
        updated_by: UUID,
    ) -> MedicalReport:
        report = await self.get_report(report_id, patient_id)
        if not report:
            raise ValueError("Report not found")

        for field, value in data.model_dump(exclude_none=True).items():
            setattr(report, field, value)
        report.updated_by = updated_by

        await self.db.commit()
        await self.db.refresh(report)
        return report

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete_report(
        self,
        report_id: UUID,
        patient_id: UUID,
        deleted_by: UUID,
    ) -> None:
        report = await self.get_report(report_id, patient_id)
        if not report:
            raise ValueError("Report not found")

        # Remove file from disk
        if report.file_url and os.path.exists(report.file_url):
            try:
                os.remove(report.file_url)
                logger.info("medical_report_file_deleted", path=report.file_url)
            except Exception as exc:
                logger.error("medical_report_file_deletion_failed", error=str(exc))

        report.is_deleted = True
        report.deleted_at = datetime.now(timezone.utc)
        report.deleted_by = deleted_by
        await self.db.commit()
        logger.info("medical_report_deleted", report_id=str(report_id))

    # ------------------------------------------------------------------
    # Get file path for download
    # ------------------------------------------------------------------

    async def get_file_path(self, report_id: UUID, patient_id: UUID) -> Optional[str]:
        report = await self.get_report(report_id, patient_id)
        if not report or not report.file_url:
            return None
        if not os.path.exists(report.file_url):
            return None
        return report.file_url
