"""Patient dashboard summary schema."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel

class PatientDashboardSummary(BaseModel):
    total_documents: int
    recent_documents: int
    total_appointments: int
    upcoming_appointments: int
    next_appointment_at: Optional[datetime]
    total_messages: int
    unread_messages: int
    # Add more fields as needed for progress, tasks, etc.
