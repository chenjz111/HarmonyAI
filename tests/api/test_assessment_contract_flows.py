from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.main import app
from tests.ai_engine.test_questionnaire_v21 import valid_v21_envelope


client = TestClient(app)


def create_assessment(with_follow_up=False):
    suffix = uuid4().hex[:10]
    session_id = f"session-contract-{suffix}"
    payload = {
        "session_id": session_id,
        "user_id": f"user-contract-{suffix}",
        "questionnaire_answers": valid_v21_envelope(),
    }
    if with_follow_up:
        payload["narrative_text"] = "Recent changes; duration is unclear."
    response = client.post("/api/v2/assessments", json=payload)
    body = response.json()
    assert response.status_code == 200
    assert body["success"] is True
    assessment = body["data"]
    assert assessment["revision"] == 1
    return assessment["assessment_id"], session_id, assessment


def assert_revision_shape(item):
    assert set(item) >= {
        "assessment_id", "revision", "previous_revision",
        "created_at", "change_summary", "changes",
    }
    assert isinstance(item["changes"], list)
    assert all(set(change) == {"field", "from", "to"} for change in item["changes"])


def test_follow_up_answers_create_revision_and_user_follow_up_evidence():
    assessment_id, _, assessment = create_assessment(with_follow_up=True)
    question = assessment["follow_up_questions"][0]
    body = client.post(
        f"/api/v2/assessments/{assessment_id}/follow-up",
        json={
            "revision": 1,
            "answers": [{
                "follow_up_id": question["follow_up_id"],
                "answer": "one-to-two-weeks",
            }],
        },
    ).json()
    assert body["success"] is True, body
    assert body["data"]["revision"]["revision"] == 2
    assert body["data"]["revision"]["previous_revision"] == 1
    assert any(
        item["source_type"] == "user_follow_up"
        for item in body["data"]["assessment"]["evidence_items"]
    )


def test_follow_up_caps_answers_at_four():
    assessment_id, _, _ = create_assessment()
    response = client.post(
        f"/api/v2/assessments/{assessment_id}/follow-up",
        json={
            "revision": 1,
            "answers": [
                {"follow_up_id": f"fu-{index}", "answer": "answer"}
                for index in range(5)
            ],
        },
    )
    assert response.status_code == 422


def test_full_partial_and_inaccurate_confirmation_states():
    for level, corrections, expected_confirmation in [
        ("fully_accurate", [], False),
        (
            "partially_accurate",
            [{"field": "evidence.tension_worry.value", "from": 3, "to": 2}],
            True,
        ),
        (
            "inaccurate",
            [{"field": "assessment_summary", "from": None, "to": "not-accurate"}],
            True,
        ),
    ]:
        assessment_id, _, _ = create_assessment()
        body = client.patch(
            f"/api/v2/assessments/{assessment_id}/confirmation",
            json={
                "revision": 1,
                "confirmation_level": level,
                "corrections": corrections,
            },
        ).json()
        assert body["success"] is True
        assert body["data"]["assessment"]["confirmation_level"] == level
        assert body["data"]["assessment"]["requires_user_confirmation"] is expected_confirmation
        assert body["data"]["revision"]["revision"] == 2
        if corrections:
            assert any(
                item["source_type"] == "user_correction"
                for item in body["data"]["assessment"]["evidence_items"]
            )


def test_revision_one_is_retained_and_history_is_ordered():
    assessment_id, _, _ = create_assessment()
    client.patch(
        f"/api/v2/assessments/{assessment_id}/confirmation",
        json={"revision": 1, "confirmation_level": "fully_accurate", "corrections": []},
    )
    history = client.get(
        f"/api/v2/assessments/{assessment_id}/revisions"
    ).json()["data"]["revisions"]
    assert [item["revision"] for item in history] == [1, 2]
    assert history[0]["previous_revision"] is None
    for item in history:
        assert_revision_shape(item)


def test_path_uses_assessment_id_and_rejects_session_id_alias():
    assessment_id, session_id, _ = create_assessment()
    valid = client.get(f"/api/v2/assessments/{assessment_id}/revisions").json()
    invalid = client.get(f"/api/v2/assessments/{session_id}/revisions").json()
    assert valid["success"] is True
    assert invalid["success"] is False
    assert invalid["error"]["code"] == "ASSESSMENT_NOT_FOUND"


def test_stale_revision_is_rejected_without_overwrite():
    assessment_id, _, _ = create_assessment()
    first = client.patch(
        f"/api/v2/assessments/{assessment_id}/confirmation",
        json={"revision": 1, "confirmation_level": "fully_accurate", "corrections": []},
    ).json()
    stale = client.patch(
        f"/api/v2/assessments/{assessment_id}/confirmation",
        json={"revision": 1, "confirmation_level": "inaccurate", "corrections": []},
    ).json()
    assert first["success"] is True
    assert stale["success"] is False
    assert stale["error"]["code"] == "REVISION_CONFLICT"
