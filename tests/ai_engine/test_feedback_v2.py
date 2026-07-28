class MemoryFeedbackRepository:
    def __init__(self):
        self.records = {}
        self.preference_updates = []

    def get(self, feedback_id):
        return self.records.get(feedback_id)

    def save(self, record, preference_patch):
        self.records[record["feedback_id"]] = record
        self.preference_updates.append(preference_patch)


class FailingFeedbackRepository(MemoryFeedbackRepository):
    def save(self, record, preference_patch):
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


def test_explicit_submission_saves_feedback_and_returns_only_a_personal_preference_patch():
    from backend.ai_engine.feedback_v2 import submit_feedback_v2

    repository = MemoryFeedbackRepository()

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


def test_empty_comment_is_normalized_and_valid_scores_are_preserved():
    from backend.ai_engine.feedback_v2 import submit_feedback_v2

    repository = MemoryFeedbackRepository()

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

    repository = MemoryFeedbackRepository()

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

    repository = MemoryFeedbackRepository()
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
