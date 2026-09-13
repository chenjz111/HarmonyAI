"""Assessment V3.1 owner read and final confirmation behavior."""

import uuid
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.v3 import understanding_service
from tests.api.v3.test_assessment_v3 import (_assessment_body, _confirmed_understanding, _guest_headers, _mock_chain, _provider_fact, _setup_guest, _v3_data)

client = TestClient(app)

def _create_available_assessment(monkeypatch, db_session_factory):
    monkeypatch.setattr(understanding_service, "build_provider_chain", lambda: _mock_chain([_provider_fact("anger_tendency", "烦躁易怒倾向", "emotional_state"), _provider_fact("flank_discomfort", "胁肋不适", "somatic")]))
    headers, session_id = _setup_guest()
    db = db_session_factory()
    understanding_id = _confirmed_understanding(headers, session_id, db, facts=None)
    db.close()
    response = client.post("/api/v3/assessments", headers={**headers, "Idempotency-Key": f"asmt-{uuid.uuid4().hex}"}, json=_assessment_body(session_id, understanding_id, 3))
    assert response.status_code == 201, response.text
    return headers, _v3_data(response)

def test_owner_can_read_current_assessment(monkeypatch, db_session_factory):
    headers, created = _create_available_assessment(monkeypatch, db_session_factory)
    response = client.get(f"/api/v3/assessments/{created['assessment_id']}", headers=headers)
    assert response.status_code == 200, response.text
    loaded = _v3_data(response)
    assert loaded["assessment_id"] == created["assessment_id"]
    assert loaded["revision"] == created["revision"]
    assert loaded["presentation"] == created["presentation"]
    assert {item["fact_evidence_id"] for item in loaded["fact_evidence"]} == {
        item["fact_evidence_id"] for item in created["fact_evidence"]
    }
    assert {item["organ_evidence_link_id"] for item in loaded["organ_evidence_links"]} == {
        item["organ_evidence_link_id"] for item in created["organ_evidence_links"]
    }

def test_foreign_owner_cannot_read_assessment(monkeypatch, db_session_factory):
    _headers, created = _create_available_assessment(monkeypatch, db_session_factory)
    response = client.get(f"/api/v3/assessments/{created['assessment_id']}", headers=_guest_headers())
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

def test_foreign_owner_cannot_confirm_assessment(monkeypatch, db_session_factory):
    _headers, created = _create_available_assessment(monkeypatch, db_session_factory)
    response = client.post(
        f"/api/v3/assessments/{created['assessment_id']}/confirmations",
        headers=_guest_headers(),
        json={"expected_revision": 1, "expected_input_revision": 3, "decision": "confirm", "changes": []},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

def test_plain_confirmation_keeps_revision(monkeypatch, db_session_factory):
    headers, created = _create_available_assessment(monkeypatch, db_session_factory)
    response = client.post(f"/api/v3/assessments/{created['assessment_id']}/confirmations", headers=headers, json={"expected_revision": 1, "expected_input_revision": 3, "decision": "confirm", "changes": []})
    assert response.status_code == 200, response.text
    confirmed = _v3_data(response)
    assert confirmed["revision"] == 1
    assert confirmed["status"] == "confirmed"
    assert confirmed["requires_user_confirmation"] is False

def test_confirmation_with_edited_summary_creates_revision(monkeypatch, db_session_factory):
    headers, created = _create_available_assessment(monkeypatch, db_session_factory)
    response = client.post(f"/api/v3/assessments/{created['assessment_id']}/confirmations", headers=headers, json={"expected_revision": 1, "expected_input_revision": 3, "decision": "confirm_with_changes", "changes": [], "edited_summary_text": "最近容易烦躁，也会感到胸胁不舒。"})
    assert response.status_code == 201, response.text
    changed = _v3_data(response)
    assert changed["revision"] == 2
    assert changed["status"] == "confirmed"
    assert changed["state_summary"] == "最近容易烦躁，也会感到胸胁不舒。"
    assert changed["presentation"]["summary"] == changed["state_summary"]

def test_confirmation_rejects_stale_revision(monkeypatch, db_session_factory):
    headers, created = _create_available_assessment(monkeypatch, db_session_factory)
    url = f"/api/v3/assessments/{created['assessment_id']}/confirmations"
    first = client.post(url, headers=headers, json={"expected_revision": 1, "expected_input_revision": 3, "decision": "confirm", "changes": []})
    assert first.status_code == 200, first.text
    stale = client.post(url, headers=headers, json={"expected_revision": 2, "expected_input_revision": 3, "decision": "confirm", "changes": []})
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "REVISION_CONFLICT"
