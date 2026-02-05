# Flora Medical - API CURL Examples

## 🏥 Hospital Search & Linking

### 1. Search for a Hospital
Use this to populate the autocomplete field when a doctor is searching for their hospital.

```bash
# Search by name (e.g. "Apollo")
curl -X GET "http://localhost:8000/api/v1/hospitals?search=Apollo" \
  -H "accept: application/json"

# Search by city
curl -X GET "http://localhost:8000/api/v1/hospitals?city=Delhi" \
  -H "accept: application/json"
```

**Response:**
```json
{
  "items": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "name": "Apollo Hospital",
      "slug": "apollo-hospital-delhi",
      "city": "New Delhi",
      "country": "India"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

---

### 2. Update Doctor Profile (Link Hospital)
Once the doctor selects a hospital from the search results, send the `hospital_id` in the update payload.

```bash
curl -X PUT "http://localhost:8000/api/v1/doctors/me" \
  -H "accept: application/json" \
  -H "Authorization: Bearer <your_access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "hospital_id": "123e4567-e89b-12d3-a456-426614174000",
    "consultation_fee": 1500,
    "years_of_experience": 12
  }'
```

**Response:**
```json
{
  "id": "doctor_uuid",
  "full_name": "Dr. Smith",
  "hospital_id": "123e4567-e89b-12d3-a456-426614174000",
  "hospital_name": "Apollo Hospital",
  "consultation_fee": 1500.0,
  "years_of_experience": 12
}
```

---

### 3. Get Hospital Details
To show the hospital's address card (as seen in the UI design).

```bash
curl -X GET "http://localhost:8000/api/v1/hospitals/123e4567-e89b-12d3-a456-426614174000" \
  -H "accept: application/json"
```

**Response:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Apollo Hospital",
  "address_line1": "Sarita Vihar, Mathura Road",
  "city": "New Delhi",
  "country": "India",
  "facilities": {
    "emergency": true,
    "parking": true
  }
}
```
