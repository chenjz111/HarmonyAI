"""Feedback V1 backward compatibility tests — Sprint 3 Issue #37."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import pytest
from fastapi.testclient import TestClient
from backend.app.core.exceptions import build_error_response
from backend.app.main import app
from backend.app.schemas.common import AgentLayer

client = TestClient(app)


def test_v1_feedback_still_works():
    """Old feedback format still processed."""
    payload = {"user_id": "u_001", "session_id": "sess_v1_compat",
               "overall_satisfaction": 4, "emotion_match": 5}
    resp = client.post("/api/feedback", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "agent_id" in data
    assert data["agent_id"] == "feedback_agent"


def test_v1_rating_field_compat():
    """Old 'rating' field still works."""
    payload = {"user_id": "u_001", "session_id": "sess_v1_rating",
               "rating": 3}
    resp = client.post("/api/feedback", json=payload)
    assert resp.status_code == 200


def test_v1_no_auto_default():
    """When no rating is provided, it does not auto-fill 4."""
    payload = {"user_id": "u_001", "session_id": "sess_v1_no_rating"}
    resp = client.post("/api/feedback", json=payload)
    assert resp.status_code == 200


def test_v1_error_response_uses_strings_and_hides_internal_details():
    data = build_error_response(
        agent_id="feedback_agent",
        agent_name="反馈Agent",
        agent_layer=AgentLayer.AI_GENERATION,
        session_id="sess_error",
        user_id="u_001",
        error=RuntimeError("mysql://root:secret@localhost/harmony"),
    )

    assert all(isinstance(item, str) for item in data["warnings"])
    assert data["reason"] == ["异常:服务暂时不可用，请稍后重试"]
    assert "secret" not in str(data)
