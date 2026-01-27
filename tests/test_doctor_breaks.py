"""Test doctor availability with break times."""

import pytest
from httpx import AsyncClient
from datetime import time, date, datetime
from uuid import uuid4

from app.models.user import User
from app.core.security import get_password_hash
from app.utils.enums import UserRole

@pytest.mark.asyncio
async def test_doctor_availability_breaks(client: AsyncClient, db_session):
    """Test setting doctor availability with break times."""
    # Create doctor user
    doctor_email = f"doctor_{uuid4()}@example.com"
    user_data = {
        "email": doctor_email,
        "password": "Test@123456",
        "full_name": "Test Doctor",
        "role": UserRole.DOCTOR.value,
        "phone": "1234567890"
    }
    
    # Register user
    response = await client.post("/api/v1/auth/register", json={
        "email": user_data["email"],
        "password": user_data["password"],
        "confirm_password": user_data["password"],
        "full_name": user_data["full_name"],
        "role": "doctor"
    })
    assert response.status_code == 200
    user_id = response.json()["id"]
    
    # Login to get token
    response = await client.post("/api/v1/auth/login", json={
        "email": user_data["email"],
        "password": user_data["password"]
    })
    token = response.json()["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create doctor profile
    response = await client.post("/api/v1/doctors", json={
        "title": "Dr.",
        "license_number": "DOC123",
        "consultation_fee": 100.0
    }, headers=headers)
    assert response.status_code == 200
    doctor_id = response.json()["id"]
    
    # Set availability with break
    availability_data = [
        {
            "day_of_week": 0,  # Monday
            "start_time": "09:00:00",
            "end_time": "17:00:00",
            "break_start_time": "13:00:00",
            "break_end_time": "14:00:00",
            "slot_duration_minutes": 30
        }
    ]
    
    response = await client.put(
        "/api/v1/doctors/availability",
        json=availability_data,
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["break_start_time"] == "13:00:00"
    assert data[0]["break_end_time"] == "14:00:00"
