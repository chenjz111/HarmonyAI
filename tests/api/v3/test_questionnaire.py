"""V3.1 questionnaire Q1-Q10 submission (Issue #99)."""

import base64
from contextlib import contextmanager
import json
import uuid

from fastapi.testclient import TestClient

from backend.app.core.database import get_db
from backend.app.main import app
from backend.app.models import Session as SessionModel


client = TestClient(app)


@contextmanager
def _seed_db():
    generator = app.dependency_overrides[get_db]()
    try:
        yield next(generator)
    finally:
        generator.close()


def _v3_data(response):
    payload = response.json()
    if "data" not in payload:
        raise AssertionError(
            f"unexpected {response.status_code}: {json.dumps(payload, ensure_ascii=False)}"
        )
    return payload["data"]


def _public_user_id(token: str) -> str:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))["sub"]


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


def _transition(headers, session_id, key, body):
    return client.post(
        f"/api/v3/sessions/{session_id}/input-transitions",
        headers={**headers, "Idempotency-Key": key},
        json=body,
    )


def _approved_manifest() -> dict:
    from pathlib import Path

    return json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "knowledge" / "v3" / "questionnaire-v3.0.json"
        ).read_text(encoding="utf-8")
    )


def _complete_answers() -> list[dict]:
    answers = [
        {"question_id": f"q{i:02d}", "answer_type": "frequency_0_4", "value": 0}
        for i in range(1, 6)
    ]
    answers += [
        {"question_id": f"q{i:02d}", "answer_type": "multi_choice_evidence", "value": ["none"]}
        for i in range(6, 11)
    ]
    return answers


def _body(session_id, expected_input_revision, answers=None):
    manifest = _approved_manifest()
    return {
        "session_id": session_id,
        "expected_input_revision": expected_input_revision,
        "schema_id": manifest["schema_id"],
        "schema_version": manifest["schema_version"],
        "manifest_version": manifest["manifest_version"],
        "content_checksum": manifest["content_checksum"],
        "answers": answers if answers is not None else _complete_answers(),
        "started_at": "2026-01-01T00:00:00Z",
        "completed_at": "2026-01-01T00:05:00Z",
    }


def _post(headers, session_id, key, body):
    return client.post(
        f"/api/v3/sessions/{session_id}/questionnaire",
        headers={**headers, "Idempotency-Key": key},
        json=body,
    )


def test_submit_complete_questionnaire_binds_active_source():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    _transition(
        headers, session_id, "sel-1",
        {"expected_input_revision": 1, "action": "select_mode", "input_mode": "without_document"},
    )
    response = _post(headers, session_id, "q-1", _body(session_id, 2))
    assert response.status_code == 201, response.text
    data = _v3_data(response)
    assert data["status"] == "submitted"
    assert data["input_revision"] == 3
    assert data["schema_id"] == "questionnaire_v3"

    # Session now carries the active questionnaire reference.
    with _seed_db() as session:
        row = session.query(SessionModel).filter(
            SessionModel.session_id == session_id
        ).one()
        assert row.active_questionnaire_submission_id == data["questionnaire_submission_id"]
        assert row.input_revision == 3


def test_submit_rejects_incomplete_questionnaire():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    _transition(
        headers, session_id, "sel-1",
        {"expected_input_revision": 1, "action": "select_mode", "input_mode": "without_document"},
    )
    # Only 5 answers.
    answers = [
        {"question_id": f"q{i:02d}", "answer_type": "frequency_0_4", "value": 0}
        for i in range(1, 6)
    ]
    response = _post(headers, session_id, "q-1", _body(session_id, 2, answers=answers))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "QUESTIONNAIRE_INCOMPLETE"


def test_submit_rejects_wrong_checksum():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    _transition(
        headers, session_id, "sel-1",
        {"expected_input_revision": 1, "action": "select_mode", "input_mode": "without_document"},
    )
    body = _body(session_id, 2)
    body["content_checksum"] = "sha256:" + "0" * 64
    response = _post(headers, session_id, "q-1", body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "QUESTIONNAIRE_INVALID_CHECKSUM"


def test_submit_rejects_invalid_option_and_mutual_exclusion():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    _transition(
        headers, session_id, "sel-1",
        {"expected_input_revision": 1, "action": "select_mode", "input_mode": "without_document"},
    )

    # Invalid option code on q06.
    bad_option = _complete_answers()
    bad_option[5] = {"question_id": "q06", "answer_type": "multi_choice_evidence", "value": ["bogus"]}
    response = _post(headers, session_id, "q-badopt", _body(session_id, 2, answers=bad_option))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "QUESTIONNAIRE_INVALID_OPTION"

    # Mutual exclusion: none + a symptom option on q06.
    bad_excl = _complete_answers()
    bad_excl[5] = {"question_id": "q06", "answer_type": "multi_choice_evidence", "value": ["none", "flank_discomfort"]}
    response = _post(headers, session_id, "q-badexcl", _body(session_id, 2, answers=bad_excl))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "QUESTIONNAIRE_MUTUAL_EXCLUSION"


def test_submit_requires_matching_input_revision():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    _transition(
        headers, session_id, "sel-1",
        {"expected_input_revision": 1, "action": "select_mode", "input_mode": "without_document"},
    )
    response = _post(headers, session_id, "q-1", _body(session_id, 99))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INPUT_REVISION_CONFLICT"


def test_submit_is_idempotent_and_isolated():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    _transition(
        headers, session_id, "sel-1",
        {"expected_input_revision": 1, "action": "select_mode", "input_mode": "without_document"},
    )
    body = _body(session_id, 2)
    first = _post(headers, session_id, "q-1", body)
    assert first.status_code == 201
    replay = _post(headers, session_id, "q-1", body)
    assert replay.status_code == 200
    assert _v3_data(replay)["questionnaire_submission_id"] == _v3_data(first)[
        "questionnaire_submission_id"
    ]

    stranger = _guest_headers()
    denied = _post(stranger, session_id, "q-2", _body(session_id, 3))
    assert denied.status_code == 404
