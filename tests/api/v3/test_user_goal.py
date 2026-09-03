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


def test_submit_and_read_user_goal():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)

    submitted = _submit(
        headers,
        session_id,
        {"primary_goal": "sleep", "secondary_goal": "relaxation", "custom_goal_text": None},
    )
    assert submitted.status_code == 200, submitted.text
    assert _v3_data(submitted)["user_goal"]["primary_goal"] == "sleep"

    read = _v3_data(client.get(f"/api/v3/sessions/{session_id}/user-goal", headers=headers))
    assert read["user_goal"]["secondary_goal"] == "relaxation"


def test_skip_user_goal_stores_null():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)

    skipped = _submit(headers, session_id, None)
    assert skipped.status_code == 200
    assert _v3_data(skipped)["user_goal"] is None

    read = _v3_data(client.get(f"/api/v3/sessions/{session_id}/user-goal", headers=headers))
    assert read["user_goal"] is None


def test_user_goal_validation():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)

    # secondary == primary is invalid.
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

    # custom_goal_text only allowed with "other".
    extra_text = _submit(
        headers, session_id,
        {"primary_goal": "sleep", "secondary_goal": None, "custom_goal_text": "想睡好"},
    )
    assert extra_text.status_code == 422


def test_user_goal_is_cross_user_isolated():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)

    stranger = _guest_headers()
    denied = client.get(f"/api/v3/sessions/{session_id}/user-goal", headers=stranger)
    assert denied.status_code == 404
