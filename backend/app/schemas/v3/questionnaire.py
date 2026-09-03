"""V3.1 questionnaire submission contracts (Issue #99).

A complete Q1-Q10 submission is persisted as an immutable
QuestionnaireSubmissionV3 and bound as the session's active questionnaire
source (without_document path) with an optimistic input_revision CAS.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import (
    NonEmptyString,
    QuestionnaireAnswer,
    Timestamp,
    V3BaseModel,
)


class QuestionnaireSubmissionRequest(V3BaseModel):
    session_id: NonEmptyString
    expected_input_revision: Annotated[int, Field(ge=1)]
    schema_id: Literal["questionnaire_v3"]
    schema_version: NonEmptyString
    manifest_version: NonEmptyString
    content_checksum: Annotated[str, Field(pattern=r"^sha256:.+")]
    answers: Annotated[list[QuestionnaireAnswer], Field(min_length=1, max_length=10)]
    started_at: Timestamp
    completed_at: Timestamp

    @model_validator(mode="after")
    def validate_submission_identity(self) -> "QuestionnaireSubmissionRequest":
        question_ids = [item.question_id for item in self.answers]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("submission cannot answer one question twice")
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at")
        return self


class QuestionnaireSubmissionResponse(V3BaseModel):
    questionnaire_submission_id: NonEmptyString
    schema_id: Literal["questionnaire_v3"]
    schema_version: NonEmptyString
    manifest_version: NonEmptyString
    content_checksum: NonEmptyString
    input_revision: Annotated[int, Field(ge=1)]
    status: Literal["submitted"]
