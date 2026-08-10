from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


class QuestionnaireValidationError(ValueError):
    """Raised when Questionnaire V2 answers do not match its fixed contract."""


V21_QUESTION_IDS = (
    "q01_goal",
    "q02_mood_state",
    "q03_tension_frequency",
    "q04_worry_control",
    "q05_overthinking",
    "q06_irritability",
    "q07_low_mood",
    "q08_interest_loss",
    "q09_fear_unease",
    "q10_sleep_disturbance",
    "q11_low_energy",
    "q12_appetite_change",
    "q13_body_tension",
    "q14_physical_signals",
    "q15_duration",
    "q16_daily_impact",
    "q17_change_goal",
    "q18_social_function",
    "q19_safety_context",
    "q20_safety",
)

_V21_DIMENSION_BY_QUESTION = {
    "q03_tension_frequency": "tension_worry",
    "q05_overthinking": "overthinking",
    "q06_irritability": "irritability_anger",
    "q07_low_mood": "low_mood",
    "q08_interest_loss": "interest_loss",
    "q09_fear_unease": "fear_unease",
    "q10_sleep_disturbance": "sleep_disturbance",
    "q11_low_energy": "low_energy",
    "q12_appetite_change": "appetite_change",
    "q13_body_tension": "body_tension",
    "q16_daily_impact": "daily_impact",
    "q18_social_function": "social_function",
}
_V21_MOOD_OPTIONS = {"sunny", "lightly_cloudy", "cloudy", "rainy", "stormy"}
_V21_SAFETY_OPTIONS = {
    "none",
    "self_harm_thoughts",
    "severe_chest_pain",
    "severe_breathing_difficulty",
}
_V21_PHYSICAL_OPTIONS = {
    "neck_tension",
    "head_heaviness",
    "palpitation",
    "stomach_discomfort",
    "fatigue",
    "other",
}


@dataclass(frozen=True)
class DimensionScore:
    raw_score: int
    normalized_score: int
    weighted_score: int
    source_questions: tuple[str, ...]
    q04_qualitative: int | None = None


@dataclass(frozen=True)
class QuestionnaireScore:
    schema_version: str
    questions_answered: int
    dimension_scores: dict[str, DimensionScore]
    physical_signals: tuple[str, ...]
    safety_flags: tuple[str, ...]
    qualitative: dict[str, object]
    source: str


@dataclass(frozen=True)
class QuickStateScore:
    schema_version: str
    values: dict[str, int]
    goal: str
    source: str = "quick_state"


_QUESTION_IDS = (
    "q01_mood_weather",
    "q02_tension_worry",
    "q03_overthinking",
    "q04_irritability_anger",
    "q05_low_mood",
    "q06_interest_loss",
    "q07_fear_unease",
    "q08_sleep_disturbance",
    "q09_low_energy",
    "q10_appetite_change",
    "q11_daily_impact",
    "q12_physical_safety",
)

_MOOD_WEATHER_OPTIONS = {
    "sunny",
    "lightly_cloudy",
    "cloudy",
    "rainy",
    "stormy",
}

_DIMENSION_BY_QUESTION = {
    "q02_tension_worry": "tension_worry",
    "q03_overthinking": "overthinking",
    "q04_irritability_anger": "irritability_anger",
    "q05_low_mood": "low_mood",
    "q06_interest_loss": "interest_loss",
    "q07_fear_unease": "fear_unease",
    "q08_sleep_disturbance": "sleep_disturbance",
    "q09_low_energy": "low_energy",
    "q10_appetite_change": "appetite_change",
    "q11_daily_impact": "daily_impact",
}

_PHYSICAL_SIGNALS = (
    "neck_tension",
    "head_heaviness",
    "palpitation",
    "stomach_discomfort",
    "fatigue",
    "other",
)
_SAFETY_SIGNALS = (
    "severe_chest_pain",
    "severe_breathing_difficulty",
    "self_harm_thoughts",
)
_Q12_OPTIONS = set(_PHYSICAL_SIGNALS) | set(_SAFETY_SIGNALS) | {"none"}


def score_questionnaire(
    answers: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> dict[str, object]:
    """Validate and deterministically score a complete Questionnaire V2 response."""
    if isinstance(answers, Mapping) and answers.get("schema_version") == "questionnaire_v2.1":
        return score_questionnaire_v21(answers)  # type: ignore[return-value]
    normalized_answers = _normalize_answers(answers)
    _validate_answers(normalized_answers)

    dimension_scores = {
        dimension: {
            "raw_score": normalized_answers[question_id],
            "normalized_score": normalized_answers[question_id] * 25,
            "source_question": question_id,
        }
        for question_id, dimension in _DIMENSION_BY_QUESTION.items()
    }
    selected_q12 = normalized_answers["q12_physical_safety"]
    return {
        "mood_metaphor": normalized_answers["q01_mood_weather"],
        "dimension_scores": dimension_scores,
        "physical_signals": [
            signal for signal in _PHYSICAL_SIGNALS if signal in selected_q12
        ],
        "safety_flags": [
            signal for signal in _SAFETY_SIGNALS if signal in selected_q12
        ],
    }


def score_questionnaire_v21(envelope: Mapping[str, Any]) -> QuestionnaireScore:
    """Validate and score the 20-question Questionnaire V2.1 contract."""
    if not isinstance(envelope, Mapping):
        raise QuestionnaireValidationError("questionnaire_v2.1 must be a mapping")
    if envelope.get("schema_version") != "questionnaire_v2.1":
        raise QuestionnaireValidationError(
            "schema_version must be questionnaire_v2.1"
        )
    if envelope.get("time_window_days") != 14:
        raise QuestionnaireValidationError("time_window_days must be 14")

    normalized = _normalize_answer_records(
        envelope.get("answers"),
        expected_ids=V21_QUESTION_IDS,
    )
    _validate_v21_values(normalized)

    dimensions: dict[str, DimensionScore] = {}
    for question_id, dimension in _V21_DIMENSION_BY_QUESTION.items():
        value = normalized[question_id]
        assert type(value) is int
        dimensions[dimension] = DimensionScore(
            raw_score=value,
            normalized_score=value * 25,
            weighted_score=value,
            source_questions=(question_id,),
            q04_qualitative=(
                normalized["q04_worry_control"]
                if dimension == "tension_worry"
                else None
            ),
        )

    safety_flags = tuple(
        flag
        for flag in _V21_SAFETY_OPTIONS
        if flag != "none" and flag in normalized["q20_safety"]
    )
    physical_signals = tuple(
        signal
        for signal in _V21_PHYSICAL_OPTIONS
        if signal in normalized["q14_physical_signals"]
    )
    return QuestionnaireScore(
        schema_version="questionnaire_v2.1",
        questions_answered=len(V21_QUESTION_IDS),
        dimension_scores=dimensions,
        physical_signals=physical_signals,
        safety_flags=safety_flags,
        qualitative={
            "goal": normalized["q01_goal"],
            "mood_state": normalized["q02_mood_state"],
            "worry_control": normalized["q04_worry_control"],
            "duration": normalized["q15_duration"],
            "change_goal": normalized["q17_change_goal"],
            "safety_context": normalized["q19_safety_context"],
        },
        source="built_in_compatibility_definition",
    )


def score_quick_state(envelope: Mapping[str, Any]) -> QuickStateScore:
    """Validate and score the six-question Quick State V1 contract."""
    if not isinstance(envelope, Mapping):
        raise QuestionnaireValidationError("quick_state_v1 must be a mapping")
    if envelope.get("schema_version") != "quick_state_v1":
        raise QuestionnaireValidationError("schema_version must be quick_state_v1")

    normalized = _normalize_answer_records(
        envelope.get("answers"),
        expected_ids=(
            "tension",
            "overthinking",
            "low_mood",
            "body_tension",
            "mental_fatigue",
            "goal",
        ),
    )
    for question_id in (
        "tension",
        "overthinking",
        "low_mood",
        "body_tension",
        "mental_fatigue",
    ):
        value = normalized[question_id]
        if type(value) is not int or not 0 <= value <= 10:
            raise QuestionnaireValidationError(
                f"{question_id} must be an integer from 0 to 10"
            )
    goal = normalized["goal"]
    if not isinstance(goal, str) or not goal.strip():
        raise QuestionnaireValidationError("goal must be a non-empty string")
    return QuickStateScore(
        schema_version="quick_state_v1",
        values={
            question_id: normalized[question_id]
            for question_id in (
                "tension",
                "overthinking",
                "low_mood",
                "body_tension",
                "mental_fatigue",
            )
        },
        goal=goal.strip(),
    )


def _normalize_answer_records(
    records: object,
    *,
    expected_ids: Sequence[str],
) -> dict[str, Any]:
    if isinstance(records, (str, bytes)) or not isinstance(records, Sequence):
        raise QuestionnaireValidationError("answers must be answer records")
    normalized: dict[str, Any] = {}
    for record in records:
        if not isinstance(record, Mapping) or "question_id" not in record or "value" not in record:
            raise QuestionnaireValidationError(
                "answer records must contain question_id and value"
            )
        question_id = record["question_id"]
        if not isinstance(question_id, str) or question_id in normalized:
            raise QuestionnaireValidationError("question_id must be unique text")
        normalized[question_id] = record["value"]
    missing = [question_id for question_id in expected_ids if question_id not in normalized]
    if missing:
        raise QuestionnaireValidationError(
            f"missing required questions: {', '.join(missing)}"
        )
    unexpected = [question_id for question_id in normalized if question_id not in expected_ids]
    if unexpected:
        raise QuestionnaireValidationError(f"unexpected question_id: {unexpected[0]}")
    if len(normalized) != len(expected_ids):
        raise QuestionnaireValidationError("answers must contain every required question once")
    return normalized


def _validate_v21_values(answers: Mapping[str, Any]) -> None:
    goal = answers["q01_goal"]
    if not isinstance(goal, str) or not goal.strip():
        raise QuestionnaireValidationError("q01_goal must be a non-empty string")
    mood = answers["q02_mood_state"]
    if not isinstance(mood, str) or mood not in _V21_MOOD_OPTIONS:
        raise QuestionnaireValidationError(f"invalid q02_mood_state: {mood}")
    for question_id in _V21_DIMENSION_BY_QUESTION:
        value = answers[question_id]
        if type(value) is not int or not 0 <= value <= 4:
            raise QuestionnaireValidationError(
                f"{question_id} must be an integer from 0 to 4"
            )
    physical = answers["q14_physical_signals"]
    if not isinstance(physical, (list, tuple)) or any(
        not isinstance(signal, str) or signal not in _V21_PHYSICAL_OPTIONS
        for signal in physical
    ):
        raise QuestionnaireValidationError("q14_physical_signals contains an invalid signal")
    safety = answers["q20_safety"]
    if not isinstance(safety, (list, tuple)) or not safety:
        raise QuestionnaireValidationError("q20_safety must be a non-empty list")
    if any(not isinstance(flag, str) or flag not in _V21_SAFETY_OPTIONS for flag in safety):
        raise QuestionnaireValidationError("q20_safety contains an invalid flag")
    if "none" in safety and len(safety) != 1:
        raise QuestionnaireValidationError("q20_safety none cannot be combined")


def _normalize_answers(
    answers: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if isinstance(answers, Mapping):
        if "schema_version" in answers or "answers" in answers:
            return _normalize_envelope(answers)
        return dict(answers)
    if isinstance(answers, (str, bytes)) or not isinstance(answers, Sequence):
        raise QuestionnaireValidationError("answers must be a mapping or answer records")

    normalized: dict[str, Any] = {}
    for record in answers:
        if not isinstance(record, Mapping) or "question_id" not in record or "value" not in record:
            raise QuestionnaireValidationError(
                "answer records must contain question_id and value"
            )
        question_id = record["question_id"]
        if question_id in normalized:
            raise QuestionnaireValidationError(f"duplicate question_id: {question_id}")
        normalized[question_id] = record["value"]
    return normalized


def _normalize_envelope(envelope: Mapping[str, Any]) -> dict[str, Any]:
    if envelope.get("schema_version") != "questionnaire_v2.0":
        raise QuestionnaireValidationError(
            "schema_version must be questionnaire_v2.0"
        )
    if envelope.get("time_window_days") != 7:
        raise QuestionnaireValidationError(
            "time_window_days must be 7"
        )
    records = envelope.get("answers")
    if isinstance(records, (str, bytes)) or not isinstance(
        records,
        Sequence,
    ):
        raise QuestionnaireValidationError(
            "answers must be answer records"
        )
    return _normalize_answers(records)


def _validate_answers(answers: Mapping[str, Any]) -> None:
    missing = [question_id for question_id in _QUESTION_IDS if question_id not in answers]
    if missing:
        raise QuestionnaireValidationError(f"missing required questions: {', '.join(missing)}")

    unexpected = [question_id for question_id in answers if question_id not in _QUESTION_IDS]
    if unexpected:
        raise QuestionnaireValidationError(f"unexpected question_id: {unexpected[0]}")

    mood = answers["q01_mood_weather"]
    if not isinstance(mood, str) or mood not in _MOOD_WEATHER_OPTIONS:
        raise QuestionnaireValidationError(f"invalid q01_mood_weather: {mood}")

    for question_id in _DIMENSION_BY_QUESTION:
        value = answers[question_id]
        if type(value) is not int or not 0 <= value <= 4:
            raise QuestionnaireValidationError(
                f"{question_id} must be an integer from 0 to 4"
            )

    selected_q12 = answers["q12_physical_safety"]
    if not isinstance(selected_q12, (list, tuple)) or not selected_q12:
        raise QuestionnaireValidationError(
            "q12_physical_safety must be a non-empty list of signals"
        )
    if any(
        not isinstance(signal, str) or signal not in _Q12_OPTIONS
        for signal in selected_q12
    ):
        invalid = next(
            signal for signal in selected_q12
            if not isinstance(signal, str) or signal not in _Q12_OPTIONS
        )
        raise QuestionnaireValidationError(f"invalid q12_physical_safety signal: {invalid}")
    if len(set(selected_q12)) != len(selected_q12):
        raise QuestionnaireValidationError("q12_physical_safety signals must be unique")
    if "none" in selected_q12 and len(selected_q12) != 1:
        raise QuestionnaireValidationError(
            "q12_physical_safety none cannot be combined with other signals"
        )
