from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.schemas.evidence_v21 import AppetiteValue


class AnalysisMode(str, Enum):
    DOCUMENT_NARRATIVE_QUESTIONNAIRE = (
        "document_narrative_questionnaire"
    )
    DOCUMENT_QUESTIONNAIRE = "document_questionnaire"
    NARRATIVE_QUESTIONNAIRE = "narrative_questionnaire"
    QUESTIONNAIRE_ONLY = "questionnaire_only"


class QuestionnaireAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    question_id: str = Field(min_length=1)
    value: str | int | list[str] | AppetiteValue
    type: Literal[
        "single_choice",
        "visual_single",
        "frequency_0_4",
        "visual_multi",
        "multi_choice",
        "duration_choice",
    ] | None = None
    score: int | None = None


class QuestionnaireContext(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    mood_metaphor: str | None = None
    physical_signals: list[str] = Field(default_factory=list)


class QuestionnaireV2Submission(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["questionnaire_v2.0", "questionnaire_v2.1"]
    time_window_days: Literal[7, 14]
    answers: list[QuestionnaireAnswer] = Field(min_length=12)
    started_at: str | None = None
    completed_at: str | None = None
    dimension_scores: dict[str, int] | None = None
    context: QuestionnaireContext | None = None
    safety_flags: list[str] | None = None
    completion_seconds: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_version_shape(self):
        if self.schema_version == "questionnaire_v2.0":
            if self.time_window_days != 7:
                raise ValueError("questionnaire_v2.0 uses a 7-day window")
        else:
            if self.time_window_days != 14:
                raise ValueError("questionnaire_v2.1 uses a 14-day window")
            if len(self.answers) != 20:
                raise ValueError("questionnaire_v2.1 requires exactly 20 answers")
        return self


class AssessmentV2Request(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    session_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    document_id: str | None = None
    document_text: str | None = None
    narrative_text: str | None = None
    questionnaire_answers: QuestionnaireV2Submission


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
    assessment_id: str | None = None
    session_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    status: Literal["success", "degraded", "blocked_safety"]
    confidence: float = Field(
        ge=0,
        le=1,
        description="系统证据充分度，不是医学诊断准确率",
    )
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
