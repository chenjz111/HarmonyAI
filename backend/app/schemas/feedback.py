"""Pydantic schemas for User Feedback — Agent ⑤.

Strictly mirrors agent-schemas.md Agent ⑤ 用户反馈Agent output.
"""
from __future__ import annotations
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class SubjectiveFeedback(BaseModel):
    overall_satisfaction: int = Field(..., ge=1, le=5)
    emotion_match: int = Field(..., ge=1, le=5)
    relaxation_feeling: Optional[int] = Field(None, ge=1, le=5)
    sleep_improvement: Optional[int] = Field(None, ge=1, le=5)
    stress_reduction: Optional[int] = Field(None, ge=1, le=5)
    text_feedback: Optional[str] = None


class BehavioralData(BaseModel):
    completion_rate: float = Field(..., ge=0, le=1)
    replay_count: int = 0
    pause_count: int = 0
    skip_forward_count: int = 0
    listen_session: Optional[str] = None
    average_volume: Optional[float] = Field(None, ge=0, le=1)


class WearableData(BaseModel):
    heart_rate: Optional[dict] = None
    hrv: Optional[dict] = None
    sleep_duration: Optional[dict] = None
    sleep_score: Optional[dict] = None
    respiration: Optional[dict] = None


class FeedbackDecision(BaseModel):
    action: str = Field(..., description="continue / adjust / rediag")
    action_detail: str
    next_step: str
    adjustments: Optional[dict] = None


class PreferredInstrument(BaseModel):
    id: str
    name: str
    score: float
    occurrences: int


class PreferredBpmRange(BaseModel):
    min: int
    max: int


class EffectiveSyndromePrescription(BaseModel):
    syndrome: str
    effective_tone_ids: list[str]
    effectiveness_score: float


class UserProfileUpdate(BaseModel):
    preferred_instruments: list[PreferredInstrument] = []
    preferred_bpm_range: Optional[PreferredBpmRange] = None
    preferred_session: Optional[str] = None
    effective_syndrome_prescription: Optional[EffectiveSyndromePrescription] = None


# ---------------------------------------------------------------------------
# Request / Response
# ---------------------------------------------------------------------------

class FeedbackRequest(BaseModel):
    """Request to submit feedback — user's feedback after listening."""
    user_id: str
    session_id: str
    prescription_id: str
    generation_id: Optional[int] = None
    day: int
    feedback: "FeedbackBody"


class FeedbackBody(BaseModel):
    subjective: SubjectiveFeedback
    behavioral: Optional[BehavioralData] = None
    wearable: Optional[WearableData] = None


class FeedbackResponse(BaseModel):
    """Agent ⑤ output."""
    agent_id: str = "feedback_agent"
    agent_version: str = "1.0.0"
    user_id: str
    session_id: str
    prescription_id: str
    feedback_id: str = Field(..., pattern=r"^fb_\d{8}_\d{3}$")
    feedback: dict  # mirrors the submitted feedback
    decision: FeedbackDecision
    user_profile_update: Optional[UserProfileUpdate] = None
    confidence: float
    reason: list[str]
    processing_time_ms: int
    timestamp: datetime


# resolve forward reference
FeedbackRequest.model_rebuild()
