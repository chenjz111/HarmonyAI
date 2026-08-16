import copy

import pytest

from backend.ai_engine.questionnaire_v2 import (
    QuestionnaireValidationError,
    score_questionnaire,
)


def valid_v22_envelope():
    values = {
        "q01_user_goal": {
            "primary_goal": "relaxation",
            "secondary_goal": "sleep",
            "custom_goal_text": None,
        },
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
        "q14_low_energy": "three_quarters",
        "q15_appetite_change": {"direction": "none", "severity": 0},
        "q16_physical_signals": {
            "selected": ["neck_tension", "other"],
            "custom_text": "耳鸣",
        },
        "q17_duration": "1_to_2_weeks",
        "q18_daily_impact": 1,
        "q19_self_harm": "never",
        "q20_emergency": ["none"],
    }
    return {
        "schema_version": "questionnaire_v2.2",
        "time_window_days": 14,
        "answers": [
            {"question_id": question_id, "value": value}
            for question_id, value in values.items()
        ],
    }


def _set_answer(envelope, question_id, value):
    changed = copy.deepcopy(envelope)
    next(item for item in changed["answers"] if item["question_id"] == question_id)["value"] = value
    return changed


def test_v22_scores_five_energy_levels_and_preserves_supplemental_physical_text():
    result = score_questionnaire(valid_v22_envelope())

    assert result.schema_version == "questionnaire_v2.2"
    assert result.dimension_scores["low_energy"].raw_score == 1
    assert result.physical_signals == ("neck_tension", "other")
    assert result.qualitative["physical_signal_text"] == "耳鸣"
    assert result.qualitative["goal"] == {
        "primary_goal": "relaxation",
        "secondary_goal": "sleep",
        "custom_goal_text": None,
    }


@pytest.mark.parametrize("battery, expected", [
    ("full", 0),
    ("three_quarters", 1),
    ("half", 2),
    ("quarter", 3),
    ("empty", 4),
])
def test_v22_energy_direction_is_low_energy_reverse_mapping(battery, expected):
    result = score_questionnaire(
        _set_answer(valid_v22_envelope(), "q14_low_energy", battery)
    )
    assert result.dimension_scores["low_energy"].raw_score == expected


@pytest.mark.parametrize("goal", [
    {"primary_goal": "relaxation", "secondary_goal": "relaxation", "custom_goal_text": None},
    {"primary_goal": "other", "secondary_goal": None, "custom_goal_text": None},
    {"primary_goal": "relaxation", "secondary_goal": "other", "custom_goal_text": ""},
])
def test_v22_rejects_invalid_goal_selection(goal):
    with pytest.raises(QuestionnaireValidationError):
        score_questionnaire(_set_answer(valid_v22_envelope(), "q01_user_goal", goal))


@pytest.mark.parametrize("physical", [
    {"selected": ["none", "neck_tension"], "custom_text": None},
    {"selected": ["other"], "custom_text": None},
    {"selected": ["neck_tension", "neck_tension"], "custom_text": None},
])
def test_v22_rejects_invalid_physical_selection(physical):
    with pytest.raises(QuestionnaireValidationError):
        score_questionnaire(
            _set_answer(valid_v22_envelope(), "q16_physical_signals", physical)
        )


@pytest.mark.parametrize("self_harm", ["fleeting", "sometimes", "often", "specific_plan"])
def test_v22_preserves_frozen_q19_safety(self_harm):
    result = score_questionnaire(
        _set_answer(valid_v22_envelope(), "q19_self_harm", self_harm)
    )
    assert "self_harm_thoughts" in result.safety_flags

