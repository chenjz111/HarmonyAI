"""Feedback 2.0 API tests — Sprint 3 Issue #37."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import pytest
from fastapi.testclient import TestClient
from backend.app.core.database import get_db
from backend.app.main import app

client = TestClient(app)


def test_v2_feedback_submits():
    """Feedback 2.0 can be submitted with pre/post state."""
    payload = {
        "schema_version": "feedback_v2.0",
        "session_id": "sess_test_v2",
        "prescription_id": "rx_test_v2",
        "music_id": "gong_001",
        "pre_state": {"tension": 7, "body_tension": 6, "mental_fatigue": 8, "goal": "sleep"},
        "post_state": {"tension": 5, "body_tension": 4, "mental_fatigue": 6, "change_label": "slightly_better"},
        "experience": {"overall_rating": 4, "relaxation_rating": 4, "music_match_rating": 3,
                       "continue_use": "yes", "favorite": True, "disliked_features": []},
        "playback": {"listened_seconds": 780, "duration_seconds": 900,
                     "completion_rate": 0.87, "pause_count": 1, "skip_count": 0},
    }
    resp = client.post("/api/v2/feedback", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "feedback_id" in data["data"]
    assert data["data"]["subjective_change"]["tension_delta"] == -2
    assert data["data"]["global_rule_update"] is False


def test_v2_validation_rejects_invalid():
    """Invalid fields rejected via Pydantic."""
    payload = {"session_id": "s_test", "pre_state": {"tension": 20}}  # 20 > 10
    data = client.post("/api/v2/feedback", json=payload).json()
    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"

    payload2 = {
        "schema_version": "feedback_v2.0",
        "session_id": "s_test",
        "prescription_id": "rx_invalid",
        "music_id": "music_invalid",
        "pre_state": {"tension": 5, "goal": "relax"},
        "post_state": {"tension": 5, "change_label": "no_change"},
        "experience": {
            "overall_rating": 9,
            "relaxation_rating": 4,
            "music_match_rating": 4,
            "continue_use": "yes",
            "favorite": False,
        },
    }
    data2 = client.post("/api/v2/feedback", json=payload2).json()
    assert data2["success"] is False
    assert data2["error"]["code"] == "VALIDATION_ERROR"


def test_v2_no_default_rating():
    """When user does NOT submit a rating, system does NOT auto-fill 4 stars."""
    payload = {
        "schema_version": "feedback_v2.0",
        "session_id": "s_test_no_rating",
        "prescription_id": "rx_no_rating",
        "music_id": "music_no_rating",
        "pre_state": {"tension": 5, "body_tension": 5, "mental_fatigue": 5, "goal": "relax"},
        "post_state": {"tension": 4, "body_tension": 4, "mental_fatigue": 4, "change_label": "no_change"},
        "experience": {"continue_use": "yes", "favorite": False, "disliked_features": []},
    }
    resp = client.post("/api/v2/feedback", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_v2_feedback_error_does_not_leak_internal_details():
    class FailingDb:
        def query(self, *_args, **_kwargs):
            raise RuntimeError("mysql://root:secret@localhost/harmony")

        def rollback(self):
            pass

    def failing_db():
        yield FailingDb()

    app.dependency_overrides[get_db] = failing_db
    try:
        payload = {
            "schema_version": "feedback_v2.0",
            "session_id": "sess_private_error",
            "prescription_id": "rx_private_error",
            "music_id": "music_private_error",
            "pre_state": {
                "tension": 5,
                "body_tension": 5,
                "mental_fatigue": 5,
                "goal": "relax",
            },
            "post_state": {
                "tension": 4,
                "body_tension": 4,
                "mental_fatigue": 4,
                "change_label": "no_change",
            },
            "experience": {
                "overall_rating": 4,
                "relaxation_rating": 4,
                "music_match_rating": 4,
                "continue_use": "yes",
                "favorite": False,
            },
        }
        data = client.post("/api/v2/feedback", json=payload).json()
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert data["success"] is False
    assert data["error"]["code"] == "FEEDBACK_FAILED"
    assert data["error"]["message"] == "反馈保存失败，请稍后重试"
    assert "secret" not in str(data)
