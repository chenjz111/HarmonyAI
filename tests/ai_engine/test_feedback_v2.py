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
        "feedback_id": "feedback-001",
        "session_id": "session-001",
        "user_id": "user-001",
        "before": {"tension": 8, "body_tension": 7, "fatigue": 6},
        "after": {"tension": 3, "body_tension": 4, "fatigue": 4},
        "rating": 5,
        "relaxation": 9,
        "match": 8,
        "comment": "  Calm and focused.  ",
        "is_favorite": True,
        "continue_listening": True,
        "disliked_features": ["lyrics", "fast tempo"],
        "track_id": "track-jiao-01",
    }
    payload.update(overrides)
    return payload


def test_explicit_submission_uses_one_atomic_save_once_and_returns_only_a_personal_preference_patch():
    from backend.ai_engine.feedback_v2 import submit_feedback_v2

    repository = AtomicFeedbackRepository()

    result = submit_feedback_v2(feedback_payload(), repository)

    assert result == {
        "status": "success",
        "feedback_id": "feedback-001",
        "idempotent": False,
        "deltas": {"tension": 5, "body_tension": 3, "fatigue": 2},
        "comment": "Calm and focused.",
        "personal_preference_patch": {
            "favorite_track_ids": ["track-jiao-01"],
            "continue_listening": True,
            "disliked_features": ["lyrics", "fast tempo"],
        },
        "global_rule_update": False,
    }
    assert repository.records["feedback-001"]["rating"] == 5
    assert repository.preference_updates == [
        {
            "favorite_track_ids": ["track-jiao-01"],
            "continue_listening": True,
            "disliked_features": ["lyrics", "fast tempo"],
        }
    ]
    assert repository.save_once_calls == 1


def test_empty_comment_is_normalized_and_valid_scores_are_preserved():
    from backend.ai_engine.feedback_v2 import submit_feedback_v2

    repository = AtomicFeedbackRepository()

    result = submit_feedback_v2(
        feedback_payload(comment="   ", rating=1, relaxation=0, match=10),
        repository,
    )

    assert result["status"] == "success"
    assert result["comment"] == ""
    assert repository.records["feedback-001"]["rating"] == 1
    assert repository.records["feedback-001"]["relaxation"] == 0
    assert repository.records["feedback-001"]["match"] == 10


def test_invalid_scores_are_rejected_before_persistence():
    from backend.ai_engine.feedback_v2 import submit_feedback_v2

    repository = AtomicFeedbackRepository()

    result = submit_feedback_v2(feedback_payload(rating=6), repository)

    assert result == {
        "status": "failed",
        "error_code": "INVALID_PAYLOAD",
        "field": "rating",
        "global_rule_update": False,
    }
    assert repository.records == {}
    assert repository.preference_updates == []


def test_save_failure_is_reported_without_updating_preferences():
    from backend.ai_engine.feedback_v2 import submit_feedback_v2

    repository = FailingFeedbackRepository()

    result = submit_feedback_v2(feedback_payload(), repository)

    assert result == {
        "status": "failed",
        "feedback_id": "feedback-001",
        "error_code": "PERSISTENCE_FAILED",
        "global_rule_update": False,
    }
    assert repository.records == {}
    assert repository.preference_updates == []


def test_duplicate_feedback_id_is_idempotent_and_does_not_save_twice():
    from backend.ai_engine.feedback_v2 import submit_feedback_v2

    repository = AtomicFeedbackRepository()
    first = submit_feedback_v2(feedback_payload(), repository)
    second = submit_feedback_v2(feedback_payload(comment="different text"), repository)

    assert first["status"] == "success"
    assert second == {
        "status": "success",
        "feedback_id": "feedback-001",
        "idempotent": True,
        "global_rule_update": False,
    }
    assert repository.records["feedback-001"]["comment"] == "Calm and focused."
    assert len(repository.preference_updates) == 1
    assert repository.save_once_calls == 2


@pytest.mark.parametrize(
    "scale",
    [
        "before_tension",
        "after_tension",
        "before_body_tension",
        "after_body_tension",
        "before_fatigue",
        "after_fatigue",
        "rating",
        "relaxation",
        "match",
    ],
)
@pytest.mark.parametrize("invalid_value", [math.nan, math.inf, -math.inf])
def test_all_feedback_scales_reject_non_finite_values(scale, invalid_value):
    from backend.ai_engine.feedback_v2 import submit_feedback_v2

    repository = AtomicFeedbackRepository()
    payload = feedback_payload()
    if scale == "before_tension":
        payload["before"]["tension"] = invalid_value
    elif scale == "after_tension":
        payload["after"]["tension"] = invalid_value
    elif scale == "before_body_tension":
        payload["before"]["body_tension"] = invalid_value
    elif scale == "after_body_tension":
        payload["after"]["body_tension"] = invalid_value
    elif scale == "before_fatigue":
        payload["before"]["fatigue"] = invalid_value
    elif scale == "after_fatigue":
        payload["after"]["fatigue"] = invalid_value
    else:
        payload[scale] = invalid_value

    result = submit_feedback_v2(payload, repository)

    assert result["status"] == "failed"
    assert result["error_code"] == "INVALID_PAYLOAD"
    assert repository.records == {}
    assert repository.preference_updates == []


def test_missing_after_reports_after_as_the_invalid_field():
    from backend.ai_engine.feedback_v2 import submit_feedback_v2

    result = submit_feedback_v2(
        feedback_payload(after=None),
        AtomicFeedbackRepository(),
    )

    assert result == {
        "status": "failed",
        "error_code": "INVALID_PAYLOAD",
        "field": "after",
        "global_rule_update": False,
    }
