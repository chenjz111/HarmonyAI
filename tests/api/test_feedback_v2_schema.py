import pytest
from pydantic import ValidationError

from backend.app.schemas.feedback_v2 import (
    FeedbackV2Request,
    FeedbackV2Response,
)


class AtomicRepository:
    def __init__(self):
        self.records = {}
        self.preference_updates = []

    def save_once(self, record, preference_patch):
        feedback_id = record["feedback_id"]
        if feedback_id in self.records:
            return False
        self.records[feedback_id] = record
        self.preference_updates.append(preference_patch)
        return True


def canonical_feedback(**overrides):
    payload = {
        "schema_version": "feedback_v2.0",
        "session_id": "sess-feedback",
        "prescription_id": "rx-feedback",
        "music_id": "music-gong-001",
        "pre_state": {
            "tension": 7,
            "body_tension": 6,
            "mental_fatigue": 8,
            "goal": "sleep",
        },
        "post_state": {
            "tension": 5,
            "body_tension": 4,
            "mental_fatigue": 6,
            "change_label": "slightly_better",
        },
        "experience": {
            "overall_rating": 4,
            "relaxation_rating": 4,
            "music_match_rating": 3,
            "continue_use": "yes",
            "favorite": True,
            "disliked_features": ["high_frequency"],
            "disliked_instruments": ["笛子"],
            "comment": "  整体比较放松，但笛声有一点尖。  ",
        },
        "playback": {
            "listened_seconds": 780,
            "duration_seconds": 900,
            "completion_rate": 0.87,
            "pause_count": 1,
            "skip_count": 0,
        },
    }
    payload.update(overrides)
    return payload


def test_feedback_request_accepts_canonical_nested_contract():
    request = FeedbackV2Request.model_validate(canonical_feedback())

    assert request.music_id == "music-gong-001"
    assert request.pre_state.mental_fatigue == 8
    assert request.experience.overall_rating == 4
    assert request.experience.comment == "整体比较放松，但笛声有一点尖。"


def test_feedback_request_rejects_track_id_alias():
    payload = canonical_feedback()
    payload["track_id"] = payload.pop("music_id")

    with pytest.raises(ValidationError):
        FeedbackV2Request.model_validate(payload)


def test_feedback_runtime_returns_canonical_subjective_change_and_patch():
    from backend.ai_engine.feedback_v2 import submit_feedback_v2

    repository = AtomicRepository()
    result = submit_feedback_v2(canonical_feedback(), repository)
    validated = FeedbackV2Response.model_validate(result)

    assert validated.subjective_change.model_dump() == {
        "tension_delta": -2,
        "body_tension_delta": -2,
        "mental_fatigue_delta": -2,
        "summary": "用户主观感到紧张、身体紧绷和精神疲劳有所下降。",
    }
    assert validated.decision.action == "adjust_personal_preference"
    assert validated.personal_preference_patch.model_dump() == {
        "reduce_instruments": ["笛子"],
        "reduce_high_frequency": True,
        "preserve_instruments": [],
        "favorite_tracks_add": ["music-gong-001"],
    }
    saved = next(iter(repository.records.values()))
    assert saved["music_id"] == "music-gong-001"
    assert saved["experience"]["comment"] == "整体比较放松，但笛声有一点尖。"
    assert result["global_rule_update"] is False
