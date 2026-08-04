import math

import pytest


class AtomicFeedbackRepository:
    def __init__(self):
        self.records = {}
        self.preference_updates = []
        self.save_once_calls = 0

    def save_once(self, record, preference_patch):
        self.save_once_calls += 1
        if record["feedback_id"] in self.records:
            return False
        self.records[record["feedback_id"]] = record
        self.preference_updates.append(preference_patch)
        return True


class FailingFeedbackRepository(AtomicFeedbackRepository):
    def save_once(self, record, preference_patch):
        del record, preference_patch
        raise OSError("database unavailable")


def feedback_payload(**overrides):
    payload = {
        "schema_version": "feedback_v2.0",
        "session_id": "session-001",
        "prescription_id": "prescription-001",
        "music_id": "music-jiao-01",
        "pre_state": {
            "tension": 8,
            "body_tension": 7,
            "mental_fatigue": 6,
            "goal": "relax",
        },
        "post_state": {
            "tension": 3,
            "body_tension": 4,
            "mental_fatigue": 4,
            "change_label": "much_better",
        },
        "experience": {
            "overall_rating": 5,
            "relaxation_rating": 5,
            "music_match_rating": 4,
            "continue_use": "yes",
            "favorite": True,
            "disliked_features": ["high_frequency"],
            "disliked_instruments": ["flute"],
            "comment": "  Calm and focused.  ",
        },
        "playback": {
            "listened_seconds": 840,
            "duration_seconds": 900,
            "completion_rate": 0.93,
            "pause_count": 0,
            "skip_count": 0,
        },
    }
    payload.update(overrides)
    return payload


def test_explicit_submission_uses_one_atomic_save_once_and_returns_only_a_personal_preference_patch():
    from backend.ai_engine.feedback_v2 import submit_feedback_v2

    repository = AtomicFeedbackRepository()

    result = submit_feedback_v2(feedback_payload(), repository)

    assert result["status"] == "success"
    assert result["agent_id"] == "feedback_agent"
    assert result["idempotent"] is False
    assert result["subjective_change"] == {
        "tension_delta": -5,
        "body_tension_delta": -3,
        "mental_fatigue_delta": -2,
        "summary": result["subjective_change"]["summary"],
    }
    assert result["experience_summary"] == {
        "overall_rating": 5,
        "relaxation_rating": 5,
        "music_match_rating": 4,
        "continue_use": "yes",
        "favorite": True,
    }
    assert result["personal_preference_patch"] == {
        "reduce_instruments": ["flute"],
        "reduce_high_frequency": True,
        "preserve_instruments": [],
        "favorite_tracks_add": ["music-jiao-01"],
    }
    assert result["global_rule_update"] is False
    feedback_id = result["feedback_id"]
    assert repository.records[feedback_id]["music_id"] == "music-jiao-01"
    assert repository.records[feedback_id]["experience"]["comment"] == "Calm and focused."
    assert repository.preference_updates == [
        {
            "reduce_instruments": ["flute"],
            "reduce_high_frequency": True,
            "preserve_instruments": [],
            "favorite_tracks_add": ["music-jiao-01"],
        }
    ]
    assert repository.save_once_calls == 1


def test_empty_comment_is_normalized_and_valid_scores_are_preserved():
    from backend.ai_engine.feedback_v2 import submit_feedback_v2

    repository = AtomicFeedbackRepository()

    payload = feedback_payload()
    payload["experience"].update(
        comment="   ",
        overall_rating=1,
        relaxation_rating=1,
        music_match_rating=5,
    )
    result = submit_feedback_v2(payload, repository)

    assert result["status"] == "success"
    record = repository.records[result["feedback_id"]]
    assert record["experience"]["comment"] == ""
    assert record["experience"]["overall_rating"] == 1
    assert record["experience"]["relaxation_rating"] == 1
    assert record["experience"]["music_match_rating"] == 5


def test_invalid_scores_are_rejected_before_persistence():
    from backend.ai_engine.feedback_v2 import submit_feedback_v2

    repository = AtomicFeedbackRepository()

    payload = feedback_payload()
    payload["experience"]["overall_rating"] = 6
    result = submit_feedback_v2(payload, repository)

    assert result == {
        "agent_id": "feedback_agent",
        "status": "failed",
        "error_code": "INVALID_PAYLOAD",
        "field": "experience",
        "global_rule_update": False,
    }
    assert repository.records == {}
    assert repository.preference_updates == []


def test_save_failure_is_reported_without_updating_preferences():
    from backend.ai_engine.feedback_v2 import submit_feedback_v2

    repository = FailingFeedbackRepository()

    result = submit_feedback_v2(feedback_payload(), repository)

    assert result["status"] == "failed"
    assert result["feedback_id"].startswith("fb_")
    assert result["error_code"] == "PERSISTENCE_FAILED"
    assert result["global_rule_update"] is False
    assert repository.records == {}
    assert repository.preference_updates == []


def test_duplicate_feedback_id_is_idempotent_and_does_not_save_twice():
    from backend.ai_engine.feedback_v2 import submit_feedback_v2

    repository = AtomicFeedbackRepository()
    first = submit_feedback_v2(feedback_payload(), repository)
    duplicate = feedback_payload()
    duplicate["experience"]["comment"] = "different text"
    second = submit_feedback_v2(duplicate, repository)

    assert first["status"] == "success"
    assert second["status"] == "success"
    assert second["feedback_id"] == first["feedback_id"]
    assert second["idempotent"] is True
    assert second["global_rule_update"] is False
    assert (
        repository.records[first["feedback_id"]]["experience"]["comment"]
        == "Calm and focused."
    )
    assert len(repository.preference_updates) == 1
    assert repository.save_once_calls == 2


@pytest.mark.parametrize(
    "scale",
    [
        "pre_tension",
        "post_tension",
        "pre_body_tension",
        "post_body_tension",
        "pre_mental_fatigue",
        "post_mental_fatigue",
        "overall_rating",
        "relaxation_rating",
        "music_match_rating",
        "completion_rate",
    ],
)
@pytest.mark.parametrize("invalid_value", [math.nan, math.inf, -math.inf])
def test_all_feedback_scales_reject_non_finite_values(scale, invalid_value):
    from backend.ai_engine.feedback_v2 import submit_feedback_v2

    repository = AtomicFeedbackRepository()
    payload = feedback_payload()
    if scale == "pre_tension":
        payload["pre_state"]["tension"] = invalid_value
    elif scale == "post_tension":
        payload["post_state"]["tension"] = invalid_value
    elif scale == "pre_body_tension":
        payload["pre_state"]["body_tension"] = invalid_value
    elif scale == "post_body_tension":
        payload["post_state"]["body_tension"] = invalid_value
    elif scale == "pre_mental_fatigue":
        payload["pre_state"]["mental_fatigue"] = invalid_value
    elif scale == "post_mental_fatigue":
        payload["post_state"]["mental_fatigue"] = invalid_value
    elif scale == "completion_rate":
        payload["playback"]["completion_rate"] = invalid_value
    else:
        payload["experience"][scale] = invalid_value

    result = submit_feedback_v2(payload, repository)

    assert result["status"] == "failed"
    assert result["error_code"] == "INVALID_PAYLOAD"
    assert repository.records == {}
    assert repository.preference_updates == []


def test_missing_post_state_reports_post_state_as_the_invalid_field():
    from backend.ai_engine.feedback_v2 import submit_feedback_v2

    result = submit_feedback_v2(
        feedback_payload(post_state=None),
        AtomicFeedbackRepository(),
    )

    assert result == {
        "agent_id": "feedback_agent",
        "status": "failed",
        "error_code": "INVALID_PAYLOAD",
        "field": "post_state",
        "global_rule_update": False,
    }


def test_short_exposure_adds_warning_and_never_updates_global_rules():
    from backend.ai_engine.feedback_v2 import submit_feedback_v2

    payload = feedback_payload()
    payload["playback"]["listened_seconds"] = 20
    result = submit_feedback_v2(payload, AtomicFeedbackRepository())

    assert result["warnings"] == ["SHORT_EXPOSURE"]
    assert result["global_rule_update"] is False
    assert "track_id" not in result
