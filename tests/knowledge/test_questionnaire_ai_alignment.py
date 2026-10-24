import json
from pathlib import Path

from backend.ai_engine import questionnaire_v2 as scorer


ROOT = Path(__file__).resolve().parents[2]


def test_ai_scorer_matches_reviewed_questionnaire_contract():
    questionnaire = json.loads(
        (ROOT / "knowledge" / "questionnaire-v2.json").read_text(encoding="utf-8")
    )
    questions = {item["question_id"]: item for item in questionnaire["questions"]}

    assert tuple(questions) == scorer._QUESTION_IDS
    assert {
        option["value"] for option in questions["q01_mood_weather"]["options"]
    } == scorer._MOOD_WEATHER_OPTIONS
    assert questions["q03_overthinking"]["scoring"]["score_map"] == (
        scorer._VISUAL_SCORE_MAPS["q03_overthinking"]
    )
    assert questions["q09_low_energy"]["scoring"]["score_map"] == (
        scorer._VISUAL_SCORE_MAPS["q09_low_energy"]
    )

    q12_values = {
        option["value"] for option in questions["q12_physical_safety"]["options"]
    }
    assert q12_values == scorer._Q12_OPTIONS


def test_visual_answers_are_scored_by_the_reviewed_maps():
    answers = {
        "q01_mood_weather": "cloudy",
        "q02_tension_worry": 2,
        "q03_overthinking": "waves",
        "q04_irritability_anger": 2,
        "q05_low_mood": 2,
        "q06_interest_loss": 2,
        "q07_fear_unease": 2,
        "q08_sleep_disturbance": 2,
        "q09_low_energy": "half",
        "q10_appetite_change": 2,
        "q11_daily_impact": 2,
        "q12_physical_safety": ["none"],
    }

    result = scorer.score_questionnaire(answers)

    assert result["dimension_scores"]["overthinking"]["raw_score"] == 2
    assert result["dimension_scores"]["overthinking"]["normalized_score"] == 50
    assert result["dimension_scores"]["low_energy"]["raw_score"] == 2
    assert result["dimension_scores"]["low_energy"]["normalized_score"] == 50
