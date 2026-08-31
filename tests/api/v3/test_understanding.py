"""V3 understanding ingestion, OCR status, input-mode and confirmation API.

Covers the non-conflicting Section A surface: explicit OCR failure statuses
(no confirmed reference from a failed source), the persisted session input
mode derived from the material sources, and the optimistic-revision
confirmation flow with immutable revisions.
"""

import base64
from contextlib import contextmanager
import json
import uuid

from fastapi.testclient import TestClient

from backend.app.core.database import get_db
from backend.app.main import app
from backend.app.models import Session as SessionModel
from backend.app.models.document import Document
from backend.app.models.v3.identity import UserIdentity
from backend.app.models.v3.understanding import UnderstandingRun, UnderstandingSource


client = TestClient(app)


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


@contextmanager
def _seed_db():
    generator = app.dependency_overrides[get_db]()
    try:
        yield next(generator)
    finally:
        generator.close()


def _setup_guest() -> tuple[dict[str, str], str]:
    headers = _guest_headers()
    session_id = _v3_data(
        client.post(
            "/api/v3/sessions",
            headers={**headers, "Idempotency-Key": f"seed-session-{uuid.uuid4().hex}"},
            json={},
        )
    )["session_id"]
    return headers, session_id


def _row_ids(session, public_user_id: str, session_id: str) -> tuple[int, int]:
    user = (
        session.query(UserIdentity)
        .filter(UserIdentity.public_user_id == public_user_id)
        .one()
    )
    sess = (
        session.query(SessionModel)
        .filter(
            SessionModel.session_id == session_id,
            SessionModel.user_id == user.internal_user_pk,
        )
        .one()
    )
    return user.internal_user_pk, sess.id


def _seed_document(
    session,
    *,
    user_pk: int,
    session_id: str,
    ocr_text: str | None = None,
    ocr_error_code: str | None = None,
    status: str = "uploaded",
) -> str:
    document_id = f"doc_{uuid.uuid4().hex}"
    session.add(
        Document(
            user_id=user_pk,
            session_id=session_id,
            document_id=document_id,
            original_filename="sample.png",
            file_type="png",
            file_size_bytes=1024,
            storage_path=f"docs/{document_id}",
            status=status,
            ocr_text=ocr_text,
            ocr_confidence="high" if ocr_text else None,
            ocr_error_code=ocr_error_code,
        )
    )
    session.commit()
    return document_id


def _narrative_source(text: str) -> dict[str, str]:
    return {
        "source_id": f"src_{uuid.uuid4().hex}",
        "source_type": "narrative",
        "processing_status": "ready",
        "text": text,
        "captured_at": "2026-01-01T00:00:00Z",
    }


def _document_source(document_id: str) -> dict[str, str]:
    return {
        "source_id": f"src_{uuid.uuid4().hex}",
        "source_type": "document",
        "processing_status": "ready",
        "text_ref": document_id,
        "captured_at": "2026-01-01T00:00:00Z",
    }


def _understanding_body(session_id: str, inputs: list[dict[str, str]]) -> dict:
    return {
        "schema_version": "understanding_v3.0",
        "session_id": session_id,
        "inputs": inputs,
    }


def _post_understanding(headers, body, idempotency_key):
    return client.post(
        "/api/v3/understandings",
        headers={**headers, "Idempotency-Key": idempotency_key},
        json=body,
    )


def _session_input_mode(session_id: str) -> str | None:
    with _seed_db() as session:
        row = session.query(SessionModel).filter(
            SessionModel.session_id == session_id
        ).one()
        return row.input_mode


def test_narrative_ingestion_persists_without_document_mode():
    headers, session_id = _setup_guest()
    response = _post_understanding(
        headers,
        _understanding_body(session_id, [_narrative_source("最近总是睡不好。")]),
        "sha256:und-narrative-1",
    )
    if response.status_code != 201:
        raise AssertionError(
            f"{response.status_code}: {json.dumps(response.json(), ensure_ascii=False)}"
        )
    data = _v3_data(response)
    assert data["status"] == "needs_confirmation"
    assert data["revision"] == 1
    assert data["source_statuses"][0]["status"] == "ready"
    assert data["safety_status"] == "clear"
    assert _session_input_mode(session_id) == "without_document"


def test_document_ingestion_uses_ocr_text_and_with_document_mode():
    headers, session_id = _setup_guest()
    with _seed_db() as session:
        user_pk, _ = _row_ids(
            session,
            _public_user_id(headers["Authorization"].split()[1]),
            session_id,
        )
        document_id = _seed_document(
            session,
            user_pk=user_pk,
            session_id=session_id,
            ocr_text="材料中提到近期睡眠恢复不足。",
        )
    response = _post_understanding(
        headers,
        _understanding_body(session_id, [_document_source(document_id)]),
        "sha256:und-doc-1",
    )
    assert response.status_code == 201
    data = _v3_data(response)
    assert data["status"] == "needs_confirmation"
    assert data["source_statuses"][0]["status"] == "ready"
    assert data["case_summary"]["summary"].startswith("材料中提到近期睡眠")
    assert _session_input_mode(session_id) == "with_document"


def test_ocr_failure_is_explicit_and_never_confirms():
    headers, session_id = _setup_guest()
    with _seed_db() as session:
        user_pk, _ = _row_ids(
            session,
            _public_user_id(headers["Authorization"].split()[1]),
            session_id,
        )
        document_id = _seed_document(
            session,
            user_pk=user_pk,
            session_id=session_id,
            ocr_text=None,
            ocr_error_code="OCR_FAILED",
        )
    response = _post_understanding(
        headers,
        _understanding_body(session_id, [_document_source(document_id)]),
        "sha256:und-ocrfail-1",
    )
    assert response.status_code == 201
    data = _v3_data(response)
    assert data["status"] == "failed"
    assert data["case_summary"] is None
    assert data["source_statuses"][0]["status"] == "failed"
    assert data["degradation"]["active"] is True

    # The failed source must not surface a confirmed reference anywhere.
    with _seed_db() as session:
        run = session.query(UnderstandingRun).one()
        assert run.status == "failed"
        source = session.query(UnderstandingSource).one()
        assert source.processing_status == "failed"


def test_ingestion_requires_idempotency_key():
    headers, session_id = _setup_guest()
    response = client.post(
        "/api/v3/understandings",
        headers=headers,
        json=_understanding_body(session_id, [_narrative_source("内容。")]),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_ingestion_replay_returns_same_resource():
    headers, session_id = _setup_guest()
    body = _understanding_body(session_id, [_narrative_source("重复提交。")])
    first = _post_understanding(headers, body, "sha256:und-replay-1")
    assert first.status_code == 201
    understanding_id = _v3_data(first)["understanding_id"]

    second = _post_understanding(headers, body, "sha256:und-replay-1")
    assert second.status_code == 200
    assert _v3_data(second)["understanding_id"] == understanding_id


def test_read_model_and_cross_user_isolation():
    headers, session_id = _setup_guest()
    response = _post_understanding(
        headers,
        _understanding_body(session_id, [_narrative_source("仅本人可见。")]),
        "sha256:und-read-1",
    )
    understanding_id = _v3_data(response)["understanding_id"]

    own = client.get(f"/api/v3/understandings/{understanding_id}", headers=headers)
    assert own.status_code == 200
    assert _v3_data(own)["status"] == "needs_confirmation"

    stranger = _guest_headers()
    denied = client.get(
        f"/api/v3/understandings/{understanding_id}", headers=stranger
    )
    assert denied.status_code == 404
    assert denied.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_confirm_advances_revision_once():
    headers, session_id = _setup_guest()
    understanding_id = _v3_data(
        _post_understanding(
            headers,
            _understanding_body(session_id, [_narrative_source("可确认内容。")]),
            "sha256:und-confirm-1",
        )
    )["understanding_id"]

    result = _v3_data(
        client.post(
            f"/api/v3/understandings/{understanding_id}/confirmations",
            headers={**headers, "Idempotency-Key": "sha256:und-confirm-dec-1"},
            json={"expected_revision": 1, "decision": "confirm"},
        )
    )
    assert result["previous_revision"] == 1
    assert result["revision"] == 2
    assert result["status"] == "confirmed"

    read = _v3_data(client.get(f"/api/v3/understandings/{understanding_id}", headers=headers))
    assert read["revision"] == 2
    assert read["status"] == "confirmed"


def test_confirm_requires_matching_revision():
    headers, session_id = _setup_guest()
    understanding_id = _v3_data(
        _post_understanding(
            headers,
            _understanding_body(session_id, [_narrative_source("冲突内容。")]),
            "sha256:und-conflict-1",
        )
    )["understanding_id"]

    response = client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers={**headers, "Idempotency-Key": "sha256:und-conflict-dec-1"},
        json={"expected_revision": 99, "decision": "confirm"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REVISION_CONFLICT"


def test_confirm_with_changes_edits_case_summary():
    headers, session_id = _setup_guest()
    with _seed_db() as session:
        user_pk, _ = _row_ids(
            session,
            _public_user_id(headers["Authorization"].split()[1]),
            session_id,
        )
        document_id = _seed_document(
            session,
            user_pk=user_pk,
            session_id=session_id,
            ocr_text="材料提到睡眠恢复不足。",
        )
    understanding_id = _v3_data(
        _post_understanding(
            headers,
            _understanding_body(session_id, [_document_source(document_id)]),
            "sha256:und-changes-1",
        )
    )["understanding_id"]
    case_summary_id = _v3_data(
        client.get(f"/api/v3/understandings/{understanding_id}", headers=headers)
    )["case_summary"]["case_summary_id"]

    result = _v3_data(
        client.post(
            f"/api/v3/understandings/{understanding_id}/confirmations",
            headers={**headers, "Idempotency-Key": "sha256:und-changes-dec-1"},
            json={
                "expected_revision": 1,
                "decision": "confirm_with_changes",
                "changes": [
                    {
                        "target_type": "case_summary",
                        "target_id": case_summary_id,
                        "field": "summary",
                        "old_value": "材料提到睡眠恢复不足。",
                        "new_value": "材料提到近期睡眠恢复不佳。",
                    }
                ],
            },
        )
    )
    assert result["revision"] == 2
    assert result["status"] == "confirmed"
    assert result["applied_changes"] == ["chg_1"]

    updated = _v3_data(
        client.get(f"/api/v3/understandings/{understanding_id}", headers=headers)
    )
    assert updated["case_summary"]["summary"] == "材料提到近期睡眠恢复不佳。"


def test_reject_source_rejects_whole_material():
    headers, session_id = _setup_guest()
    understanding_id = _v3_data(
        _post_understanding(
            headers,
            _understanding_body(session_id, [_narrative_source("无法采用的内容。")]),
            "sha256:und-reject-1",
        )
    )["understanding_id"]

    result = _v3_data(
        client.post(
            f"/api/v3/understandings/{understanding_id}/confirmations",
            headers={**headers, "Idempotency-Key": "sha256:und-reject-dec-1"},
            json={"expected_revision": 1, "decision": "reject_source"},
        )
    )
    assert result["status"] == "rejected"

    read = _v3_data(
        client.get(f"/api/v3/understandings/{understanding_id}", headers=headers)
    )
    assert read["status"] == "failed"
    assert read["case_summary"] is None
    assert read["source_statuses"][0]["status"] == "skipped"


def test_historical_revision_read_returns_its_own_status():
    headers, session_id = _setup_guest()
    understanding_id = _v3_data(
        _post_understanding(
            headers,
            _understanding_body(session_id, [_narrative_source("历史快照内容。")]),
            "sha256:und-hist-1",
        )
    )["understanding_id"]

    _v3_data(
        client.post(
            f"/api/v3/understandings/{understanding_id}/confirmations",
            headers={**headers, "Idempotency-Key": "sha256:und-hist-dec-1"},
            json={"expected_revision": 1, "decision": "confirm"},
        )
    )

    current = _v3_data(
        client.get(f"/api/v3/understandings/{understanding_id}", headers=headers)
    )
    assert current["revision"] == 2
    assert current["status"] == "confirmed"

    historical = _v3_data(
        client.get(
            f"/api/v3/understandings/{understanding_id}?revision=1", headers=headers
        )
    )
    assert historical["revision"] == 1
    assert historical["status"] == "needs_confirmation"

    beyond = client.get(
        f"/api/v3/understandings/{understanding_id}?revision=3", headers=headers
    )
    assert beyond.status_code == 404


def test_cannot_confirm_keeps_undecided():
    headers, session_id = _setup_guest()
    understanding_id = _v3_data(
        _post_understanding(
            headers,
            _understanding_body(session_id, [_narrative_source("暂无法确认。")]),
            "sha256:und-undecided-1",
        )
    )["understanding_id"]

    result = _v3_data(
        client.post(
            f"/api/v3/understandings/{understanding_id}/confirmations",
            headers={**headers, "Idempotency-Key": "sha256:und-undecided-dec-1"},
            json={"expected_revision": 1, "decision": "cannot_confirm"},
        )
    )
    assert result["status"] == "needs_confirmation"
    read = _v3_data(
        client.get(f"/api/v3/understandings/{understanding_id}", headers=headers)
    )
    assert read["status"] == "needs_confirmation"
    assert read["revision"] == 2


def test_stranger_cannot_confirm_owned_understanding():
    headers, session_id = _setup_guest()
    understanding_id = _v3_data(
        _post_understanding(
            headers,
            _understanding_body(session_id, [_narrative_source("仅本人确认。")]),
            "sha256:und-owner-1",
        )
    )["understanding_id"]

    stranger = _guest_headers()
    response = client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers={**stranger, "Idempotency-Key": "sha256:und-owner-dec-1"},
        json={"expected_revision": 1, "decision": "confirm"},
    )
    assert response.status_code == 404
