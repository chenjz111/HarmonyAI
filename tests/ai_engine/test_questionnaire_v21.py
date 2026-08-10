import pytest

from backend.ai_engine.questionnaire_v2 import (
    V21_QUESTION_IDS,
    score_questionnaire_v21,
    score_quick_state,
)


def valid_v21_envelope():
    values = {question_id: 0 for question_id in V21_QUESTION_IDS}
    values["q01_goal"] = "relax"
    values["q02_mood_state"] = "cloudy"
    values["q03_tension_frequency"] = 4
    values["q04_worry_control"] = 4
    values["q14_physical_signals"] = []
    values["q15_duration"] = "1-2周"
    values["q17_change_goal"] = "relax"
    values["q19_safety_context"] = "none"
    values["q20_safety"] = ["none"]
    return {
        "schema_version": "questionnaire_v2.1",
        "time_window_days": 14,
        "answers": [
            {"question_id": question_id, "value": value}
            for question_id, value in values.items()
        ],
    }


def valid_quick_state_envelope():
    return {
        "schema_version": "quick_state_v1",
        "answers": [
            {"question_id": "tension", "value": 8},
            {"question_id": "overthinking", "value": 6},
            {"question_id": "low_mood", "value": 2},
            {"question_id": "body_tension", "value": 7},
            {"question_id": "mental_fatigue", "value": 5},
            {"question_id": "goal", "value": "relax"},
        ],
    }


def test_v21_dispatch_scores_twenty_questions_without_using_q04_twice():
    result = score_questionnaire_v21(valid_v21_envelope())

    assert result.schema_version == "questionnaire_v2.1"
    assert result.questions_answered == 20
    assert result.dimension_scores["tension_worry"].q04_qualitative == 4
    assert result.dimension_scores["tension_worry"].weighted_score == 4


def test_quick_state_requires_six_items_and_0_to_10_values():
    result = score_quick_state(valid_quick_state_envelope())

    assert result.schema_version == "quick_state_v1"
    assert result.values["tension"] == 8
    assert result.goal == "relax"


def frozen_v21_envelope(*, self_harm="never", emergency=None):
    values = {
        "q01_user_goal": "relaxation",
        "q02_mood_weather": "clear",
        "q03_tension_worry": 1,
        "q04_worry_control": 4,
        "q05_overthinking": "calm",
        "q06_irritability_anger": 0,
        "q07_fear_unease": 0,
        "q08_low_mood": 0,
        "q09_interest_loss": 0,
        "q10_calm_wellbeing": 4,
        "q11_emotional_recovery": 1,
        "q12_sleep_disturbance": 2,
        "q13_unrefreshing_sleep": 1,
        "q14_low_energy": "half",
        "q15_appetite_change": {"direction": "none", "severity": 0},
        "q16_physical_signals": ["neck_tension"],
        "q17_duration": "1_to_2_weeks",
        "q18_daily_impact": 1,
        "q19_self_harm": self_harm,
        "q20_emergency": emergency or ["none"],
    }
    return {
        "schema_version": "questionnaire_v2.1",
        "time_window_days": 14,
        "answers": [{"question_id": key, "value": value} for key, value in values.items()],
    }


def test_frozen_v21_ids_preserve_q04_qualitative_q15_direction_and_reverse_score():
    from backend.ai_engine.questionnaire_v2 import score_questionnaire_v21

    result = score_questionnaire_v21(frozen_v21_envelope())

    assert result.questions_answered == 20
    assert result.dimension_scores["tension_worry"].q04_qualitative == 4
    assert result.dimension_scores["calm_wellbeing"].raw_score == 0
    assert result.qualitative["appetite_change"] == {"direction": "none", "severity": 0}
    assert result.physical_signals == ("neck_tension",)


@pytest.mark.parametrize("answer", ["fleeting", "sometimes", "often", "specific_plan"])
def test_frozen_q19_non_never_is_safety(answer):
    from backend.ai_engine.questionnaire_v2 import score_questionnaire_v21

    assert "self_harm_thoughts" in score_questionnaire_v21(
        frozen_v21_envelope(self_harm=answer)
    ).safety_flags


def test_frozen_q20_emergency_and_none_are_mutually_exclusive():
    from backend.ai_engine.questionnaire_v2 import score_questionnaire_v21, QuestionnaireValidationError

    with pytest.raises(QuestionnaireValidationError):
        score_questionnaire_v21(
            frozen_v21_envelope(emergency=["none", "confusion"])
        )
