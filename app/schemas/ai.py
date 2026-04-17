"""AI and chatbot schemas."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import BaseSchema


class AIChatRequest(BaseModel):
    """AI chat request."""

    message: str = Field(..., max_length=5000)
    session_id: Optional[str] = Field(default=None, max_length=100)
    context_type: Optional[str] = Field(default=None, max_length=50)
    context_data: Optional[dict] = None
    report_text: Optional[str] = Field(default=None, max_length=20000, description="Medical report text for context")


class DoctorSuggestion(BaseModel):
    """Doctor suggestion returned by AI."""

    id: str
    name: str
    specialty: Optional[str] = None
    specialties: List[str] = []
    hospital: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    rating: Optional[float] = None
    fee: Optional[float] = None
    experience_years: Optional[int] = None
    languages: List[str] = []
    photo_url: Optional[str] = None
    profile_url: str
    recommendation: Optional[str] = None


class AIChatResponse(BaseModel):
    """AI chat response."""

    response: str
    session_id: str
    conversation_id: Optional[str] = None
    doctor_suggestions: List[DoctorSuggestion] = []
    follow_up_questions: List[str] = []
    tokens_used: int = 0
    response_time_ms: int = 0


class AIReportAnalysisRequest(BaseModel):
    """Request to analyze a medical report."""

    report_text: str = Field(..., max_length=20000)
    session_id: Optional[str] = Field(default=None, max_length=100)


class RecommendedDoctor(BaseModel):
    """Doctor recommendation from report analysis."""

    id: str
    name: str
    specialty: Optional[str] = None
    specialties: List[str] = []
    hospital: Optional[str] = None
    city: Optional[str] = None
    rating: Optional[float] = None
    fee: Optional[float] = None
    experience_years: Optional[int] = None
    profile_url: str
    relevance_score: Optional[float] = None


class AIReportAnalysisResponse(BaseModel):
    """Response from medical report analysis."""

    report_analysis: dict
    recommended_doctors: List[RecommendedDoctor] = []
    total_matches: int = 0
    response_time_ms: int = 0


class AIFileAnalysisResponse(BaseModel):
    """Response from file (image/PDF) analysis."""

    file_type: str  # "image" or "pdf"
    filename: str
    report_analysis: dict
    recommended_doctors: List[RecommendedDoctor] = []
    total_matches: int = 0
    response_time_ms: int = 0


class AIConversationResponse(BaseSchema):
    """AI conversation response."""

    id: UUID
    session_id: str
    title: Optional[str] = None
    context_type: Optional[str] = None
    is_active: bool
    message_count: int
    total_tokens_used: int
    estimated_cost: float
    rating: Optional[int] = None
    feedback: Optional[str] = None
    created_at: datetime
    ended_at: Optional[datetime] = None


class AIConversationDetailResponse(AIConversationResponse):
    """AI conversation detail with messages."""

    messages: List["AILogResponse"] = []


class AILogResponse(BaseSchema):
    """AI log entry response."""

    id: UUID
    conversation_id: UUID
    user_message: str
    ai_response: str
    model_name: str
    model_version: Optional[str] = None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    response_time_ms: int
    cost: float
    detected_intent: Optional[str] = None
    detected_entities: Optional[dict] = None
    confidence_score: Optional[float] = None
    actions_triggered: Optional[dict] = None
    is_error: bool
    error_message: Optional[str] = None
    is_helpful: Optional[bool] = None
    feedback: Optional[str] = None
    created_at: datetime


class AIFeedbackRequest(BaseModel):
    """AI response feedback."""

    log_id: UUID
    is_helpful: bool
    feedback: Optional[str] = Field(default=None, max_length=1000)


class AIConversationRatingRequest(BaseModel):
    """AI conversation rating."""

    conversation_id: UUID
    rating: int = Field(..., ge=1, le=5)
    feedback: Optional[str] = Field(default=None, max_length=2000)


class AIStatsResponse(BaseModel):
    """AI usage statistics."""

    total_conversations: int
    total_messages: int
    total_tokens_used: int
    total_cost: float
    average_response_time_ms: float
    average_rating: Optional[float] = None
    intents_distribution: dict[str, int]
    conversations_by_context: dict[str, int]


class AISuggestion(BaseModel):
    """AI suggestion for user."""

    type: str  # question, action, info
    text: str
    data: Optional[dict] = None


class AIActionResult(BaseModel):
    """Result of an AI-triggered action."""

    action_type: str
    success: bool
    message: str
    data: Optional[dict] = None
