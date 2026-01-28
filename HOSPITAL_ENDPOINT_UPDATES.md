# Doctor's Hospital Information Endpoint Updates

## Overview
Updated the doctor's hospital information endpoints to include `hospital_id` and `doctor_id` in the request body. The system can now manage hospital records by linking to existing hospitals or creating new ones based on the provided IDs.

## Changes Made

### 1. Schema Updates (`app/schemas/doctor.py`)

#### DoctorHospitalCreate
- **Added**: `doctor_id` (UUID, required) - The doctor's ID
- **Added**: `hospital_id` (UUID, optional) - Link to existing hospital instead of creating new one
- **Updated**: `name` field is now optional (required only if `hospital_id` not provided)

```python
class DoctorHospitalCreate(BaseModel):
    doctor_id: UUID = Field(..., description="The doctor's ID")
    hospital_id: Optional[UUID] = Field(default=None, description="If provided, links to existing hospital instead of creating new one")
    name: Optional[str] = Field(default=None, max_length=255, description="Required if hospital_id is not provided")
    # ... other fields
```

#### DoctorHospitalUpdate
- **Added**: `doctor_id` (UUID, required) - The doctor's ID
- **Added**: `hospital_id` (UUID, optional) - Can change hospital association

```python
class DoctorHospitalUpdate(BaseModel):
    doctor_id: UUID = Field(..., description="The doctor's ID")
    hospital_id: Optional[UUID] = Field(default=None, description="Hospital ID to link to (optional if already linked)")
    # ... other fields
```

### 2. API Endpoints Updates (`app/api/v1/doctors.py`)

#### New Endpoints Added

##### GET `/{doctor_id}/hospital`
- Get hospital information for a specific doctor by doctor_id
- No authentication required
- Returns: `DoctorHospitalResponse`

##### POST `/{doctor_id}/hospital`
- Add hospital information to a doctor's profile by doctor_id
- Request body: `DoctorHospitalCreate`
- Can link to existing hospital or create new one
- Returns: `DoctorHospitalResponse`

##### PUT `/{doctor_id}/hospital`
- Update a doctor's hospital information by doctor_id
- Request body: `DoctorHospitalUpdate`
- Can change hospital association or update hospital details
- Returns: `DoctorHospitalResponse`

##### DELETE `/{doctor_id}/hospital`
- Remove hospital from a doctor's profile by doctor_id
- Query param: `delete_hospital` (bool, optional) - If true, also soft-delete the hospital record
- Returns: 204 No Content

#### Preserved Endpoints
- `GET /me/hospital` - Get current doctor's hospital (uses auth token)
- `POST /me/hospital` - Add hospital to current doctor (uses auth token)
- `PUT /me/hospital` - Update current doctor's hospital (uses auth token)
- `DELETE /me/hospital` - Remove hospital from current doctor (uses auth token)

### 3. Service Updates (`app/services/doctor_service.py`)

#### Updated `add_doctor_hospital()` Method
Now supports two scenarios:
1. **Link to existing hospital**: If `hospital_id` is provided in request
   - Validates hospital exists
   - Links it to the doctor
   - Returns hospital details

2. **Create new hospital**: If `hospital_id` is not provided but `name` is provided
   - Creates a new hospital record
   - Links it to the doctor
   - Returns hospital details

```python
async def add_doctor_hospital(self, doctor: Doctor, data, created_by: Optional[UUID] = None):
    # Case 1: Link existing hospital by hospital_id
    if data.hospital_id:
        # Validate and link hospital
        
    # Case 2: Create new hospital
    if data.name:
        # Create new hospital and link
```

#### Updated `update_doctor_hospital()` Method
Now supports:
1. **Change hospital association**: If different `hospital_id` provided
   - Validates new hospital exists
   - Updates doctor's hospital_id
   - Returns new hospital details

2. **Update current hospital info**: Without changing hospital_id
   - Updates fields like name, description, contact info, etc.
   - Preserves current association
   - Returns updated hospital details

```python
async def update_doctor_hospital(self, doctor: Doctor, data, updated_by: Optional[UUID] = None):
    # Case 1: Change to different hospital
    if data.hospital_id and data.hospital_id != doctor.hospital_id:
        # Change association
        
    # Case 2: Update current hospital's information
    else:
        # Update fields
```

## API Usage Examples

### Create Hospital for Doctor (New Hospital)
```json
POST /api/v1/doctors/{doctor_id}/hospital
{
  "doctor_id": "uuid-here",
  "name": "City General Hospital",
  "description": "A leading hospital...",
  "address_line1": "123 Main St",
  "city": "New York",
  "country": "USA"
}
```

### Link Doctor to Existing Hospital
```json
POST /api/v1/doctors/{doctor_id}/hospital
{
  "doctor_id": "uuid-here",
  "hospital_id": "existing-hospital-uuid"
}
```

### Change Doctor's Hospital
```json
PUT /api/v1/doctors/{doctor_id}/hospital
{
  "doctor_id": "uuid-here",
  "hospital_id": "new-hospital-uuid"
}
```

### Update Hospital Information
```json
PUT /api/v1/doctors/{doctor_id}/hospital
{
  "doctor_id": "uuid-here",
  "name": "Updated Hospital Name",
  "description": "Updated description"
}
```

### Remove Hospital Association
```
DELETE /api/v1/doctors/{doctor_id}/hospital?delete_hospital=false
```

## Backward Compatibility
- All existing `/me/hospital` endpoints remain unchanged
- Existing endpoints still use current user's token for doctor identification
- New endpoints provide explicit doctor_id parameter for admin operations

## Error Handling
- Returns 404 if doctor or hospital not found
- Returns 400 with descriptive message for validation errors:
  - "Doctor already has a hospital" when creating
  - "Either hospital_id or name must be provided"
  - "Hospital with ID {id} not found" when linking

## Validation Rules
- **Create (POST)**: Either `hospital_id` OR `name` must be provided
- **Update (PUT)**: Doctor must have existing hospital or provide new `hospital_id`
- **Delete (DELETE)**: Doctor must have existing hospital to remove
