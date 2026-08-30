"""Owner Flow Amendment 001 §4.1 — session activity & input transitions."""

import uuid

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.document import Document
from backend.app.models.user import User
from backend.app.models.v3.identity import UserIdentity


client = TestClient(app)


def _v3_data(response):
    return response.json()["data"]


def _guest_token() -> str:
    return _v3_data(client.post("/api/v3/auth/guest"))["access_token"]


def _headers(token: str, *, idempotency_key: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def _create_session(token: str, *, flow: str | None = None) -> str:
    body = {} if flow is None else {"flow_contract_version": flow}
    response = client.post(
        "/api/v3/sessions",
        headers=_headers(token, idempotency_key=f"mk-sess-{uuid.uuid4().hex}"),
        json=body,
    )
    assert response.status_code == 201, response.text
    return _v3_data(response)["session_id"]


def _transition(
    token: str,
    session_id: str,
    body: dict,
    *,
    key: str | None = None,
) -> object:
    return client.post(
        f"/api/v3/sessions/{session_id}/input-transitions",
        headers=_headers(
            token, idempotency_key=key or f"mk-tr-{uuid.uuid4().hex}"
        ),
        json=body,
    )


def _activity(token: str, session_id: str) -> object:
    return client.get(
        f"/api/v3/sessions/{session_id}/activity",
        headers=_headers(token),
    )


def test_flow_contract_binding_and_initial_activity():
    token = _guest_token()
    session_id = _create_session(token, flow="v3-owner-flow-1")

    response = _activity(token, session_id)
    assert response.status_code == 200
    state = _v3_data(response)
    assert state["session_id"] == session_id
    assert state["flow_contract_version"] == "v3-owner-flow-1"
    assert state["input_mode"] is None
    assert state["input_revision"] == 1
    assert state["active_document_id"] is None
    assert state["understanding_ref"] is None
    assert state["questionnaire_ref"] is None


def test_unsupported_flow_contract_is_rejected_at_session_creation():
    token = _guest_token()
    response = client.post(
        "/api/v3/sessions",
        headers=_headers(token, idempotency_key=f"mk-bad-{uuid.uuid4().hex}"),
        json={"flow_contract_version": "not-a-real-version"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "FLOW_CONTRACT_UNSUPPORTED"


def test_select_mode_sets_entry_and_bumps_revision():
    token = _guest_token()
    session_id = _create_session(token, flow="v3-owner-flow-1")

    response = _transition(
        token,
        session_id,
        {"action": "select_mode", "expected_input_revision": 1, "input_mode": "without_document"},
    )
    assert response.status_code == 200
    ack = _v3_data(response)
    assert ack["action"] == "select_mode"
    assert ack["expected_input_revision"] == 1

    state = _v3_data(_activity(token, session_id))
    assert state["input_mode"] == "without_document"
    assert state["input_revision"] == 2


def test_select_mode_cannot_run_twice():
    token = _guest_token()
    session_id = _create_session(token, flow="v3-owner-flow-1")
    _transition(
        token,
        session_id,
        {"action": "select_mode", "expected_input_revision": 1, "input_mode": "without_document"},
    )

    response = _transition(
        token,
        session_id,
        {"action": "select_mode", "expected_input_revision": 2, "input_mode": "with_document"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TRANSITION_NOT_ALLOWED"


def test_input_revision_conflict_is_rejected():
    token = _guest_token()
    session_id = _create_session(token, flow="v3-owner-flow-1")
    _transition(
        token,
        session_id,
        {"action": "select_mode", "expected_input_revision": 1, "input_mode": "without_document"},
    )

    response = _transition(
        token,
        session_id,
        {"action": "discard_document", "expected_input_revision": 1},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INPUT_REVISION_CONFLICT"


def test_discard_document_switches_to_without_document_mode():
    token = _guest_token()
    session_id = _create_session(token, flow="v3-owner-flow-1")
    _transition(
        token,
        session_id,
        {"action": "select_mode", "expected_input_revision": 1, "input_mode": "with_document"},
    )

    response = _transition(
        token,
        session_id,
        {"action": "discard_document", "expected_input_revision": 2},
    )
    assert response.status_code == 200
    state = _v3_data(_activity(token, session_id))
    assert state["input_mode"] == "without_document"
    assert state["active_document_id"] is None
    assert state["input_revision"] == 3


def test_replace_document_requires_owned_document(
    db_session_factory,
):
    token = _guest_token()
    session_id = _create_session(token, flow="v3-owner-flow-1")

    response = _transition(
        token,
        session_id,
        {
            "action": "replace_document",
            "expected_input_revision": 1,
            "document_id": "doc_nonexistent",
        },
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_replace_document_with_owned_document_sets_active_source(
    db_session_factory,
):
    token = _guest_token()
    session_id = _create_session(token, flow="v3-owner-flow-1")

    db = db_session_factory()
    user = db.query(User).order_by(User.id.desc()).first()
    identity = db.query(UserIdentity).filter(
        UserIdentity.internal_user_pk == user.id
    ).first()
    internal_pk = identity.internal_user_pk if identity is not None else user.id
    document_id = f"doc_{uuid.uuid4().hex}"
    db.add(
        Document(
            user_id=internal_pk,
            session_id=session_id,
            document_id=document_id,
            original_filename="material.jpg",
            file_type="jpg",
            file_size_bytes=1024,
            storage_path="uploads/test.jpg",
        )
    )
    db.commit()
    db.close()

    response = _transition(
        token,
        session_id,
        {
            "action": "replace_document",
            "expected_input_revision": 1,
            "document_id": document_id,
        },
    )
    assert response.status_code == 200
    state = _v3_data(_activity(token, session_id))
    assert state["input_mode"] == "with_document"
    assert state["active_document_id"] == document_id
    assert state["understanding_ref"] is None
    assert state["input_revision"] == 2


def test_transition_requires_owner_flow_contract():
    token = _guest_token()
    session_id = _create_session(token)  # no flow_contract_version

    response = _transition(
        token,
        session_id,
        {"action": "select_mode", "expected_input_revision": 1, "input_mode": "without_document"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "FLOW_CONTRACT_UNSUPPORTED"


def test_transition_idempotency_replays_and_conflicts():
    token = _guest_token()
    session_id = _create_session(token, flow="v3-owner-flow-1")
    key = f"idem-{uuid.uuid4().hex}"
    body = {
        "action": "select_mode",
        "expected_input_revision": 1,
        "input_mode": "without_document",
    }

    first = _transition(token, session_id, body, key=key)
    replay = _transition(token, session_id, body, key=key)
    assert first.status_code == 200
    assert replay.status_code == 200
    assert _v3_data(replay) == _v3_data(first)

    state = _v3_data(_activity(token, session_id))
    assert state["input_revision"] == 2  # applied exactly once

    conflicting = _transition(
        token,
        session_id,
        {**body, "input_mode": "with_document"},
        key=key,
    )
    assert conflicting.status_code == 409
    assert conflicting.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_cross_user_activity_read_returns_404():
    token = _guest_token()
    session_id = _create_session(token, flow="v3-owner-flow-1")
    stranger = _guest_token()

    response = client.get(
        f"/api/v3/sessions/{session_id}/activity",
        headers=_headers(stranger),
    )
    assert response.status_code == 404


def test_legacy_session_without_flow_contract_still_readable():
    token = _guest_token()
    session_id = _create_session(token)

    response = _activity(token, session_id)
    assert response.status_code == 200
    state = _v3_data(response)
    assert state["flow_contract_version"] is None
    assert state["input_revision"] == 1
