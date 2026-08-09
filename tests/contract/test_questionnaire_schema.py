"""Backward-compatibility checks for the shipped V2.0 questionnaire."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_v20() -> dict:
    return json.loads((ROOT / "knowledge" / "questionnaire-v2.json").read_text(encoding="utf-8"))


def test_v20_schema_and_question_ids_remain_stable() -> None:
    questionnaire = load_v20()
    questions = questionnaire["questions"]
    assert questionnaire["schema_version"] == "questionnaire_v2.0"
    assert len(questions) == 12
    assert len({question["question_id"] for question in questions}) == 12


def test_v20_frequency_questions_use_complete_zero_to_four_scale() -> None:
    for question in load_v20()["questions"]:
        if question["type"] == "frequency_0_4":
            assert {option["value"] for option in question["options"]} == {0, 1, 2, 3, 4}


def test_v20_visual_options_keep_semantic_values() -> None:
    visual_questions = [q for q in load_v20()["questions"] if q["type"].startswith("visual_")]
    assert visual_questions
    for question in visual_questions:
        assert all(isinstance(option["value"], str) and option["value"] for option in question["options"])


def test_v20_q12_retains_physical_safety_and_exclusion_categories() -> None:
    q12 = next(q for q in load_v20()["questions"] if q["question_id"] == "q12_physical_safety")
    categories = {option["category"] for option in q12["options"]}
    assert categories == {"physical_signal", "safety_risk", "exclusion"}
    safety_values = {o["value"] for o in q12["options"] if o["category"] == "safety_risk"}
    assert safety_values == {"severe_chest_pain", "severe_breathing_difficulty", "self_harm_thoughts"}
