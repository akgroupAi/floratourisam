"""Patient medical records API endpoints."""

from typing import Annotated, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentUser, DatabaseSession, get_current_patient
from app.models.patient import Patient
from app.schemas.common import MessageResponse
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
from app.services.medical_record_service import (
    AllergyService,
    MedicalConditionService,
    MedicationService,
)

router = APIRouter()


# Medical Conditions Endpoints
@router.get("/me/medical-conditions", response_model=List[MedicalConditionResponse])
async def list_medical_conditions(
    current_user: CurrentUser,
    patient: Annotated[Patient, Depends(get_current_patient)],
    db: DatabaseSession,
):
    """List all medical conditions for the current patient."""
    service = MedicalConditionService(db)
    return await service.get_all(patient.id)


@router.post(
    "/me/medical-conditions",
    response_model=MedicalConditionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_medical_condition(
    data: MedicalConditionCreate,
    current_user: CurrentUser,
    patient: Annotated[Patient, Depends(get_current_patient)],
    db: DatabaseSession,
):
    """Create a new medical condition."""
    service = MedicalConditionService(db)
    return await service.create(patient.id, data)


@router.get("/me/medical-conditions/{condition_id}", response_model=MedicalConditionResponse)
async def get_medical_condition(
    condition_id: UUID,
    current_user: CurrentUser,
    patient: Annotated[Patient, Depends(get_current_patient)],
    db: DatabaseSession,
):
    """Get a specific medical condition."""
    service = MedicalConditionService(db)
    condition = await service.get_by_id(condition_id, patient.id)

    if not condition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medical condition not found",
        )

    return condition


@router.put("/me/medical-conditions/{condition_id}", response_model=MedicalConditionResponse)
async def update_medical_condition(
    condition_id: UUID,
    data: MedicalConditionUpdate,
    current_user: CurrentUser,
    patient: Annotated[Patient, Depends(get_current_patient)],
    db: DatabaseSession,
):
    """Update a medical condition."""
    service = MedicalConditionService(db)
    condition = await service.update(condition_id, patient.id, data)

    if not condition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medical condition not found",
        )

    return condition


@router.delete("/me/medical-conditions/{condition_id}", response_model=MessageResponse)
async def delete_medical_condition(
    condition_id: UUID,
    current_user: CurrentUser,
    patient: Annotated[Patient, Depends(get_current_patient)],
    db: DatabaseSession,
):
    """Delete a medical condition."""
    service = MedicalConditionService(db)
    success = await service.delete(condition_id, patient.id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medical condition not found",
        )

    return MessageResponse(message="Medical condition deleted successfully")


# Allergies Endpoints
@router.get("/me/allergies", response_model=List[AllergyResponse])
async def list_allergies(
    current_user: CurrentUser,
    patient: Annotated[Patient, Depends(get_current_patient)],
    db: DatabaseSession,
):
    """List all allergies for the current patient."""
    service = AllergyService(db)
    return await service.get_all(patient.id)


@router.post(
    "/me/allergies",
    response_model=AllergyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_allergy(
    data: AllergyCreate,
    current_user: CurrentUser,
    patient: Annotated[Patient, Depends(get_current_patient)],
    db: DatabaseSession,
):
    """Create a new allergy."""
    service = AllergyService(db)
    return await service.create(patient.id, data)


@router.get("/me/allergies/{allergy_id}", response_model=AllergyResponse)
async def get_allergy(
    allergy_id: UUID,
    current_user: CurrentUser,
    patient: Annotated[Patient, Depends(get_current_patient)],
    db: DatabaseSession,
):
    """Get a specific allergy."""
    service = AllergyService(db)
    allergy = await service.get_by_id(allergy_id, patient.id)

    if not allergy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Allergy not found",
        )

    return allergy


@router.put("/me/allergies/{allergy_id}", response_model=AllergyResponse)
async def update_allergy(
    allergy_id: UUID,
    data: AllergyUpdate,
    current_user: CurrentUser,
    patient: Annotated[Patient, Depends(get_current_patient)],
    db: DatabaseSession,
):
    """Update an allergy."""
    service = AllergyService(db)
    allergy = await service.update(allergy_id, patient.id, data)

    if not allergy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Allergy not found",
        )

    return allergy


@router.delete("/me/allergies/{allergy_id}", response_model=MessageResponse)
async def delete_allergy(
    allergy_id: UUID,
    current_user: CurrentUser,
    patient: Annotated[Patient, Depends(get_current_patient)],
    db: DatabaseSession,
):
    """Delete an allergy."""
    service = AllergyService(db)
    success = await service.delete(allergy_id, patient.id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Allergy not found",
        )

    return MessageResponse(message="Allergy deleted successfully")


# Medications Endpoints
@router.get("/me/medications", response_model=List[MedicationResponse])
async def list_medications(
    current_user: CurrentUser,
    patient: Annotated[Patient, Depends(get_current_patient)],
    db: DatabaseSession,
    active_only: bool = False,
):
    """List all medications for the current patient."""
    service = MedicationService(db)
    return await service.get_all(patient.id, active_only=active_only)


@router.get("/me/medications/active", response_model=List[MedicationResponse])
async def list_active_medications(
    current_user: CurrentUser,
    patient: Annotated[Patient, Depends(get_current_patient)],
    db: DatabaseSession,
):
    """List only active medications for the current patient."""
    service = MedicationService(db)
    return await service.get_all(patient.id, active_only=True)


@router.post(
    "/me/medications",
    response_model=MedicationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_medication(
    data: MedicationCreate,
    current_user: CurrentUser,
    patient: Annotated[Patient, Depends(get_current_patient)],
    db: DatabaseSession,
):
    """Create a new medication."""
    service = MedicationService(db)
    return await service.create(patient.id, data)


@router.get("/me/medications/{medication_id}", response_model=MedicationResponse)
async def get_medication(
    medication_id: UUID,
    current_user: CurrentUser,
    patient: Annotated[Patient, Depends(get_current_patient)],
    db: DatabaseSession,
):
    """Get a specific medication."""
    service = MedicationService(db)
    medication = await service.get_by_id(medication_id, patient.id)

    if not medication:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medication not found",
        )

    return medication


@router.put("/me/medications/{medication_id}", response_model=MedicationResponse)
async def update_medication(
    medication_id: UUID,
    data: MedicationUpdate,
    current_user: CurrentUser,
    patient: Annotated[Patient, Depends(get_current_patient)],
    db: DatabaseSession,
):
    """Update a medication."""
    service = MedicationService(db)
    medication = await service.update(medication_id, patient.id, data)

    if not medication:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medication not found",
        )

    return medication


@router.delete("/me/medications/{medication_id}", response_model=MessageResponse)
async def delete_medication(
    medication_id: UUID,
    current_user: CurrentUser,
    patient: Annotated[Patient, Depends(get_current_patient)],
    db: DatabaseSession,
):
    """Delete a medication."""
    service = MedicationService(db)
    success = await service.delete(medication_id, patient.id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medication not found",
        )

    return MessageResponse(message="Medication deleted successfully")
