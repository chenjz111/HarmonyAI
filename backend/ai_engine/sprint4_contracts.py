from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal, NotRequired, TypedDict


EvidenceSourceType = Literal[
    "questionnaire",
    "narrative",
    "document",
    "user_follow_up",
    "user_correction",
]


class ProviderErrorCode(str, Enum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    CONNECTION_TIMEOUT = "CONNECTION_TIMEOUT"
    READ_TIMEOUT = "READ_TIMEOUT"
    RATE_LIMITED = "RATE_LIMITED"
    SERVER_ERROR = "SERVER_ERROR"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    INVALID_JSON = "INVALID_JSON"
    JSON_REPAIR_FAILED = "JSON_REPAIR_FAILED"
    SCHEMA_VIOLATION = "SCHEMA_VIOLATION"
    EMPTY_RESPONSE = "EMPTY_RESPONSE"


# Compatibility alias for the pre-freeze internal name.
ProviderReasonCode = str


class EvidenceItem(TypedDict):
    evidence_id: str
    category: str
    label: str
    display_name: str
    value: int | float | str | bool | None
    polarity: Literal["present", "absent", "reduced", "increased", "unchanged"]
    severity: Literal["none", "mild", "moderate", "severe"]
    severity_display: str
    time_window: str
    source_type: EvidenceSourceType
    source_ref: str
    quote: NotRequired[str]
    extraction_confidence: NotRequired[float]
    confirmed: bool
    dimension_score: NotRequired[int | None]
    negated: NotRequired[bool]


class Conflict(TypedDict):
    conflict_id: str
    topic: str
    display_topic: str
    severity: Literal["minor", "moderate", "major"]
    sources: list[dict[str, object]]
    summary: str
    resolution: Literal[
        "awaiting_user",
        "resolved_by_user",
        "resolved_by_rule",
        "unresolved",
    ]
    user_resolution: NotRequired[str | None]


class MissingInformation(TypedDict):
    field: str
    display_name: str
    reason: str
    severity: Literal["critical", "important", "supplementary"]
    candidate_follow_up: NotRequired[dict[str, object] | None]


class FollowUpQuestion(TypedDict):
    follow_up_id: str
    assessment_id: str
    trigger_reason: str
    priority: int
    question_id: str
    text: str
    type: Literal["single_choice", "multi_choice", "scale_0_10", "text"]
    options: list[str]
    required: bool
    max_questions_total: int


class AssessmentRevision(TypedDict):
    assessment_id: str
    revision: int
    previous_revision: int | None
    created_at: str
    change_summary: str
    changes: list[dict[str, object]]


@dataclass(frozen=True)
class ProviderRequest:
    system_prompt: str
    user_prompt: str
    operation: str
    prompt_version: str
    timeout_seconds: float = 20.0


@dataclass(frozen=True)
class ProviderResponse:
    data: dict[str, object]
    provider: str
    model: str
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None
    attempts: int


class ProviderError(RuntimeError):
    def __init__(
        self,
        reason_code: ProviderErrorCode | str,
        retryable: bool,
        user_message: str,
        *,
        cause: BaseException | None = None,
    ) -> None:
        self.reason_code = (
            reason_code.value if isinstance(reason_code, ProviderErrorCode) else reason_code
        )
        self.error_code = self.reason_code
        self.retryable = retryable
        self.user_message = user_message
        self.cause = cause
        super().__init__(f"{reason_code}: {user_message}")


@dataclass(frozen=True)
class NarrativeEvidence:
    category: str
    label: str
    value: int | str | bool | None
    polarity: str
    time_window: str | None
    quote: str
    source_ref: str
    extraction_confidence: float
    negated: bool


@dataclass(frozen=True)
class NarrativeExtractionResult:
    status: Literal["processed", "unavailable", "degraded"]
    items: tuple[NarrativeEvidence, ...]
    evidence_quotes: tuple[NarrativeEvidence, ...]
    reason_code: str | None = None
    warnings: tuple[str, ...] = ()
    model_metadata: dict[str, object] | None = None
