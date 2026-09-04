"""Public V3 entry/session read models and input-transition contracts."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .assessment import QuestionnaireRef, UnderstandingRef
from .common import NonEmptyString, V3BaseModel


class EntryChoice(V3BaseModel):
    id: Literal["with_document", "without_document"]
    label: NonEmptyString
    next_route: Literal["/v3/material", "/v3/narrative", "/v3/questionnaire"]

    @model_validator(mode="after")
    def id_and_route_must_match(self) -> "EntryChoice":
        expected = {
            "with_document": {"/v3/material"},
            "without_document": {"/v3/narrative", "/v3/questionnaire"},
        }
        if self.next_route not in expected[self.id]:
            raise ValueError("entry choice id and route do not match")
        return self


class EntryReadModel(V3BaseModel):
    page: Literal["entry"]
    session_id: NonEmptyString
    title: NonEmptyString
    description: NonEmptyString
    choices: list[EntryChoice]


class SessionActivityReadModel(V3BaseModel):
    """Active-input state of a v3-owner-flow-1 session (amendment §4.1)."""

    session_id: NonEmptyString
    flow_contract_version: Literal["v3-owner-flow-1"]
    input_mode: Literal["with_document", "without_document"] | None
    input_revision: Annotated[int, Field(ge=1)]
    active_document_id: NonEmptyString | None
    understanding_ref: UnderstandingRef | None
    questionnaire_ref: QuestionnaireRef | None


InputTransitionAction = Literal[
    "select_mode",
    "replace_document",
    "discard_document",
]


class InputTransitionRequest(V3BaseModel):
    expected_input_revision: Annotated[int, Field(ge=1)]
    action: InputTransitionAction
    input_mode: Literal["with_document", "without_document"] | None = None
    document_id: NonEmptyString | None = None

    @model_validator(mode="after")
    def validate_action_payload(self) -> "InputTransitionRequest":
        if self.action == "select_mode":
            if self.input_mode is None:
                raise ValueError("select_mode requires input_mode")
            if self.document_id is not None:
                raise ValueError("select_mode cannot carry document_id")
        elif self.action == "replace_document":
            if self.document_id is None:
                raise ValueError("replace_document requires document_id")
            if self.input_mode is not None:
                raise ValueError("replace_document cannot carry input_mode")
        else:  # discard_document
            if self.document_id is not None or self.input_mode is not None:
                raise ValueError("discard_document cannot carry input_mode/document_id")
        return self
