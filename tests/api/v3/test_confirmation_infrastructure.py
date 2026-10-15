"""Offline owner-input continuity; no changes to fact authorization semantics."""

import pytest

from backend.app.models.v3.understanding import UnderstandingRun
from backend.app.services.v3 import understanding_service
from tests.api.v3.test_owner_flow import (
    client, _guest_headers, _new_flow_session, _transition, _seed_db,
    _seed_document, _user_pk, _v3_data,
)
from tests.api.v3.test_understanding_ai_extraction import _mock_chain


def _pending(monkeypatch):
    monkeypatch.setattr(understanding_service, "build_provider_chain", _mock_chain)
    headers = _guest_headers()
    sid = _new_flow_session(headers)
    _transition(headers, sid, "select", {"expected_input_revision": 1,
        "action": "select_mode", "input_mode": "with_document"})
    with _seed_db() as db:
        doc = _seed_document(db, user_pk=_user_pk(db, headers["Authorization"]),
            session_id=sid, ocr_text="睡眠后仍感疲惫。")
    _transition(headers, sid, "replace", {"expected_input_revision": 2,
        "action": "replace_document", "document_id": doc})
    run = _v3_data(client.post("/api/v3/understandings",
        headers={**headers, "Idempotency-Key": "extract"}, json={
            "schema_version": "understanding_v3.1", "session_id": sid,
            "expected_input_revision": 3, "inputs": [{"source_id": "source",
                "source_type": "document", "processing_status": "ready",
                "text_ref": doc, "captured_at": "2026-01-01T00:00:00Z"}]}))
    return headers, sid, run


def _confirm(headers, uid, body, key="confirm"):
    return client.post(f"/api/v3/understandings/{uid}/confirmations",
        headers={**headers, "Idempotency-Key": key}, json={
            "schema_version": "understanding_v3.1", **body})


def test_rejected_revision_can_be_edited_on_same_input(monkeypatch):
    headers, sid, run = _pending(monkeypatch)
    uid = run["understanding_id"]
    fact = run["normalized_facts"][0]
    rejected = _confirm(headers, uid, {"expected_revision": 1,
        "expected_input_revision": 3, "decision": "confirm_with_changes",
        "changes": [{"target_type": "normalized_fact", "target_id": fact["fact_id"],
            "field": "confirmation_status", "old_value": "unconfirmed",
            "new_value": "rejected"}]})
    assert rejected.status_code == 201, rejected.text
    before = _v3_data(client.get(f"/api/v3/understandings/{uid}?revision=2", headers=headers))
    edited = _confirm(headers, uid, {"expected_revision": 2,
        "expected_input_revision": 4, "decision": "confirm_with_changes",
        "edited_summary_text": "资料记录睡眠恢复不足。", "reprocess_requested": True}, "edit")
    assert edited.status_code == 201, edited.text
    assert _v3_data(edited)["status"] == "confirmed"
    assert all(f["confirmation_status"] == "confirmed"
        for f in _v3_data(edited)["understanding"]["normalized_facts"])
    assert _v3_data(client.get(f"/api/v3/understandings/{uid}?revision=2", headers=headers)) == before
    assert before["normalized_facts"][0]["confirmation_status"] == "rejected"
    with _seed_db() as db:
        assert db.get(UnderstandingRun, uid).input_revision == 5


@pytest.mark.parametrize("stale", ["revision", "input", "replacement", "discard"])
def test_confirmation_continuity_keeps_stale_guards(monkeypatch, stale):
    headers, sid, run = _pending(monkeypatch)
    uid = run["understanding_id"]
    body = {"expected_revision": 1, "expected_input_revision": 3, "decision": "confirm"}
    first = _confirm(headers, uid, body)
    assert first.status_code == 201, first.text
    replay = _confirm(headers, uid, body)
    assert replay.status_code == 200
    assert _v3_data(replay) == _v3_data(first)
    next_body = {"expected_revision": 2, "expected_input_revision": 4, "decision": "confirm"}
    if stale == "revision":
        next_body["expected_revision"] = 1
    elif stale == "input":
        next_body["expected_input_revision"] = 3
    elif stale == "replacement":
        with _seed_db() as db:
            doc = _seed_document(db, user_pk=_user_pk(db, headers["Authorization"]),
                session_id=sid, ocr_text="新的资料。")
        changed = _transition(headers, sid, "new-document", {"expected_input_revision": 4,
            "action": "replace_document", "document_id": doc})
        assert changed.status_code == 201, changed.text
        next_body["expected_input_revision"] = 5
    else:
        changed = _transition(headers, sid, "discard", {"expected_input_revision": 4,
            "action": "discard_document"})
        assert changed.status_code == 201, changed.text
        next_body["expected_input_revision"] = 5
    result = _confirm(headers, uid, next_body, "competing-request")
    assert result.status_code == 409, result.text
    assert _v3_data(client.get(f"/api/v3/understandings/{uid}", headers=headers))["revision"] == 2


def test_competing_input_update_fails_cas_and_rolls_back(monkeypatch):
    """Interleave an input advance after initial checks, immediately before CAS."""
    from sqlalchemy import update
    from backend.app.models import Session as SessionModel
    headers, sid, run = _pending(monkeypatch)
    uid = run["understanding_id"]
    original_cas = understanding_service._cas_bind_understanding

    def competing_update(db, session_row, understanding_id, revision, expected):
        db.execute(update(SessionModel).where(SessionModel.id == session_row.id)
            .values(input_revision=expected + 1))
        return original_cas(db, session_row, understanding_id, revision, expected)

    monkeypatch.setattr(understanding_service, "_cas_bind_understanding", competing_update)
    response = _confirm(headers, uid, {"expected_revision": 1,
        "expected_input_revision": 3, "decision": "confirm"})
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "INPUT_REVISION_CONFLICT"
    with _seed_db() as db:
        assert db.get(UnderstandingRun, uid).input_revision == 3
        assert db.get(UnderstandingRun, uid).current_revision == 1
    assert _v3_data(client.get(f"/api/v3/understandings/{uid}", headers=headers))["status"] == "needs_confirmation"


def test_pending_edit_rejects_stale_expected_input_before_reconciliation(monkeypatch):
    headers, sid, run = _pending(monkeypatch)
    calls = []
    monkeypatch.setattr(understanding_service, "re_extract_facts",
        lambda *args: calls.append(args) or ([], []))
    response = _confirm(headers, run["understanding_id"], {"expected_revision": 1,
        "expected_input_revision": 2, "decision": "confirm_with_changes",
        "edited_summary_text": "修改资料。", "reprocess_requested": True})
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "INPUT_REVISION_CONFLICT"
    assert calls == []
