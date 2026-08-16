from backend.ai_engine.feedback_v2 import submit_feedback_v2
from tests.ai_engine.test_feedback_v2 import AtomicFeedbackRepository


def minimal_feedback(change_label: str = "no_change") -> dict[str, object]:
    return {
        "schema_version": "feedback_v2.0",
        "session_id": "session-minimal",
        "prescription_id": "prescription-minimal",
        "music_id": "music-minimal",
        "post_state": {"change_label": change_label},
    }


def test_only_change_label_is_required_for_feedback_submission():
    repository = AtomicFeedbackRepository()

    result = submit_feedback_v2(minimal_feedback("slightly_better"), repository)

    assert result["status"] == "success"
    assert result["subjective_change"]["tension_delta"] is None
    assert result["experience_summary"]["overall_rating"] is None
    assert result["global_rule_update"] is False


def test_missing_change_label_is_rejected():
    payload = minimal_feedback()
    payload["post_state"] = {}

    result = submit_feedback_v2(payload, AtomicFeedbackRepository())

    assert result["status"] == "failed"
    assert result["field"] == "post_state"


def test_positive_and_adjustment_preferences_update_only_personal_patch():
    payload = minimal_feedback("much_better")
    payload["experience"] = {
        "liked_features": ["古琴", "节奏舒缓"],
        "adjustment_preferences": ["下次更慢一些"],
        "comment": "页面清楚，音乐让我放松了一点。",
    }

    result = submit_feedback_v2(payload, AtomicFeedbackRepository())

    assert result["personal_preference_patch"]["preferred_features"] == ["古琴", "节奏舒缓"]
    assert result["personal_preference_patch"]["adjustment_preferences"] == ["下次更慢一些"]
    assert result["global_rule_update"] is False
