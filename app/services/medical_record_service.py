"""Medical record service for managing patient health information."""

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.medical_record import Allergy, MedicalCondition, Medication
from app.schemas.medical_record import (
    AllergyCreate,
    AllergyResponse,
    AllergyUpdate,
    MedicalConditionCreate,
    MedicalConditionResponse,
    MedicalConditionUpdate,
    MedicationCreate,
    MedicationResponse,
    MedicationUpdate,
)

logger = get_logger(__name__)


class MedicalConditionService:
    """Service for managing patient medical conditions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self, patient_id: uuid.UUID) -> List[MedicalConditionResponse]:
        """Get all medical conditions for a patient."""
        result = await self.db.execute(
            select(MedicalCondition)
            .where(
                MedicalCondition.patient_id == patient_id,
                MedicalCondition.is_deleted == False,
            )
            .order_by(MedicalCondition.created_at.desc())
        )
        conditions = result.scalars().all()

        return [
            MedicalConditionResponse(
                id=c.id,
                patient_id=c.patient_id,
                condition_name=c.condition_name,
                diagnosed_date=c.diagnosed_date,
                status=c.status,
                severity=c.severity,
                notes=c.notes,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in conditions
        ]

    async def get_by_id(
        self, condition_id: uuid.UUID, patient_id: uuid.UUID
    ) -> Optional[MedicalConditionResponse]:
        """Get a specific medical condition."""
        result = await self.db.execute(
            select(MedicalCondition).where(
                MedicalCondition.id == condition_id,
                MedicalCondition.patient_id == patient_id,
                MedicalCondition.is_deleted == False,
            )
        )
        condition = result.scalar_one_or_none()

        if not condition:
            return None

        return MedicalConditionResponse(
            id=condition.id,
            patient_id=condition.patient_id,
            condition_name=condition.condition_name,
            diagnosed_date=condition.diagnosed_date,
            status=condition.status,
            severity=condition.severity,
            notes=condition.notes,
            created_at=condition.created_at,
            updated_at=condition.updated_at,
        )

    async def create(
        self, patient_id: uuid.UUID, data: MedicalConditionCreate
    ) -> MedicalConditionResponse:
        """Create a new medical condition."""
        condition = MedicalCondition(
            patient_id=patient_id,
            condition_name=data.condition_name,
            diagnosed_date=data.diagnosed_date,
            status=data.status.value,
            severity=data.severity.value if data.severity else None,
            notes=data.notes,
        )

        self.db.add(condition)
        await self.db.commit()
        await self.db.refresh(condition)

        logger.info(
            "medical_condition_created",
            condition_id=str(condition.id),
            patient_id=str(patient_id),
        )

        return MedicalConditionResponse(
            id=condition.id,
            patient_id=condition.patient_id,
            condition_name=condition.condition_name,
            diagnosed_date=condition.diagnosed_date,
            status=condition.status,
            severity=condition.severity,
            notes=condition.notes,
            created_at=condition.created_at,
            updated_at=condition.updated_at,
        )

    async def update(
        self, condition_id: uuid.UUID, patient_id: uuid.UUID, data: MedicalConditionUpdate
    ) -> Optional[MedicalConditionResponse]:
        """Update a medical condition."""
        result = await self.db.execute(
            select(MedicalCondition).where(
                MedicalCondition.id == condition_id,
                MedicalCondition.patient_id == patient_id,
                MedicalCondition.is_deleted == False,
            )
        )
        condition = result.scalar_one_or_none()

        if not condition:
            return None

        # Update fields
        if data.condition_name is not None:
            condition.condition_name = data.condition_name
        if data.diagnosed_date is not None:
            condition.diagnosed_date = data.diagnosed_date
        if data.status is not None:
            condition.status = data.status.value
        if data.severity is not None:
            condition.severity = data.severity.value
        if data.notes is not None:
            condition.notes = data.notes

        await self.db.commit()
        await self.db.refresh(condition)

        logger.info("medical_condition_updated", condition_id=str(condition_id))

        return MedicalConditionResponse(
            id=condition.id,
            patient_id=condition.patient_id,
            condition_name=condition.condition_name,
            diagnosed_date=condition.diagnosed_date,
            status=condition.status,
            severity=condition.severity,
            notes=condition.notes,
            created_at=condition.created_at,
            updated_at=condition.updated_at,
        )

    async def delete(self, condition_id: uuid.UUID, patient_id: uuid.UUID) -> bool:
        """Delete a medical condition."""
        result = await self.db.execute(
            select(MedicalCondition).where(
                MedicalCondition.id == condition_id,
                MedicalCondition.patient_id == patient_id,
                MedicalCondition.is_deleted == False,
            )
        )
        condition = result.scalar_one_or_none()

        if not condition:
            return False

        condition.soft_delete()
        await self.db.commit()

        logger.info("medical_condition_deleted", condition_id=str(condition_id))

        return True


class AllergyService:
    """Service for managing patient allergies."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self, patient_id: uuid.UUID) -> List[AllergyResponse]:
        """Get all allergies for a patient."""
        result = await self.db.execute(
            select(Allergy)
            .where(
                Allergy.patient_id == patient_id,
                Allergy.is_deleted == False,
            )
            .order_by(Allergy.created_at.desc())
        )
        allergies = result.scalars().all()

        return [
            AllergyResponse(
                id=a.id,
                patient_id=a.patient_id,
                allergen=a.allergen,
                reaction=a.reaction,
                severity=a.severity,
                diagnosed_date=a.diagnosed_date,
                notes=a.notes,
                created_at=a.created_at,
                updated_at=a.updated_at,
            )
            for a in allergies
        ]

    async def get_by_id(
        self, allergy_id: uuid.UUID, patient_id: uuid.UUID
    ) -> Optional[AllergyResponse]:
        """Get a specific allergy."""
        result = await self.db.execute(
            select(Allergy).where(
                Allergy.id == allergy_id,
                Allergy.patient_id == patient_id,
                Allergy.is_deleted == False,
            )
        )
        allergy = result.scalar_one_or_none()

        if not allergy:
            return None

        return AllergyResponse(
            id=allergy.id,
            patient_id=allergy.patient_id,
            allergen=allergy.allergen,
            reaction=allergy.reaction,
            severity=allergy.severity,
            diagnosed_date=allergy.diagnosed_date,
            notes=allergy.notes,
            created_at=allergy.created_at,
            updated_at=allergy.updated_at,
        )

    async def create(
        self, patient_id: uuid.UUID, data: AllergyCreate
    ) -> AllergyResponse:
        """Create a new allergy."""
        allergy = Allergy(
            patient_id=patient_id,
            allergen=data.allergen,
            reaction=data.reaction,
            severity=data.severity.value,
            diagnosed_date=data.diagnosed_date,
            notes=data.notes,
        )

        self.db.add(allergy)
        await self.db.commit()
        await self.db.refresh(allergy)

        logger.info("allergy_created", allergy_id=str(allergy.id), patient_id=str(patient_id))

        return AllergyResponse(
            id=allergy.id,
            patient_id=allergy.patient_id,
            allergen=allergy.allergen,
            reaction=allergy.reaction,
            severity=allergy.severity,
            diagnosed_date=allergy.diagnosed_date,
            notes=allergy.notes,
            created_at=allergy.created_at,
            updated_at=allergy.updated_at,
        )

    async def update(
        self, allergy_id: uuid.UUID, patient_id: uuid.UUID, data: AllergyUpdate
    ) -> Optional[AllergyResponse]:
        """Update an allergy."""
        result = await self.db.execute(
            select(Allergy).where(
                Allergy.id == allergy_id,
                Allergy.patient_id == patient_id,
                Allergy.is_deleted == False,
            )
        )
        allergy = result.scalar_one_or_none()

        if not allergy:
            return None

        # Update fields
        if data.allergen is not None:
            allergy.allergen = data.allergen
        if data.reaction is not None:
            allergy.reaction = data.reaction
        if data.severity is not None:
            allergy.severity = data.severity.value
        if data.diagnosed_date is not None:
            allergy.diagnosed_date = data.diagnosed_date
        if data.notes is not None:
            allergy.notes = data.notes

        await self.db.commit()
        await self.db.refresh(allergy)

        logger.info("allergy_updated", allergy_id=str(allergy_id))

        return AllergyResponse(
            id=allergy.id,
            patient_id=allergy.patient_id,
            allergen=allergy.allergen,
            reaction=allergy.reaction,
            severity=allergy.severity,
            diagnosed_date=allergy.diagnosed_date,
            notes=allergy.notes,
            created_at=allergy.created_at,
            updated_at=allergy.updated_at,
        )

    async def delete(self, allergy_id: uuid.UUID, patient_id: uuid.UUID) -> bool:
        """Delete an allergy."""
        result = await self.db.execute(
            select(Allergy).where(
                Allergy.id == allergy_id,
                Allergy.patient_id == patient_id,
                Allergy.is_deleted == False,
            )
        )
        allergy = result.scalar_one_or_none()

        if not allergy:
            return False

        allergy.soft_delete()
        await self.db.commit()

        logger.info("allergy_deleted", allergy_id=str(allergy_id))

        return True


class MedicationService:
    """Service for managing patient medications."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(
        self, patient_id: uuid.UUID, active_only: bool = False
    ) -> List[MedicationResponse]:
        """Get all medications for a patient."""
        query = select(Medication).where(
            Medication.patient_id == patient_id,
            Medication.is_deleted == False,
        )

        if active_only:
            query = query.where(Medication.is_active == True)

        query = query.order_by(Medication.created_at.desc())

        result = await self.db.execute(query)
        medications = result.scalars().all()

        return [
            MedicationResponse(
                id=m.id,
                patient_id=m.patient_id,
                medication_name=m.medication_name,
                dosage=m.dosage,
                frequency=m.frequency,
                duration=m.duration,
                start_date=m.start_date,
                end_date=m.end_date,
                prescribing_doctor=m.prescribing_doctor,
                notes=m.notes,
                is_active=m.is_active,
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
            for m in medications
        ]

    async def get_by_id(
        self, medication_id: uuid.UUID, patient_id: uuid.UUID
    ) -> Optional[MedicationResponse]:
        """Get a specific medication."""
        result = await self.db.execute(
            select(Medication).where(
                Medication.id == medication_id,
                Medication.patient_id == patient_id,
                Medication.is_deleted == False,
            )
        )
        medication = result.scalar_one_or_none()

        if not medication:
            return None

        return MedicationResponse(
            id=medication.id,
            patient_id=medication.patient_id,
            medication_name=medication.medication_name,
            dosage=medication.dosage,
            frequency=medication.frequency,
            duration=medication.duration,
            start_date=medication.start_date,
            end_date=medication.end_date,
            prescribing_doctor=medication.prescribing_doctor,
            notes=medication.notes,
            is_active=medication.is_active,
            created_at=medication.created_at,
            updated_at=medication.updated_at,
        )

    async def create(
        self, patient_id: uuid.UUID, data: MedicationCreate
    ) -> MedicationResponse:
        """Create a new medication."""
        medication = Medication(
            patient_id=patient_id,
            medication_name=data.medication_name,
            dosage=data.dosage,
            frequency=data.frequency,
            duration=data.duration,
            start_date=data.start_date,
            end_date=data.end_date,
            prescribing_doctor=data.prescribing_doctor,
            notes=data.notes,
            is_active=data.is_active,
        )

        self.db.add(medication)
        await self.db.commit()
        await self.db.refresh(medication)

        logger.info(
            "medication_created", medication_id=str(medication.id), patient_id=str(patient_id)
        )

        return MedicationResponse(
            id=medication.id,
            patient_id=medication.patient_id,
            medication_name=medication.medication_name,
            dosage=medication.dosage,
            frequency=medication.frequency,
            duration=medication.duration,
            start_date=medication.start_date,
            end_date=medication.end_date,
            prescribing_doctor=medication.prescribing_doctor,
            notes=medication.notes,
            is_active=medication.is_active,
            created_at=medication.created_at,
            updated_at=medication.updated_at,
        )

    async def update(
        self, medication_id: uuid.UUID, patient_id: uuid.UUID, data: MedicationUpdate
    ) -> Optional[MedicationResponse]:
        """Update a medication."""
        result = await self.db.execute(
            select(Medication).where(
                Medication.id == medication_id,
                Medication.patient_id == patient_id,
                Medication.is_deleted == False,
            )
        )
        medication = result.scalar_one_or_none()

        if not medication:
            return None

        # Update fields
        if data.medication_name is not None:
            medication.medication_name = data.medication_name
        if data.dosage is not None:
            medication.dosage = data.dosage
        if data.frequency is not None:
            medication.frequency = data.frequency
        if data.duration is not None:
            medication.duration = data.duration
        if data.start_date is not None:
            medication.start_date = data.start_date
        if data.end_date is not None:
            medication.end_date = data.end_date
        if data.prescribing_doctor is not None:
            medication.prescribing_doctor = data.prescribing_doctor
        if data.notes is not None:
            medication.notes = data.notes
        if data.is_active is not None:
            medication.is_active = data.is_active

        await self.db.commit()
        await self.db.refresh(medication)

        logger.info("medication_updated", medication_id=str(medication_id))

        return MedicationResponse(
            id=medication.id,
            patient_id=medication.patient_id,
            medication_name=medication.medication_name,
            dosage=medication.dosage,
            frequency=medication.frequency,
            duration=medication.duration,
            start_date=medication.start_date,
            end_date=medication.end_date,
            prescribing_doctor=medication.prescribing_doctor,
            notes=medication.notes,
            is_active=medication.is_active,
            created_at=medication.created_at,
            updated_at=medication.updated_at,
        )

    async def delete(self, medication_id: uuid.UUID, patient_id: uuid.UUID) -> bool:
        """Delete a medication."""
        result = await self.db.execute(
            select(Medication).where(
                Medication.id == medication_id,
                Medication.patient_id == patient_id,
                Medication.is_deleted == False,
            )
        )
        medication = result.scalar_one_or_none()

        if not medication:
            return False

        medication.soft_delete()
        await self.db.commit()

        logger.info("medication_deleted", medication_id=str(medication_id))

        return True
