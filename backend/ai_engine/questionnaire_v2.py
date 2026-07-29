from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class QuestionnaireValidationError(ValueError):
    """Raised when Questionnaire V2 answers do not match its fixed contract."""


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
