"""Sprint 3 V2 API Contract — per docs/api-contract-v2.md.

Unified response format:
  { success, data, error, meta }
"""
from __future__ import annotations
from typing import Optional
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field, model_validator


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

    @model_validator(mode="after")
    def validate_confirmation(self):
        if self.confirmed:
            if not self.redactions_confirmed:
                raise ValueError("redactions_confirmed is required")
            if not self.document_text or not self.document_text.strip():
                raise ValueError("document_text is required")
        return self
