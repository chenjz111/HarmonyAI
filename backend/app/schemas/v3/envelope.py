"""Shared success and error envelopes for every public V3 API."""

from typing import Generic, Literal, TypeVar

from pydantic import Field

from .common import NonEmptyString, V3BaseModel


DataT = TypeVar("DataT")


class V3SuccessEnvelope(V3BaseModel, Generic[DataT]):
    ok: Literal[True] = True
    data: DataT
    request_id: NonEmptyString
    schema_version: Literal["harmonyai_v3.0"] = "harmonyai_v3.0"


class V3Error(V3BaseModel):
    code: NonEmptyString
    message: NonEmptyString
    retryable: bool
    next_actions: list[NonEmptyString] = Field(default_factory=list)


class V3ErrorEnvelope(V3BaseModel):
    ok: Literal[False] = False
    error: V3Error
    request_id: NonEmptyString
    schema_version: Literal["harmonyai_v3.0"] = "harmonyai_v3.0"
