"""V3 document read/write contracts (Issue #99 — ownership unification).

Document rows are owned by the authenticated user; every operation validates
that the document belongs to the caller and (for listing) to the given session.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import NonEmptyString, V3BaseModel


class DocumentCreateRequest(V3BaseModel):
    """Client-registered document metadata only. storage_path / status / OCR
    fields are server-controlled: the actual upload + OCR runs through the
    existing upload/OCR chain, not through this endpoint."""

    session_id: NonEmptyString
    original_filename: NonEmptyString
    file_type: Literal["jpg", "jpeg", "png", "pdf"]
    file_size_bytes: Annotated[int, Field(gt=0)]


class DocumentReadModel(V3BaseModel):
    document_id: NonEmptyString
    session_id: NonEmptyString
    original_filename: NonEmptyString
    file_type: str
    file_size_bytes: int
    status: str
    ocr_confidence: str | None
    ocr_error_code: str | None
    ocr_confirmed: bool


class DocumentList(V3BaseModel):
    session_id: NonEmptyString
    documents: list[DocumentReadModel]
    total: int


class DocumentSetReplaceRequest(V3BaseModel):
    session_id: NonEmptyString
    expected_input_revision: Annotated[int, Field(ge=1)]
    document_ids: Annotated[list[NonEmptyString], Field(min_length=1, max_length=3)]

    @model_validator(mode="after")
    def unique_documents(self) -> "DocumentSetReplaceRequest":
        if len(set(self.document_ids)) != len(self.document_ids):
            raise ValueError("document_ids must be unique")
        return self


class DocumentSetReadModel(V3BaseModel):
    document_set_id: NonEmptyString
    revision: Annotated[int, Field(ge=1)]
    status: Literal["active", "superseded", "discarded"]
    documents: list[DocumentReadModel]
    input_revision: Annotated[int, Field(ge=1)]


RelevanceOutcome = Literal["VALID", "INVALID", "IRRELEVANT", "INSUFFICIENT"]


class DocumentRelevanceItem(V3BaseModel):
    document_id: NonEmptyString
    outcome: RelevanceOutcome
    reason_codes: list[NonEmptyString] = Field(default_factory=list)


class DocumentRelevanceRecordRequest(V3BaseModel):
    document_set_id: NonEmptyString
    document_set_revision: Annotated[int, Field(ge=1)]
    items: Annotated[list[DocumentRelevanceItem], Field(min_length=1)]
    evaluator: NonEmptyString | None = None
    evaluator_version: NonEmptyString | None = None


class DocumentRelevanceItemRead(V3BaseModel):
    document_id: NonEmptyString
    outcome: RelevanceOutcome
    reason_codes: list[NonEmptyString]
    evaluated_at: str


class DocumentRelevanceReadModel(V3BaseModel):
    document_set_id: NonEmptyString
    document_set_revision: Annotated[int, Field(ge=1)]
    items: list[DocumentRelevanceItemRead]
