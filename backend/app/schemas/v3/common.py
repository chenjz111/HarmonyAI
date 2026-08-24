"""Canonical types shared by every HarmonyAI V3 boundary."""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Annotated, Literal, TypeAlias

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StringConstraints,
    model_validator,
)


class V3BaseModel(BaseModel):
    """Base for externally parsed V3 payloads."""

    model_config = ConfigDict(extra="forbid")


NonEmptyString: TypeAlias = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]
Score01: TypeAlias = Annotated[float, Field(ge=0.0, le=1.0)]
def _validate_utc_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("timestamp must be timezone-aware UTC")
    return value


Timestamp: TypeAlias = Annotated[datetime, AfterValidator(_validate_utc_timestamp)]


class OrganCode(str, Enum):
    liver = "liver"
    heart = "heart"
    spleen = "spleen"
    lung = "lung"
    kidney = "kidney"


class ElementCode(str, Enum):
    wood = "wood"
    fire = "fire"
    earth = "earth"
    metal = "metal"
    water = "water"


class ToneCode(str, Enum):
    jiao = "jiao"
    zhi = "zhi"
    gong = "gong"
    shang = "shang"
    yu = "yu"


class SourceType(str, Enum):
    document = "document"
    case_summary = "case_summary"
    narrative = "narrative"
    voice_transcript = "voice_transcript"
    questionnaire = "questionnaire"
    user_correction = "user_correction"


class SafetyStatus(str, Enum):
    clear = "clear"
    needs_verification = "needs_verification"
    resolved = "resolved"
    confirmed_mental_health_risk = "confirmed_mental_health_risk"
    confirmed_acute_physical_risk = "confirmed_acute_physical_risk"


class Severity(str, Enum):
    none = "none"
    mild = "mild"
    moderate = "moderate"
    severe = "severe"
    unknown = "unknown"


class EvidenceDirection(str, Enum):
    supporting = "supporting"
    contradicting = "contradicting"


class UserGoalCode(str, Enum):
    sleep = "sleep"
    relaxation = "relaxation"
    emotion_regulation = "emotion_regulation"
    focus = "focus"
    energy = "energy"
    stress_relief = "stress_relief"
    other = "other"


class UserGoal(V3BaseModel):
    primary_goal: UserGoalCode
    secondary_goal: UserGoalCode | None = None
    custom_goal_text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)] | None = None

    @model_validator(mode="after")
    def validate_goal_combination(self) -> "UserGoal":
        if self.secondary_goal == self.primary_goal:
            raise ValueError("secondary_goal must differ from primary_goal")
        uses_other = UserGoalCode.other in {
            self.primary_goal,
            self.secondary_goal,
        }
        if uses_other and self.custom_goal_text is None:
            raise ValueError("custom_goal_text is required when other is selected")
        if not uses_other and self.custom_goal_text is not None:
            raise ValueError("custom_goal_text is only allowed when other is selected")
        return self


class OrganProfile(V3BaseModel):
    status: Literal["available", "insufficient"]
    weights: dict[OrganCode, Score01] | None
    score_semantics: Literal["relative_evidence_distribution"]

    @model_validator(mode="after")
    def validate_weight_state(self) -> "OrganProfile":
        if self.status == "insufficient":
            if self.weights is not None:
                raise ValueError("insufficient organ profile cannot contain weights")
            return self
        expected = set(OrganCode)
        if self.weights is None or set(self.weights) != expected:
            raise ValueError("available organ profile requires all five organ weights")
        if abs(sum(self.weights.values()) - 1.0) > 0.001:
            raise ValueError("organ weights must sum to 1 ± 0.001")
        return self


class ElementProfile(V3BaseModel):
    status: Literal["available", "insufficient"]
    weights: dict[ElementCode, Score01] | None
    score_semantics: Literal["relative_element_support"]

    @model_validator(mode="after")
    def validate_weight_state(self) -> "ElementProfile":
        if self.status == "insufficient":
            if self.weights is not None:
                raise ValueError("insufficient element profile cannot contain weights")
            return self
        expected = set(ElementCode)
        if self.weights is None or set(self.weights) != expected:
            raise ValueError("available element profile requires all five element weights")
        if abs(sum(self.weights.values()) - 1.0) > 0.001:
            raise ValueError("element weights must sum to 1 ± 0.001")
        return self


class BooleanFactValue(V3BaseModel):
    type: Literal["boolean"]
    value: StrictBool


class SeverityFactValue(V3BaseModel):
    type: Literal["severity"]
    value: Severity


class FrequencyFactValue(V3BaseModel):
    type: Literal["frequency_0_4"]
    value: Annotated[StrictInt, Field(ge=0, le=4)]


class NumberFactValue(V3BaseModel):
    type: Literal["number"]
    value: float


class CodedTextFactValue(V3BaseModel):
    type: Literal["coded_text"]
    value: NonEmptyString


NormalizedFactValue: TypeAlias = Annotated[
    BooleanFactValue
    | SeverityFactValue
    | FrequencyFactValue
    | NumberFactValue
    | CodedTextFactValue,
    Field(discriminator="type"),
]


class SourceRef(V3BaseModel):
    source_id: NonEmptyString
    source_type: SourceType
    span_ref: NonEmptyString | None = None


class Degradation(V3BaseModel):
    active: bool
    reason_codes: list[NonEmptyString]


class Conflict(V3BaseModel):
    conflict_id: NonEmptyString
    fact_ids: Annotated[list[NonEmptyString], Field(min_length=2)]
    severity: Literal["minor", "major"]
    display_summary: NonEmptyString
    resolution_status: Literal["unresolved", "resolved"]


class MissingInformation(V3BaseModel):
    missing_id: NonEmptyString
    field_code: NonEmptyString
    display_question: NonEmptyString
    required_for_diagnosis: bool


class MedicalReview(V3BaseModel):
    status: Literal["approved"]
    review_version: NonEmptyString


class ClaimDictionaryEntry(V3BaseModel):
    claim_code: NonEmptyString
    display_name: NonEmptyString
    category: NonEmptyString
    value_type: Literal["boolean", "severity", "frequency_0_4", "number", "coded_text"]
    allowed_values: list[StrictBool | StrictInt | float | NonEmptyString]
    questionnaire_option_refs: list[NonEmptyString]
    organ_mapping_allowed: bool
    medical_review: MedicalReview

    @model_validator(mode="after")
    def allowed_values_match_value_type(self) -> "ClaimDictionaryEntry":
        values = self.allowed_values
        if not values:
            raise ValueError("claim dictionary allowed_values cannot be empty")
        if self.value_type == "boolean" and not all(type(value) is bool for value in values):
            raise ValueError("boolean claim allowed_values must be booleans")
        if self.value_type == "severity" and not all(
            isinstance(value, str) and value in {item.value for item in Severity}
            for value in values
        ):
            raise ValueError("severity claim allowed_values must use canonical severity codes")
        if self.value_type == "frequency_0_4" and not all(
            type(value) is int and 0 <= value <= 4 for value in values
        ):
            raise ValueError("frequency claim allowed_values must be integers from 0 to 4")
        if self.value_type == "number" and not all(
            type(value) in {int, float} for value in values
        ):
            raise ValueError("number claim allowed_values must be numeric")
        if self.value_type == "coded_text" and not all(
            isinstance(value, str) and bool(value.strip()) for value in values
        ):
            raise ValueError("coded_text claim allowed_values must be non-empty strings")
        if len({repr(value) for value in values}) != len(values):
            raise ValueError("claim dictionary allowed_values must be unique")
        if len(set(self.questionnaire_option_refs)) != len(self.questionnaire_option_refs):
            raise ValueError("questionnaire_option_refs must be unique")
        return self


class AuthPrincipal(V3BaseModel):
    internal_user_pk: Annotated[int, Field(gt=0)]
    public_user_id: NonEmptyString
    auth_type: Literal["registered", "guest"]
    guest_expires_at: Timestamp | None

    @model_validator(mode="after")
    def validate_guest_expiry(self) -> "AuthPrincipal":
        if self.auth_type == "guest" and self.guest_expires_at is None:
            raise ValueError("guest principal requires guest_expires_at")
        if self.auth_type == "registered" and self.guest_expires_at is not None:
            raise ValueError("registered principal cannot have guest_expires_at")
        return self


class GuestAuthResponse(V3BaseModel):
    access_token: NonEmptyString
    token_type: Literal["Bearer"]
    expires_at: Timestamp
    public_user_id: NonEmptyString


class QuestionnaireOption(V3BaseModel):
    option_code: NonEmptyString
    label: NonEmptyString
    claim_code: NonEmptyString | None
    is_none: bool
    exclusive_with: list[NonEmptyString]

    @model_validator(mode="after")
    def validate_none_semantics(self) -> "QuestionnaireOption":
        if self.is_none:
            if self.claim_code is not None or "*" not in self.exclusive_with:
                raise ValueError("none option requires null claim and wildcard exclusivity")
        elif self.claim_code is None:
            raise ValueError("non-none option requires claim_code")
        return self


class QuestionnaireQuestion(V3BaseModel):
    question_id: Annotated[str, Field(pattern=r"^q(?:0[1-9]|10)$")]
    position: Annotated[int, Field(ge=1, le=10)]
    prompt: NonEmptyString
    answer_type: Literal[
        "multi_choice_evidence",
        "single_choice_evidence",
        "frequency_0_4",
    ]
    required: bool
    min_selections: Annotated[int, Field(ge=1)] | None = None
    max_selections: Annotated[int, Field(ge=1)] | None = None
    options: list[QuestionnaireOption] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_answer_shape(self) -> "QuestionnaireQuestion":
        if self.answer_type == "frequency_0_4":
            if self.options or self.min_selections is not None or self.max_selections is not None:
                raise ValueError("frequency question cannot define choice options")
            return self
        if not self.options or self.min_selections is None or self.max_selections is None:
            raise ValueError("choice question requires options and selection bounds")
        if self.min_selections > self.max_selections or self.max_selections > len(self.options):
            raise ValueError("question selection bounds are inconsistent")
        codes = [item.option_code for item in self.options]
        if len(codes) != len(set(codes)):
            raise ValueError("question option codes must be unique")
        if sum(item.is_none for item in self.options) > 1:
            raise ValueError("question can contain at most one none option")
        return self


class QuestionnaireSchemaV3(V3BaseModel):
    schema_id: Literal["questionnaire_v3"]
    schema_version: NonEmptyString
    manifest_version: NonEmptyString
    time_window: Literal["past_7_days"]
    time_window_days: Literal[7]
    question_count: Literal[10]
    questions: Annotated[list[QuestionnaireQuestion], Field(min_length=10, max_length=10)]
    claim_dictionary_version: NonEmptyString
    content_checksum: Annotated[str, Field(pattern=r"^sha256:.+")]
    review_status: Literal["approved"]

    @model_validator(mode="after")
    def validate_question_identity(self) -> "QuestionnaireSchemaV3":
        ids = [item.question_id for item in self.questions]
        positions = [item.position for item in self.questions]
        if ids != [f"q{index:02d}" for index in range(1, 11)]:
            raise ValueError("questions must be ordered q01 through q10")
        if positions != list(range(1, 11)):
            raise ValueError("question positions must be ordered 1 through 10")
        return self


class MultiChoiceAnswer(V3BaseModel):
    question_id: Annotated[str, Field(pattern=r"^q(?:0[1-9]|10)$")]
    answer_type: Literal["multi_choice_evidence"]
    value: Annotated[list[NonEmptyString], Field(min_length=1)]


class SingleChoiceAnswer(V3BaseModel):
    question_id: Annotated[str, Field(pattern=r"^q(?:0[1-9]|10)$")]
    answer_type: Literal["single_choice_evidence"]
    value: NonEmptyString


class FrequencyAnswer(V3BaseModel):
    question_id: Annotated[str, Field(pattern=r"^q(?:0[1-9]|10)$")]
    answer_type: Literal["frequency_0_4"]
    value: Annotated[StrictInt, Field(ge=0, le=4)]


QuestionnaireAnswer: TypeAlias = Annotated[
    MultiChoiceAnswer | SingleChoiceAnswer | FrequencyAnswer,
    Field(discriminator="answer_type"),
]


class QuestionnaireV3Submission(V3BaseModel):
    questionnaire_submission_id: NonEmptyString
    schema_id: Literal["questionnaire_v3"]
    schema_version: NonEmptyString
    manifest_version: NonEmptyString
    content_checksum: Annotated[str, Field(pattern=r"^sha256:.+")]
    time_window_days: Literal[7]
    answers: Annotated[list[QuestionnaireAnswer], Field(min_length=1, max_length=10)]
    started_at: Timestamp
    completed_at: Timestamp

    @model_validator(mode="after")
    def validate_submission_identity(self) -> "QuestionnaireV3Submission":
        question_ids = [item.question_id for item in self.answers]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("submission cannot answer one question twice")
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at")
        return self


class ProviderCapabilities(V3BaseModel):
    structured_json: bool
    max_input_characters: Annotated[int, Field(gt=0)]


class ProviderHealth(V3BaseModel):
    status: Literal["configured", "healthy", "degraded", "down", "not_configured"]
    provider_kind: Literal["cloud", "local", "rule"]
    provider: NonEmptyString
    model: NonEmptyString | None
    checked_at: Timestamp
    capabilities: ProviderCapabilities
    safe_message: str | None