"""V3 document read/write contracts (Issue #99 — ownership unification).

Document rows are owned by the authenticated user; every operation validates
that the document belongs to the caller and (for listing) to the given session.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .common import NonEmptyString, V3BaseModel


class DocumentCreateRequest(V3BaseModel):
    session_id: NonEmptyString
    original_filename: NonEmptyString
    file_type: Literal["jpg", "jpeg", "png", "pdf"]
    file_size_bytes: Annotated[int, Field(gt=0)]
    storage_path: NonEmptyString
    status: Literal["uploaded", "ocr_failed"] = "uploaded"
    ocr_text: str | None = None
    ocr_confidence: Literal["high", "medium", "low"] | None = None
    ocr_error_code: NonEmptyString | None = None


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
