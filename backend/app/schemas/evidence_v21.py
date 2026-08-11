"""Frozen Sprint 4 EvidenceItem value union."""
from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AppetiteValue(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    direction: Literal["increase", "decrease", "none"]
    severity: int = Field(ge=0, le=4)

    @model_validator(mode="after")
    def validate_none_severity(self):
        if self.direction == "none" and self.severity != 0:
            raise ValueError("severity must be zero when appetite direction is none")
        return self


class EvidenceBase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    evidence_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    polarity: Literal["present", "absent", "reduced", "increased", "unchanged"]
    severity: Literal["none", "mild", "moderate", "severe"]
    severity_display: str = Field(min_length=1)
    time_window: str = Field(min_length=1)
    source_type: Literal[
        "questionnaire",
        "narrative",
        "document",
        "user_follow_up",
        "user_correction",
    ]
    source_ref: str = Field(min_length=1)
    quote: str | None = None
    extraction_confidence: float | None = Field(default=None, ge=0, le=1)
    confirmed: bool
    dimension_score: int | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def validate_source_requirements(self):
        if self.source_type in {"narrative", "document"}:
            if not self.quote or not self.quote.strip():
                raise ValueError("quote is required for narrative/document evidence")
        if self.source_type == "narrative" and self.extraction_confidence is None:
            raise ValueError("extraction_confidence is required for narrative evidence")
        return self


class NumericEvidence(EvidenceBase):
    category: Literal["emotion", "sleep", "energy"]
    value: int = Field(ge=0, le=4)


class CategoricalEvidence(EvidenceBase):
    category: Literal["life_event", "goal"]
    value: str = Field(min_length=1)


class PhysicalEvidence(EvidenceBase):
    category: Literal["physical"]
    value: list[Annotated[str, Field(min_length=1)]] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_values(self):
        if len(self.value) != len(set(self.value)):
            raise ValueError("physical evidence values must be unique")
        return self


class AppetiteEvidence(EvidenceBase):
    category: Literal["appetite"]
    value: AppetiteValue


EvidenceItemV21 = Annotated[
    Union[
        NumericEvidence,
        CategoricalEvidence,
        PhysicalEvidence,
        AppetiteEvidence,
    ],
    Field(discriminator="category"),
]
