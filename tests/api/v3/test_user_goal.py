"""V3.1 optional UserGoal (疗愈诉求) tests (Issue #99 step 4)."""

import base64
import json
import uuid

from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def _v3_data(response):
    payload = response.json()
    if "data" not in payload:
        raise AssertionError(
            f"unexpected {response.status_code}: {json.dumps(payload, ensure_ascii=False)}"
        )
    return payload["data"]


def _guest_headers() -> dict[str, str]:
    token = _v3_data(client.post("/api/v3/auth/guest"))["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _new_flow_session(headers) -> str:
    response = client.post(
        "/api/v3/sessions",
        headers={**headers, "Idempotency-Key": f"seed-{uuid.uuid4().hex}"},
        json={"flow_contract_version": "v3-owner-flow-1"},
    )
    assert response.status_code == 201, response.text
    return _v3_data(response)["session_id"]


def _submit(headers, session_id, user_goal):
    return client.put(
        f"/api/v3/sessions/{session_id}/user-goal",
        headers=headers,
        json={"user_goal": user_goal},
    )


def _submit_questionnaire(headers, session_id):
    from pathlib import Path

    manifest = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "knowledge" / "v3" / "questionnaire-v3.0.json"
        ).read_text(encoding="utf-8")
    )
    client.post(
        f"/api/v3/sessions/{session_id}/input-transitions",
        headers={**headers, "Idempotency-Key": f"sel-{uuid.uuid4().hex}"},
        json={"expected_input_revision": 1, "action": "select_mode", "input_mode": "without_document"},
    )
    response = client.post(
        f"/api/v3/sessions/{session_id}/questionnaire",
        headers={**headers, "Idempotency-Key": f"q-{uuid.uuid4().hex}"},
        json={
            "session_id": session_id,
            "expected_input_revision": 2,
            "schema_id": manifest["schema_id"],
            "schema_version": manifest["schema_version"],
            "manifest_version": manifest["manifest_version"],
            "content_checksum": manifest["content_checksum"],
            "answers": [
                {"question_id": f"q{i:02d}", "answer_type": "frequency_0_4", "value": 0}
                for i in range(1, 11)
            ],
            "started_at": "2026-01-01T00:00:00Z",
            "completed_at": "2026-01-01T00:05:00Z",
        },
    )
    assert response.status_code == 201, response.text


def test_submit_and_read_user_goal_after_questionnaire():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    _submit_questionnaire(headers, session_id)

    submitted = _submit(
        headers,
        session_id,
        {"primary_goal": "sleep", "secondary_goal": "relaxation", "custom_goal_text": None},
    )
    assert submitted.status_code == 200, submitted.text
    assert _v3_data(submitted)["user_goal"]["primary_goal"] == "sleep"

    read = _v3_data(client.get(f"/api/v3/sessions/{session_id}/user-goal", headers=headers))
    assert read["user_goal"]["secondary_goal"] == "relaxation"


def test_non_null_user_goal_requires_complete_questionnaire():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)

    response = _submit(
        headers, session_id,
        {"primary_goal": "sleep", "secondary_goal": None, "custom_goal_text": None},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "QUESTIONNAIRE_REQUIRED"


def test_skip_user_goal_stores_null():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)

    skipped = _submit(headers, session_id, None)
    assert skipped.status_code == 200
    assert _v3_data(skipped)["user_goal"] is None


def test_user_goal_validation():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)

    # secondary == primary is invalid (schema-level).
    dup = _submit(
        headers, session_id,
        {"primary_goal": "sleep", "secondary_goal": "sleep", "custom_goal_text": None},
    )
    assert dup.status_code == 422

    # "other" requires custom_goal_text.
    missing_text = _submit(
        headers, session_id,
        {"primary_goal": "other", "secondary_goal": None, "custom_goal_text": None},
    )
    assert missing_text.status_code == 422


def test_user_goal_is_cross_user_isolated():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)

    stranger = _guest_headers()
    denied = client.get(f"/api/v3/sessions/{session_id}/user-goal", headers=stranger)
    assert denied.status_code == 404
