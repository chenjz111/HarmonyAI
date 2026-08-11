"""Stable HTTP request models for the Sprint 3 workflow endpoints."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.assessment_v2 import AssessmentV2Request


class WorkflowV2Request(AssessmentV2Request):
    assessment_confirmed: bool = False
    assessment_id: str | None = None
    assessment_revision: int | None = Field(default=None, ge=1)
    feedback_payload: dict[str, object] | None = None


class MusicV2Request(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    session_id: str = Field(min_length=1)
    prescription: dict[str, object]
