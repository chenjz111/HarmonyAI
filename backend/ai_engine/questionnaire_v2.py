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

FROZEN_V21_QUESTION_IDS = (
    "q01_user_goal", "q02_mood_weather", "q03_tension_worry", "q04_worry_control",
    "q05_overthinking", "q06_irritability_anger", "q07_fear_unease", "q08_low_mood",
    "q09_interest_loss", "q10_calm_wellbeing", "q11_emotional_recovery",
    "q12_sleep_disturbance", "q13_unrefreshing_sleep", "q14_low_energy",
    "q15_appetite_change", "q16_physical_signals", "q17_duration", "q18_daily_impact",
    "q19_self_harm", "q20_emergency",
)
_FROZEN_V21_DIMENSIONS = {
    "q03_tension_worry": "tension_worry",
    "q05_overthinking": "overthinking",
    "q06_irritability_anger": "irritability_anger",
    "q07_fear_unease": "fear_unease",
    "q08_low_mood": "low_mood",
    "q09_interest_loss": "interest_loss",
    "q10_calm_wellbeing": "calm_wellbeing",
    "q11_emotional_recovery": "emotional_recovery",
    "q12_sleep_disturbance": "sleep_disturbance",
    "q13_unrefreshing_sleep": "unrefreshing_sleep",
    "q14_low_energy": "low_energy",
    "q15_appetite_change": "appetite_change",
    "q18_daily_impact": "daily_impact",
}
_FROZEN_VISUAL_SCORES = {"calm": 0, "ripple": 1, "waves": 2, "swell": 3, "storm": 4}
_FROZEN_ENERGY_SCORES = {"full": 0, "half": 2, "empty": 4}
_FROZEN_SAFETY_FLAGS = {"fleeting", "sometimes", "often", "specific_plan"}
_FROZEN_EMERGENCY_FLAGS = {
    "severe_chest_pain", "severe_breathing_difficulty", "confusion", "near_fainting", "rapid_worsening",
}

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

_VISUAL_SCORE_MAPS = {
    "q03_overthinking": {
        "calm": 0,
        "ripple": 1,
        "waves": 2,
        "swell": 3,
        "storm": 4,
    },
    "q09_low_energy": {
        "full": 0,
        "three_quarters": 1,
        "half": 2,
        "quarter": 3,
        "empty": 4,
    },
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

    dimension_scores = {}
    for question_id, dimension in _DIMENSION_BY_QUESTION.items():
        raw_score = _raw_dimension_value(question_id, normalized_answers[question_id])
        dimension_scores[dimension] = {
            "raw_score": raw_score,
            "normalized_score": raw_score * 25,
            "source_question": question_id,
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

    raw_records = envelope.get("answers")
    if isinstance(raw_records, Sequence) and any(
        isinstance(record, Mapping) and record.get("question_id") == "q01_user_goal"
        for record in raw_records
    ):
        return _score_frozen_questionnaire_v21(envelope)

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


def _score_frozen_questionnaire_v21(envelope: Mapping[str, Any]) -> QuestionnaireScore:
    normalized = _normalize_answer_records(
        envelope.get("answers"), expected_ids=FROZEN_V21_QUESTION_IDS
    )
    _validate_frozen_v21_values(normalized)
    dimensions: dict[str, DimensionScore] = {}
    for question_id, dimension in _FROZEN_V21_DIMENSIONS.items():
        value = normalized[question_id]
        raw_score = _frozen_raw_score(question_id, value)
        dimensions[dimension] = DimensionScore(
            raw_score=raw_score,
            normalized_score=raw_score * 25,
            weighted_score=raw_score,
            source_questions=(question_id,),
            q04_qualitative=normalized["q04_worry_control"] if dimension == "tension_worry" else None,
        )
    physical = tuple(normalized["q16_physical_signals"])
    safety_flags: list[str] = []
    if normalized["q19_self_harm"] in _FROZEN_SAFETY_FLAGS:
        safety_flags.append("self_harm_thoughts")
    safety_flags.extend(
        flag for flag in normalized["q20_emergency"] if flag in _FROZEN_EMERGENCY_FLAGS
    )
    return QuestionnaireScore(
        schema_version="questionnaire_v2.1",
        questions_answered=20,
        dimension_scores=dimensions,
        physical_signals=physical,
        safety_flags=tuple(safety_flags),
        qualitative={
            "goal": normalized["q01_user_goal"],
            "mood_state": normalized["q02_mood_weather"],
            "worry_control": normalized["q04_worry_control"],
            "appetite_change": normalized["q15_appetite_change"],
            "physical_signals": physical,
            "duration": normalized["q17_duration"],
            "daily_impact": normalized["q18_daily_impact"],
            "self_harm": normalized["q19_self_harm"],
            "emergency": tuple(normalized["q20_emergency"]),
        },
        source="frozen_contract_compatibility_definition",
    )


def _frozen_raw_score(question_id: str, value: object) -> int:
    if question_id == "q10_calm_wellbeing":
        return 4 - int(value)
    if question_id == "q05_overthinking":
        return _FROZEN_VISUAL_SCORES[str(value)]
    if question_id == "q14_low_energy":
        return _FROZEN_ENERGY_SCORES[str(value)]
    if question_id == "q15_appetite_change":
        return int(value["severity"])  # type: ignore[index]
    return int(value)


def _validate_frozen_v21_values(answers: Mapping[str, Any]) -> None:
    if answers["q01_user_goal"] not in {"relaxation", "sleep", "calm_irritability", "improve_low_mood", "focus", "restore_energy", "release_emotion", "other"}:
        raise QuestionnaireValidationError("invalid q01_user_goal")
    if answers["q02_mood_weather"] not in {"clear", "variable", "rainy", "fog", "storm"}:
        raise QuestionnaireValidationError("invalid q02_mood_weather")
    for question_id in _FROZEN_V21_DIMENSIONS:
        value = answers[question_id]
        if question_id in {"q05_overthinking", "q14_low_energy"}:
            if not isinstance(value, str):
                raise QuestionnaireValidationError(f"{question_id} must be a visual option")
        elif question_id == "q15_appetite_change":
            if not isinstance(value, Mapping) or value.get("direction") not in {"increase", "decrease", "none"} or type(value.get("severity")) is not int or not 0 <= value["severity"] <= 4 or (value["direction"] == "none" and value["severity"] != 0):
                raise QuestionnaireValidationError("invalid q15_appetite_change")
        elif type(value) is not int or not 0 <= value <= 4:
            raise QuestionnaireValidationError(f"{question_id} must be an integer from 0 to 4")
    physical = answers["q16_physical_signals"]
    allowed_physical = {"neck_tension", "head_heaviness", "palpitation", "chest_tightness", "stomach_discomfort", "limb_fatigue", "cold_extremities", "sweating", "dry_mouth", "none", "other"}
    if not isinstance(physical, (list, tuple)) or not physical or any(item not in allowed_physical for item in physical) or ("none" in physical and len(physical) != 1) or len(set(physical)) != len(physical):
        raise QuestionnaireValidationError("invalid q16_physical_signals")
    if answers["q17_duration"] not in {"less_than_3_days", "3_to_6_days", "1_to_2_weeks", "2_weeks_to_1_month", "1_to_3_months", "over_3_months", "recurrent_unclear"}:
        raise QuestionnaireValidationError("invalid q17_duration")
    if type(answers["q18_daily_impact"]) is not int or not 0 <= answers["q18_daily_impact"] <= 4:
        raise QuestionnaireValidationError("invalid q18_daily_impact")
    if answers["q19_self_harm"] not in {"never", "fleeting", "sometimes", "often", "specific_plan"}:
        raise QuestionnaireValidationError("invalid q19_self_harm")
    emergency = answers["q20_emergency"]
    if not isinstance(emergency, (list, tuple)) or not emergency or any(item not in _FROZEN_EMERGENCY_FLAGS | {"none"} for item in emergency) or len(set(emergency)) != len(emergency) or ("none" in emergency and len(emergency) != 1):
        raise QuestionnaireValidationError("invalid q20_emergency")


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
        if question_id in _VISUAL_SCORE_MAPS:
            valid_visual = isinstance(value, str) and value in _VISUAL_SCORE_MAPS[question_id]
            valid_legacy_number = type(value) is int and 0 <= value <= 4
            if not valid_visual and not valid_legacy_number:
                raise QuestionnaireValidationError(
                    f"{question_id} must be a valid visual option"
                )
        elif type(value) is not int or not 0 <= value <= 4:
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


def _raw_dimension_value(question_id: str, value: Any) -> int:
    """Map visual choices to their reviewed 0-4 score; retain numeric v2 compatibility."""
    if question_id in _VISUAL_SCORE_MAPS and isinstance(value, str):
        return _VISUAL_SCORE_MAPS[question_id][value]
    return value
