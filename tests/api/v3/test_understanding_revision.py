"""Owner Flow Amendment 001 §3.3 / §4.2 — Understanding v3.1 revision flow."""

import uuid

from fastapi.testclient import TestClient
import pytest

from backend.ai_engine.v3.understanding_provider import (
    MockUnderstandingProvider,
    UnderstandingProviderChain,
)
from backend.app.main import app
from backend.app.routers.v3 import understanding_router
from backend.app.schemas.v3.understanding import (
    TextSpan,
    UnderstandingProviderFact,
    UnderstandingProviderResponse,
)


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


def _create_flow_session(token: str) -> str:
    response = client.post(
        "/api/v3/sessions",
        headers=_headers(
            token, idempotency_key=f"mk-sess-{uuid.uuid4().hex}"
        ),
        json={"flow_contract_version": "v3-owner-flow-1"},
    )
    assert response.status_code == 201, response.text
    return _v3_data(response)["session_id"]


def _understanding_run_body(session_id: str) -> dict:
    return {
        "schema_version": "understanding_v3.0",
        "session_id": session_id,
        "inputs": [
            {
                "source_id": f"doc_{uuid.uuid4().hex}",
                "source_type": "document",
                "processing_status": "ready",
                "text": "近期入睡困难，白天精神不足。",
                "captured_at": "2026-08-01T00:00:00Z",
            }
        ],
    }


def _mock_chain() -> UnderstandingProviderChain:
    provider = MockUnderstandingProvider(
        UnderstandingProviderResponse(
            status="success",
            facts=[
                UnderstandingProviderFact(
                    claim_code="sleep_unrefreshing",
                    display_name="睡眠后仍感疲惫",
                    category="sleep",
                    value={"type": "severity", "value": "moderate"},
                    time_window="past_7_days",
                    negated=False,
                    subject="self",
                    span=TextSpan(start=0, end=6),
                    extraction_confidence=0.8,
                )
            ],
            warnings=[],
        )
    )
    return UnderstandingProviderChain(cloud=None, local=None, rule=provider)


def test_run_requires_approved_medical_assets(monkeypatch):
    monkeypatch.setattr(understanding_router, "_resolve_provider_chain", lambda: None)
    token = _guest_token()
    session_id = _create_flow_session(token)

    response = client.post(
        "/api/v3/understandings",
        headers=_headers(token),
        json=_understanding_run_body(session_id),
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "MEDICAL_ASSET_UNAVAILABLE"


def test_run_and_plain_confirm_persist_immutable_revisions(monkeypatch):
    monkeypatch.setattr(
        understanding_router, "_resolve_provider_chain", _mock_chain
    )
    token = _guest_token()
    session_id = _create_flow_session(token)

    created = client.post(
        "/api/v3/understandings",
        headers=_headers(token),
        json=_understanding_run_body(session_id),
    )
    assert created.status_code == 201, created.text
    understanding = _v3_data(created)
    understanding_id = understanding["understanding_id"]
    assert understanding["schema_version"] == "understanding_v3.1"
    assert understanding["revision"] == 1
    assert understanding["status"] == "needs_confirmation"
    assert understanding["safety_policy"] == "deferred_v3"
    assert understanding["safety_evaluation_status"] == "not_run"
    assert understanding["safety_status"] is None
    assert len(understanding["normalized_facts"]) == 1

    fetched = client.get(
        f"/api/v3/understandings/{understanding_id}",
        headers=_headers(token),
    )
    assert fetched.status_code == 200
    assert _v3_data(fetched)["revision"] == 1

    confirmed = client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers=_headers(token),
        json={
            "schema_version": "understanding_v3.1",
            "expected_revision": 1,
            "expected_input_revision": 1,
            "decision": "confirm",
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    result = _v3_data(confirmed)
    assert result["previous_revision"] == 1
    assert result["revision"] == 2
    assert result["status"] == "confirmed"

    latest = _v3_data(
        client.get(
            f"/api/v3/understandings/{understanding_id}",
            headers=_headers(token),
        )
    )
    assert latest["revision"] == 2
    assert latest["status"] == "confirmed"

    activity = _v3_data(
        client.get(
            f"/api/v3/sessions/{session_id}/activity",
            headers=_headers(token),
        )
    )
    assert activity["understanding_ref"] == {
        "understanding_id": understanding_id,
        "revision": 2,
    }
    assert activity["input_revision"] == 2


def test_confirm_revision_and_input_revision_conflicts(monkeypatch):
    monkeypatch.setattr(
        understanding_router, "_resolve_provider_chain", _mock_chain
    )
    token = _guest_token()
    session_id = _create_flow_session(token)
    understanding_id = _v3_data(
        client.post(
            "/api/v3/understandings",
            headers=_headers(token),
            json=_understanding_run_body(session_id),
        )
    )["understanding_id"]

    # advance to revision 2 (input_revision 1 -> 2)
    client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers=_headers(token),
        json={
            "schema_version": "understanding_v3.1",
            "expected_revision": 1,
            "expected_input_revision": 1,
            "decision": "confirm",
        },
    )
    # advance to revision 3 (input_revision 2 -> 3)
    second = client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers=_headers(token),
        json={
            "schema_version": "understanding_v3.1",
            "expected_revision": 2,
            "expected_input_revision": 2,
            "decision": "confirm",
        },
    )
    assert second.status_code == 200

    stale_revision = client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers=_headers(token),
        json={
            "schema_version": "understanding_v3.1",
            "expected_revision": 2,
            "expected_input_revision": 3,
            "decision": "confirm",
        },
    )
    assert stale_revision.status_code == 409
    assert stale_revision.json()["error"]["code"] == "REVISION_CONFLICT"

    stale_input = client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers=_headers(token),
        json={
            "schema_version": "understanding_v3.1",
            "expected_revision": 3,
            "expected_input_revision": 2,
            "decision": "confirm",
        },
    )
    assert stale_input.status_code == 409
    assert stale_input.json()["error"]["code"] == "INPUT_REVISION_CONFLICT"


def test_structured_change_applies_whitelist_and_marks_user_correction(monkeypatch):
    monkeypatch.setattr(
        understanding_router, "_resolve_provider_chain", _mock_chain
    )
    token = _guest_token()
    session_id = _create_flow_session(token)
    understanding = _v3_data(
        client.post(
            "/api/v3/understandings",
            headers=_headers(token),
            json=_understanding_run_body(session_id),
        )
    )
    understanding_id = understanding["understanding_id"]
    fact_id = understanding["normalized_facts"][0]["fact_id"]

    rejected = client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers=_headers(token),
        json={
            "schema_version": "understanding_v3.1",
            "expected_revision": 1,
            "expected_input_revision": 1,
            "decision": "confirm_with_changes",
            "changes": [
                {
                    "target_type": "normalized_fact",
                    "target_id": fact_id,
                    "field": "claim_code",
                    "old_value": "sleep_unrefreshing",
                    "new_value": "other_claim",
                }
            ],
        },
    )
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "CHANGE_NOT_ALLOWED"

    accepted = client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers=_headers(token),
        json={
            "schema_version": "understanding_v3.1",
            "expected_revision": 1,
            "expected_input_revision": 1,
            "decision": "confirm_with_changes",
            "changes": [
                {
                    "target_type": "normalized_fact",
                    "target_id": fact_id,
                    "field": "negated",
                    "old_value": False,
                    "new_value": True,
                }
            ],
        },
    )
    assert accepted.status_code == 200, accepted.text
    result = _v3_data(accepted)
    assert result["revision"] == 2
    assert fact_id in result["affected_fact_ids"]

    latest = _v3_data(
        client.get(
            f"/api/v3/understandings/{understanding_id}",
            headers=_headers(token),
        )
    )
    updated_fact = latest["normalized_facts"][0]
    assert updated_fact["negated"] is True
    assert updated_fact["confirmation_status"] == "confirmed"
    assert updated_fact["extraction"]["method"] == "user_correction"


def test_full_text_edit_without_provider_is_503_and_preserves_snapshot(monkeypatch):
    monkeypatch.setattr(
        understanding_router, "_resolve_provider_chain", _mock_chain
    )
    token = _guest_token()
    session_id = _create_flow_session(token)
    understanding_id = _v3_data(
        client.post(
            "/api/v3/understandings",
            headers=_headers(token),
            json=_understanding_run_body(session_id),
        )
    )["understanding_id"]

    monkeypatch.setattr(understanding_router, "_resolve_provider_chain", lambda: None)
    response = client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers=_headers(token),
        json={
            "schema_version": "understanding_v3.1",
            "expected_revision": 1,
            "expected_input_revision": 1,
            "decision": "confirm_with_changes",
            "edited_summary_text": "近期睡眠尚可，无特殊不适。",
            "reprocess_requested": True,
        },
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "MEDICAL_ASSET_UNAVAILABLE"

    latest = _v3_data(
        client.get(
            f"/api/v3/understandings/{understanding_id}",
            headers=_headers(token),
        )
    )
    assert latest["revision"] == 1  # old snapshot unchanged
    assert latest["status"] == "needs_confirmation"


def test_full_text_edit_with_provider_updates_facts_and_summary(monkeypatch):
    monkeypatch.setattr(
        understanding_router, "_resolve_provider_chain", _mock_chain
    )
    token = _guest_token()
    session_id = _create_flow_session(token)
    understanding_id = _v3_data(
        client.post(
            "/api/v3/understandings",
            headers=_headers(token),
            json=_understanding_run_body(session_id),
        )
    )["understanding_id"]

    response = client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers=_headers(token),
        json={
            "schema_version": "understanding_v3.1",
            "expected_revision": 1,
            "expected_input_revision": 1,
            "decision": "confirm_with_changes",
            "edited_summary_text": "资料中提到最近入睡较慢，白天有些疲惫。",
            "reprocess_requested": True,
        },
    )
    assert response.status_code == 200, response.text
    result = _v3_data(response)
    assert result["revision"] == 2

    latest = _v3_data(
        client.get(
            f"/api/v3/understandings/{understanding_id}",
            headers=_headers(token),
        )
    )
    assert latest["status"] == "confirmed"
    assert latest["case_summary"]["summary"] == "资料中提到最近入睡较慢，白天有些疲惫。"
    assert latest["case_summary"]["status"] == "confirmed"
    assert len(latest["normalized_facts"]) == 1
    assert (
        latest["normalized_facts"][0]["source_refs"][0]["source_type"]
        == "user_correction"
    )


def test_confirmation_requires_v31_discriminator(monkeypatch):
    monkeypatch.setattr(
        understanding_router, "_resolve_provider_chain", _mock_chain
    )
    token = _guest_token()
    session_id = _create_flow_session(token)
    understanding_id = _v3_data(
        client.post(
            "/api/v3/understandings",
            headers=_headers(token),
            json=_understanding_run_body(session_id),
        )
    )["understanding_id"]

    response = client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers=_headers(token),
        json={
            "schema_version": "understanding_v3.0",
            "expected_revision": 1,
            "decision": "confirm",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_SCHEMA_VERSION"


def test_cross_user_understanding_read_returns_404(monkeypatch):
    monkeypatch.setattr(
        understanding_router, "_resolve_provider_chain", _mock_chain
    )
    token = _guest_token()
    session_id = _create_flow_session(token)
    understanding_id = _v3_data(
        client.post(
            "/api/v3/understandings",
            headers=_headers(token),
            json=_understanding_run_body(session_id),
        )
    )["understanding_id"]

    stranger = _guest_token()
    response = client.get(
        f"/api/v3/understandings/{understanding_id}",
        headers=_headers(stranger),
    )
    assert response.status_code == 404
