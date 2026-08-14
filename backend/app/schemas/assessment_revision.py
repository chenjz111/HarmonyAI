"""Frozen request/response schemas for Assessment follow-up and revision flows."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.schemas.evidence_v21 import AppetiteValue


ScalarValue = str | int | float | bool | None
ContractValue = ScalarValue | list[str] | AppetiteValue


class FollowUpAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    follow_up_id: str = Field(min_length=1)
    answer: ContractValue


class FollowUpSubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    revision: int = Field(ge=1)
    answers: list[FollowUpAnswer] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def unique_follow_up_ids(self):
        ids = [item.follow_up_id for item in self.answers]
        if len(ids) != len(set(ids)):
            raise ValueError("follow_up_id values must be unique")
        return self


class RevisionChange(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    field: str = Field(min_length=1)
    from_value: ContractValue = Field(default=None, alias="from")
    to_value: ContractValue = Field(alias="to")


class AssessmentConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    revision: int = Field(ge=1)
    confirmation_level: Literal[
        "fully_accurate",
        "partially_accurate",
        "inaccurate",
    ]
    corrections: list[RevisionChange] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def corrections_match_level(self):
        if self.confirmation_level == "partially_accurate" and not self.corrections:
            raise ValueError("partial confirmation requires at least one correction")
        return self


class SafetyVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    revision: int = Field(ge=1)
    resolution: Literal[
        "current",
        "past_resolved",
        "other_person",
        "ocr_error",
        "uncertain",
    ]


class AssessmentRevisionContract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    assessment_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    previous_revision: int | None = Field(default=None, ge=1)
    created_at: str = Field(min_length=1)
    change_summary: str = Field(min_length=1)
    changes: list[RevisionChange]
