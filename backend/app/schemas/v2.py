"""Sprint 3 V2 API Contract — per docs/api-contract-v2.md.

Unified response format:
  { success, data, error, meta }
"""
from __future__ import annotations
from typing import Optional, Any
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Unified response envelope
# ---------------------------------------------------------------------------
class V2Status(str, Enum):
    SUCCESS = "success"
    DEGRADED = "degraded"
    NEEDS_CONFIRMATION = "needs_confirmation"
    BLOCKED_SAFETY = "blocked_safety"
    FAILED = "failed"


class V2Error(BaseModel):
    code: str
    message: str
    retryable: bool = False
    next_actions: list[str] = Field(default_factory=list)


class V2Meta(BaseModel):
    request_id: str
    schema_version: str = "2.0"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class V2Response(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[V2Error] = None
    meta: V2Meta


def v2_ok(data: dict, request_id: str) -> dict:
    return V2Response(success=True, data=data, error=None,
                      meta=V2Meta(request_id=request_id)).model_dump(mode="json")


def v2_err(code: str, message: str, request_id: str, retryable: bool = True,
           next_actions: list[str] | None = None) -> dict:
    return V2Response(
        success=False, data=None,
        error=V2Error(code=code, message=message, retryable=retryable,
                       next_actions=next_actions or []),
        meta=V2Meta(request_id=request_id),
    ).model_dump(mode="json")


# ---------------------------------------------------------------------------
# Session (POST /api/v2/sessions)
# ---------------------------------------------------------------------------
class SessionCreateRequest(BaseModel):
    user_id: str = Field(default="demo_user_001")
    entry_mode: str = Field(default="full")
    client_version: str = Field(default="competition-2026.07.31")


# ---------------------------------------------------------------------------
# Document Upload (POST /api/v2/documents — multipart/form-data)
# ---------------------------------------------------------------------------
class DocumentType(str, Enum):
    OUTPATIENT = "outpatient_record"
    CHECKUP = "checkup_report"
    SLEEP_EMOTION = "sleep_emotion_record"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Document Confirmation (PATCH /api/v2/documents/{id}/confirmation)
# ---------------------------------------------------------------------------
class DocumentConfirmationRequest(BaseModel):
    session_id: str
    confirmed: bool
    document_text: Optional[str] = None
    redactions_confirmed: bool = False


# ---------------------------------------------------------------------------
# Feedback 2.0 (per docs/feedback-v2-spec.md)
# ---------------------------------------------------------------------------
class PreState(BaseModel):
    tension: int = Field(ge=0, le=10)
    body_tension: int = Field(ge=0, le=10)
    mental_fatigue: int = Field(ge=0, le=10)
    goal: str = Field(default="relax", description="relax/sleep/calm/focus/other")


class PostState(BaseModel):
    tension: int = Field(ge=0, le=10)
    body_tension: int = Field(ge=0, le=10)
    mental_fatigue: int = Field(ge=0, le=10)
    change_label: str = Field(default="no_change", description="better/slightly_better/no_change/slightly_worse/worse")


class PlaybackData(BaseModel):
    listened_seconds: int = 0
    duration_seconds: int = 0
    completion_rate: float = Field(ge=0, le=1)
    pause_count: int = 0
    skip_count: int = 0


class FeedbackV2Request(BaseModel):
    """Feedback 2.0 full request — per feedback-v2-spec.md §4."""
    schema_version: str = "feedback_v2.0"
    session_id: str
    prescription_id: Optional[str] = None
    music_id: Optional[str] = None

    pre_state: PreState
    post_state: PostState

    experience: dict = Field(default_factory=dict)  # {overall_rating, relaxation_rating, music_match_rating, continue_use, favorite, disliked_features, comment}
    playback: Optional[PlaybackData] = None
    submitted_at: Optional[str] = None
