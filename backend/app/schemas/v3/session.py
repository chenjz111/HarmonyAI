"""Public V3 entry/session read models."""

from typing import Literal

from pydantic import model_validator

from .common import NonEmptyString, V3BaseModel


class EntryChoice(V3BaseModel):
    id: Literal["with_document", "without_document"]
    label: NonEmptyString
    next_route: Literal["/v3/material", "/v3/narrative"]

    @model_validator(mode="after")
    def id_and_route_must_match(self) -> "EntryChoice":
        expected = {
            "with_document": "/v3/material",
            "without_document": "/v3/narrative",
        }
        if self.next_route != expected[self.id]:
            raise ValueError("entry choice id and route do not match")
        return self


class EntryReadModel(V3BaseModel):
    page: Literal["entry"]
    session_id: NonEmptyString
    title: NonEmptyString
    description: NonEmptyString
    choices: list[EntryChoice]
