"""Pydantic schemas for the Assessment API — strictly aligned with agent-schemas.md Agent ①.

Every field name, type, and structure mirrors the JSON Schema defined in docs/architecture/agent-schemas.md.
"""
from __future__ import annotations
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Nested objects — exactly mirror agent-schemas.md structure
# ---------------------------------------------------------------------------

class EmotionScores(BaseModel):
    anxiety: float = Field(..., ge=0, le=100, description="焦虑分数")
    depression: float = Field(..., ge=0, le=100, description="抑郁分数")
    anger: float = Field(..., ge=0, le=100, description="愤怒分数")
    fear: float = Field(..., ge=0, le=100, description="恐惧分数")
    overthinking: float = Field(..., ge=0, le=100, description="思虑分数")


class BodyIndicators(BaseModel):
    sleep_quality: float = Field(..., ge=0, le=100)
    appetite: float = Field(..., ge=0, le=100)
    energy: float = Field(..., ge=0, le=100)
    palpitation: float = Field(..., ge=0, le=100)
    digestion: float = Field(..., ge=0, le=100)


class QuestionnaireScores(BaseModel):
    total: float
    emotion_dimension: float
    sleep_dimension: float
    body_dimension: float


class HealthProfile(BaseModel):
    emotion_scores: EmotionScores
    body_indicators: BodyIndicators
    questionnaire_scores: QuestionnaireScores


class RawInput(BaseModel):
    source_type: str = Field(..., description="western_medicine / tcm_report / questionnaire")
    ocr_text: Optional[str] = None
    original_diagnosis: Optional[list[str]] = None
    questionnaire_raw: Optional[dict] = None


class TermMapping(BaseModel):
    western_term: str
    tcm_syndrome: str
    source: str = Field(..., description="preset_table / llm_inference")
    confidence: float


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class AssessmentRequest(BaseModel):
    """POST /assessment request body."""
    user_id: str = Field(..., alias="user_id")
    session_id: str = Field(..., alias="session_id")
    input_channel: str = Field(..., description="case_input / voice_input / questionnaire")
    raw_input: RawInput
    health_profile: HealthProfile


class AssessmentResponse(BaseModel):
    """POST /assessment response body — mirrors Agent ① output."""
    agent_id: str = "evaluation_agent"
    agent_version: str = "1.0.0"
    user_id: str
    session_id: str
    input_channel: str
    raw_input: RawInput
    health_profile: HealthProfile
    term_mapping: list[TermMapping]
    confidence: float = Field(..., ge=0, le=1)
    reason: list[str]
    processing_time_ms: int
    timestamp: datetime

    model_config = {"populate_by_name": True}


class AssessmentListResponse(BaseModel):
    """List of assessments for a user."""
    items: list[AssessmentResponse]
    total: int
    user_id: str
