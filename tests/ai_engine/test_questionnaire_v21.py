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
