from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AnalysisMode(str, Enum):
    DOCUMENT_NARRATIVE_QUESTIONNAIRE = (
        "document_narrative_questionnaire"
    )
    DOCUMENT_QUESTIONNAIRE = "document_questionnaire"
    NARRATIVE_QUESTIONNAIRE = "narrative_questionnaire"
    QUESTIONNAIRE_ONLY = "questionnaire_only"


class AssessmentV2Request(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    document_id: str | None = None
    document_text: str | None = None
    narrative_text: str | None = None
    questionnaire_answers: (
        dict[str, Any] | list[dict[str, Any]]
    )


class SourceStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["document", "narrative", "questionnaire"]
    status: Literal[
        "confirmed",
        "used",
        "missing",
        "unavailable",
        "invalid",
    ]


class EmotionCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    emotion: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class EmotionProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_states: list[str]
    secondary_states: list[str]
    dimension_scores: dict[str, int]
    tcm_emotion_candidates: list[EmotionCandidate]


class PhysicalProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sleep_disturbance: int = Field(ge=0, le=100)
    low_energy: int = Field(ge=0, le=100)
    appetite_change: int = Field(ge=0, le=100)
    physical_signals: list[str]


class LifeEvents(BaseModel):
    model_config = ConfigDict(extra="forbid")

    triggers: list[str]


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str = Field(min_length=1)
    sources: list[str]
    summary: str = Field(min_length=1)


class ConflictItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1)
    sources: list[str]
    summary: str = Field(min_length=1)


class DegradationInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    triggered: bool
    reason_code: str | None
    fallback: str | None


class AssessmentV2Response(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: Literal["assessment_agent"]
    session_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    status: Literal["success", "degraded", "blocked_safety"]
    analysis_mode: AnalysisMode
    sources_used: list[SourceStatus]
    emotion_profile: EmotionProfile
    physical_profile: PhysicalProfile
    life_events: LifeEvents
    assessment_summary: str = Field(min_length=1)
    extracted_evidence: list[EvidenceItem]
    conflicts: list[ConflictItem]
    missing_information: list[str]
    safety_flags: list[str]
    degradation: DegradationInfo
    warnings: list[str]
    disclaimer: str = Field(min_length=1)
