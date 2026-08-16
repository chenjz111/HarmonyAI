import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _artifact():
    return json.loads((ROOT / "knowledge" / "questionnaire-v2.2.json").read_text(encoding="utf-8"))


def _question(artifact, question_id):
    return next(question for question in artifact["questions"] if question["question_id"] == question_id)


def test_v22_artifact_changes_only_approved_question_shapes_and_keeps_safety():
    artifact = _artifact()
    assert artifact["schema_version"] == "questionnaire_v2.2"
    assert artifact["total_questions"] == 20

    q1 = _question(artifact, "q01_user_goal")
    assert q1["type"] == "goal_selection"
    assert q1["max_selections"] == 2
    assert q1["primary_required"] is True

    q14 = _question(artifact, "q14_low_energy")
    assert [(option["value"], option["score"]) for option in q14["options"]] == [
        ("full", 0), ("three_quarters", 1), ("half", 2), ("quarter", 3), ("empty", 4)
    ]
    assert all(not option["icon"].startswith("battery-") for option in q14["options"])

    q16 = _question(artifact, "q16_physical_signals")
    assert q16["custom_text_for"] == "other"
    assert q16["mutually_exclusive_value"] == "none"

    q19 = _question(artifact, "q19_self_harm")
    q20 = _question(artifact, "q20_emergency")
    assert q19["safety_only"] is True and q19["scored"] is False and q19["weight"] == 0
    assert q20["safety_only"] is True and q20["scored"] is False and q20["weight"] == 0

