import json

import pytest

from backend.ai_engine.questionnaire_v2 import (
    QuestionnaireValidationError,
    score_questionnaire,
)


def complete_answers():
    return {
        "q01_mood_weather": "rainy",
        "q02_tension_worry": 0,
        "q03_overthinking": 1,
        "q04_irritability_anger": 2,
        "q05_low_mood": 3,
        "q06_interest_loss": 4,
        "q07_fear_unease": 1,
        "q08_sleep_disturbance": 2,
        "q09_low_energy": 3,
        "q10_appetite_change": 4,
        "q11_daily_impact": 0,
        "q12_physical_safety": ["neck_tension", "severe_chest_pain"],
    }


def test_scores_q2_to_q11_and_returns_each_dimension_source():
    result = score_questionnaire(complete_answers())

    assert result["mood_metaphor"] == "rainy"
    assert result["dimension_scores"] == {
        "tension_worry": {
            "raw_score": 0,
            "normalized_score": 0,
            "source_question": "q02_tension_worry",
        },
        "overthinking": {
            "raw_score": 1,
            "normalized_score": 25,
            "source_question": "q03_overthinking",
        },
        "irritability_anger": {
            "raw_score": 2,
            "normalized_score": 50,
            "source_question": "q04_irritability_anger",
        },
        "low_mood": {
            "raw_score": 3,
            "normalized_score": 75,
            "source_question": "q05_low_mood",
        },
        "interest_loss": {
            "raw_score": 4,
            "normalized_score": 100,
            "source_question": "q06_interest_loss",
        },
        "fear_unease": {
            "raw_score": 1,
            "normalized_score": 25,
            "source_question": "q07_fear_unease",
        },
        "sleep_disturbance": {
            "raw_score": 2,
            "normalized_score": 50,
            "source_question": "q08_sleep_disturbance",
        },
        "low_energy": {
            "raw_score": 3,
            "normalized_score": 75,
            "source_question": "q09_low_energy",
        },
        "appetite_change": {
            "raw_score": 4,
            "normalized_score": 100,
            "source_question": "q10_appetite_change",
        },
        "daily_impact": {
            "raw_score": 0,
            "normalized_score": 0,
            "source_question": "q11_daily_impact",
        },
    }


def test_keeps_q12_physical_and_risk_signals_separate():
    result = score_questionnaire(complete_answers())

    assert result["physical_signals"] == ["neck_tension"]
    assert result["safety_flags"] == ["severe_chest_pain"]


def test_accepts_score_boundaries_zero_and_four():
    answers = complete_answers()
    for question_id in (
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
    ):
        answers[question_id] = 0
    zero_result = score_questionnaire(answers)
    assert {item["normalized_score"] for item in zero_result["dimension_scores"].values()} == {0}

    for question_id in (
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
    ):
        answers[question_id] = 4
    max_result = score_questionnaire(answers)
    assert {item["normalized_score"] for item in max_result["dimension_scores"].values()} == {100}


def test_rejects_missing_question():
    answers = complete_answers()
    del answers["q11_daily_impact"]

    with pytest.raises(QuestionnaireValidationError, match="q11_daily_impact"):
        score_questionnaire(answers)


def test_rejects_invalid_q1_option():
    answers = complete_answers()
    answers["q01_mood_weather"] = "snowy"

    with pytest.raises(QuestionnaireValidationError, match="q01_mood_weather"):
        score_questionnaire(answers)


@pytest.mark.parametrize("invalid_value", [-1, 5, 1.5, True])
def test_rejects_non_integer_or_out_of_range_core_score(invalid_value):
    answers = complete_answers()
    answers["q02_tension_worry"] = invalid_value

    with pytest.raises(QuestionnaireValidationError, match="q02_tension_worry"):
        score_questionnaire(answers)


def test_rejects_invalid_q12_signal():
    answers = complete_answers()
    answers["q12_physical_safety"] = ["neck_tension", "unknown_signal"]

    with pytest.raises(QuestionnaireValidationError, match="unknown_signal"):
        score_questionnaire(answers)


def test_q12_none_is_mutually_exclusive_with_other_signals():
    answers = complete_answers()
    answers["q12_physical_safety"] = ["none", "fatigue"]

    with pytest.raises(QuestionnaireValidationError, match="none"):
        score_questionnaire(answers)


def test_rejects_duplicate_question_ids_in_answer_records():
    records = [
        {"question_id": question_id, "value": value}
        for question_id, value in complete_answers().items()
    ]
    records.append({"question_id": "q02_tension_worry", "value": 3})

    with pytest.raises(QuestionnaireValidationError, match="duplicate"):
        score_questionnaire(records)


def test_repeated_input_produces_identical_json_result():
    answers = complete_answers()

    first = json.dumps(score_questionnaire(answers), ensure_ascii=False, sort_keys=True)
    second = json.dumps(score_questionnaire(answers), ensure_ascii=False, sort_keys=True)

    assert first == second
