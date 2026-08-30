"""V3 session activity and input-transition contracts (Amendment 001 §4.1)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import NonEmptyString, V3BaseModel


SUPPORTED_FLOW_CONTRACT_VERSION = "v3-owner-flow-1"

InputMode = Literal["with_document", "without_document"]
InputTransitionAction = Literal[
    "select_mode",
    "replace_document",
    "discard_document",
]


class UnderstandingRefState(V3BaseModel):
    understanding_id: NonEmptyString
    revision: Annotated[int, Field(ge=1)]


class QuestionnaireRefState(V3BaseModel):
    questionnaire_submission_id: NonEmptyString
    schema_id: Literal["questionnaire_v3"]
    schema_version: NonEmptyString
    manifest_version: NonEmptyString
    content_checksum: Annotated[str, Field(pattern=r"^sha256:.+")]


class SessionActivityState(V3BaseModel):
    session_id: NonEmptyString
    flow_contract_version: NonEmptyString | None
    input_mode: InputMode | None
    input_revision: Annotated[int, Field(ge=1)]
    active_document_id: NonEmptyString | None
    understanding_ref: UnderstandingRefState | None
    questionnaire_ref: QuestionnaireRefState | None


class InputTransitionRequest(V3BaseModel):
    action: InputTransitionAction
    expected_input_revision: Annotated[int, Field(ge=1)]
    input_mode: InputMode | None = None
    document_id: NonEmptyString | None = None

    @model_validator(mode="after")
    def validate_action_payload(self) -> "InputTransitionRequest":
        if self.action == "select_mode":
            if self.input_mode is None or self.document_id is not None:
                raise ValueError("select_mode requires input_mode and no document_id")
        elif self.action == "replace_document":
            if self.document_id is None or self.input_mode is not None:
                raise ValueError("replace_document requires document_id and no input_mode")
        elif self.input_mode is not None or self.document_id is not None:
            raise ValueError("discard_document cannot carry input_mode or document_id")
        return self


class InputTransitionResult(V3BaseModel):
    action: InputTransitionAction
    expected_input_revision: Annotated[int, Field(ge=1)]
