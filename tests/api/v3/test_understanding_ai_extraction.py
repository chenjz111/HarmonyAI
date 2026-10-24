"""AI fact extraction through the Understanding Provider Chain.

Wires the Issue #89 approved claim dictionary + provider into ingestion:
OCR/Narrative text -> NormalizedFacts; confirmation propagates to inner
state; full-text edits project canonical facts without a provider and keep
earlier facts as provenance.
"""

import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError

from backend.ai_engine.v3.understanding_provider import (
    MockUnderstandingProvider,
    ProviderFailureV3,
    QwenUnderstandingProvider,
    UnderstandingProviderChain,
)
from backend.app.main import app
from backend.app.models.document import Document
from backend.app.models.v3.identity import UserIdentity
from backend.app.models.v3.understanding import (
    FactSourceRef as FactSourceRefRow,
    NormalizedFact as NormalizedFactRow,
    UnderstandingSource as UnderstandingSourceRow,
)
from backend.app.schemas.v3.understanding import (
    TextSpan,
    UnderstandingProviderFact,
    UnderstandingProviderResponse,
)
from backend.app.services.v3 import understanding_service
from backend.app.services.v3.document_summary import summarize_facts
from backend.app.services.v3.knowledge_assets import load_claim_dictionary
from backend.app.services.v3.understanding_extraction import (
    _run_provider,
    extract_facts_for_sources,
)


client = TestClient(app)


def _v3_data(response):
    return response.json()["data"]


def _guest_headers():
    token = _v3_data(client.post("/api/v3/auth/guest"))["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _setup_guest():
    headers = _guest_headers()
    response = client.post(
        "/api/v3/sessions",
        headers={**headers, "Idempotency-Key": f"sess-{uuid.uuid4().hex}"},
        json={},
    )
    session_id = _v3_data(response)["session_id"]
    return headers, session_id


def _seed_document(db_session, *, user_pk, session_id, ocr_text):
    document_id = f"doc_{uuid.uuid4().hex}"
    db_session.add(
        Document(
            user_id=user_pk,
            session_id=session_id,
            document_id=document_id,
            original_filename="sample.png",
            file_type="png",
            file_size_bytes=1024,
            storage_path=f"docs/{document_id}",
            status="uploaded",
            ocr_text=ocr_text,
            ocr_confidence="high",
            ocr_error_code=None,
        )
    )
    db_session.commit()
    return document_id


def _user_pk(db_session, headers):
    token = headers["Authorization"].split(" ")[1]
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    import base64
    import json

    public_user_id = json.loads(base64.urlsafe_b64decode(payload))["sub"]
    identity = (
        db_session.query(UserIdentity)
        .filter(UserIdentity.public_user_id == public_user_id)
        .one()
    )
    return identity.internal_user_pk


def _mock_fact():
    return UnderstandingProviderFact(
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


def _mock_chain(*, facts=None):
    if facts is None:
        facts = [_mock_fact()]
    provider = MockUnderstandingProvider(
        UnderstandingProviderResponse(status="success", facts=facts, warnings=[])
    )
    return UnderstandingProviderChain(cloud=None, local=None, rule=provider)


def _resolved_document(text="近期入睡困难。"):
    return SimpleNamespace(
        processing_status="ready",
        source=SimpleNamespace(
            source_id="src_test",
            source_type=SimpleNamespace(value="document"),
        ),
        text=text,
    )


def _document_source(document_id):
    return {
        "source_id": f"src_{uuid.uuid4().hex}",
        "source_type": "document",
        "processing_status": "ready",
        "text_ref": document_id,
        "captured_at": "2026-01-01T00:00:00Z",
    }


def _narrative_source(text):
    return {
        "source_id": f"src_{uuid.uuid4().hex}",
        "source_type": "narrative",
        "processing_status": "ready",
        "text": text,
        "captured_at": "2026-01-01T00:00:00Z",
    }


def _run_body(session_id, inputs):
    return {
        "schema_version": "understanding_v3.0",
        "session_id": session_id,
        "inputs": inputs,
    }


def _post(headers, session_id, inputs):
    return client.post(
        "/api/v3/understandings",
        headers={**headers, "Idempotency-Key": f"und-{uuid.uuid4().hex}"},
        json=_run_body(session_id, inputs),
    )


def _confirm(headers, understanding_id, *, decision="confirm", **extra):
    body = {
        "schema_version": "understanding_v3.0",
        "expected_revision": 1,
        "decision": decision,
    }
    body.update(extra)
    return client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers={**headers, "Idempotency-Key": f"cfm-{uuid.uuid4().hex}"},
        json=body,
    )


def test_document_extraction_produces_normalized_facts(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_service, "build_provider_chain", lambda: _mock_chain()
    )
    headers, session_id = _setup_guest()
    db = db_session_factory()
    user_pk = _user_pk(db, headers)
    document_id = _seed_document(
        db, user_pk=user_pk, session_id=session_id,
        ocr_text="近期入睡困难，白天精神不足。",
    )
    db.close()

    response = _post(headers, session_id, [_document_source(document_id)])
    assert response.status_code == 201, response.text
    understanding = _v3_data(response)
    assert len(understanding["normalized_facts"]) == 1
    fact = understanding["normalized_facts"][0]
    assert fact["fact_code"] == "sleep_unrefreshing"
    assert fact["value"]["value"] == "moderate"
    assert fact["negated"] is False
    assert fact["subject"] == "self"
    assert fact["confirmation_status"] == "unconfirmed"
    assert fact["extraction"]["method"] == "rule"
    assert fact["source_refs"][0]["source_type"] == "document"


def test_narrative_extraction_source_ref_is_narrative(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_service, "build_provider_chain", lambda: _mock_chain()
    )
    headers, session_id = _setup_guest()

    response = _post(headers, session_id, [_narrative_source("最近总是睡不好。")])
    assert response.status_code == 201, response.text
    understanding = _v3_data(response)
    assert len(understanding["normalized_facts"]) == 1
    assert (
        understanding["normalized_facts"][0]["source_refs"][0]["source_type"]
        == "narrative"
    )
    # narrative-only: no material CaseSummary / no document-confirmation page
    assert understanding["case_summary"] is None


def test_confirm_propagates_to_facts_and_case_summary(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_service, "build_provider_chain", lambda: _mock_chain()
    )
    headers, session_id = _setup_guest()
    db = db_session_factory()
    user_pk = _user_pk(db, headers)
    document_id = _seed_document(
        db, user_pk=user_pk, session_id=session_id,
        ocr_text="近期入睡困难，白天精神不足。",
    )
    db.close()

    understanding_id = _v3_data(
        _post(headers, session_id, [_document_source(document_id)])
    )["understanding_id"]

    confirmed = _confirm(headers, understanding_id)
    assert confirmed.status_code == 201, confirmed.text
    result = _v3_data(confirmed)
    assert result["revision"] == 2

    read = _v3_data(
        client.get(
            f"/api/v3/understandings/{understanding_id}",
            headers=headers,
        )
    )
    assert read["status"] == "confirmed"
    assert read["revision"] == 2
    assert all(
        fact["confirmation_status"] == "confirmed"
        for fact in read["normalized_facts"]
    )
    assert read["case_summary"]["status"] == "confirmed"
    assert read["case_summary"]["revision"] == 2


def test_provider_unavailable_never_fabricates_facts(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_service, "build_provider_chain", lambda: None
    )
    headers, session_id = _setup_guest()
    db = db_session_factory()
    user_pk = _user_pk(db, headers)
    document_id = _seed_document(
        db, user_pk=user_pk, session_id=session_id,
        ocr_text="近期入睡困难，白天精神不足。",
    )
    db.close()

    response = _post(headers, session_id, [_document_source(document_id)])
    assert response.status_code == 201, response.text
    assert _v3_data(response)["normalized_facts"] == []


def test_full_text_edit_never_changes_structured_fact_status(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_service, "build_provider_chain", lambda: _mock_chain()
    )
    headers, session_id = _setup_guest()
    db = db_session_factory()
    user_pk = _user_pk(db, headers)
    document_id = _seed_document(
        db, user_pk=user_pk, session_id=session_id,
        ocr_text="近期入睡困难，白天精神不足。",
    )
    db.close()

    understanding_id = _v3_data(
        _post(headers, session_id, [_document_source(document_id)])
    )["understanding_id"]
    original = _v3_data(
        client.get(f"/api/v3/understandings/{understanding_id}", headers=headers)
    )

    response = _confirm(
        headers,
        understanding_id,
        decision="confirm_with_changes",
        edited_summary_text="资料中提到最近入睡较慢，白天有些疲惫。",
        reprocess_requested=True,
    )
    assert response.status_code == 201, response.text
    result = _v3_data(response)
    assert result["revision"] == 2
    # Phase 2 (D3): a narrative-only edit decides nothing about the structured
    # facts, so no fact id is reported as affected.
    assert result["affected_fact_ids"] == []
    assert "chg_summary_edit" in result["applied_changes"]

    read = _v3_data(
        client.get(
            f"/api/v3/understandings/{understanding_id}",
            headers=headers,
        )
    )
    assert [f["fact_id"] for f in read["normalized_facts"]] == [
        f["fact_id"] for f in original["normalized_facts"]
    ]
    assert [f["confirmation_status"] for f in read["normalized_facts"]] == [
        f["confirmation_status"] for f in original["normalized_facts"]
    ]
    assert read["case_summary"]["summary"] == "资料中提到最近入睡较慢，白天有些疲惫。"


def test_successful_full_text_edit_keeps_previous_revision_immutable(
    monkeypatch, db_session_factory
):
    monkeypatch.setattr(
        understanding_service, "build_provider_chain", lambda: _mock_chain()
    )
    headers, session_id = _setup_guest()
    db = db_session_factory()
    user_pk = _user_pk(db, headers)
    document_id = _seed_document(
        db,
        user_pk=user_pk,
        session_id=session_id,
        ocr_text="近期入睡困难，白天精神不足。",
    )
    db.close()

    understanding_id = _v3_data(
        _post(headers, session_id, [_document_source(document_id)])
    )["understanding_id"]

    response = _confirm(
        headers,
        understanding_id,
        decision="confirm_with_changes",
        edited_summary_text="资料中提到最近入睡较慢，白天有些疲惫。",
        reprocess_requested=True,
    )
    assert response.status_code == 201, response.text

    previous = _v3_data(
        client.get(
            f"/api/v3/understandings/{understanding_id}?revision=1",
            headers=headers,
        )
    )
    latest = _v3_data(
        client.get(
            f"/api/v3/understandings/{understanding_id}?revision=2",
            headers=headers,
        )
    )
    # revision 1 keeps its own confirmed-in-progress summary: the approved
    # fact text, not the raw OCR excerpt it was ingested from.
    assert (
        previous["case_summary"]["summary"]
        == "资料中记录的近期状态：睡眠后仍感疲惫。"
    )
    assert previous["normalized_facts"][0]["source_refs"][0]["source_type"] == "document"
    assert latest["case_summary"]["summary"] == "资料中提到最近入睡较慢，白天有些疲惫。"
    # Phase 2 (D3/D6): the narrative is presentation only. An edit copies every
    # structured fact forward with its own status instead of dropping the ones
    # whose wording is absent from the text.
    assert [f["fact_id"] for f in latest["normalized_facts"]] == [
        f["fact_id"] for f in previous["normalized_facts"]
    ]


def test_full_text_edit_without_provider_confirms_new_revision(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_service, "build_provider_chain", lambda: None
    )
    headers, session_id = _setup_guest()
    db = db_session_factory()
    user_pk = _user_pk(db, headers)
    document_id = _seed_document(
        db, user_pk=user_pk, session_id=session_id,
        ocr_text="近期入睡困难，白天精神不足。",
    )
    db.close()

    understanding_id = _v3_data(
        _post(headers, session_id, [_document_source(document_id)])
    )["understanding_id"]

    response = _confirm(
        headers,
        understanding_id,
        decision="confirm_with_changes",
        edited_summary_text="资料中提到最近入睡较慢。",
        reprocess_requested=True,
    )
    assert response.status_code == 201, response.text

    read = _v3_data(
        client.get(
            f"/api/v3/understandings/{understanding_id}",
            headers=headers,
        )
    )
    assert read["revision"] == 2
    assert read["status"] == "confirmed"
    assert read["normalized_facts"] == []


def test_extraction_request_passes_the_provider_version_handshake():
    """The request must mirror the provider's approved dictionary version.

    The approved asset declares ``schema_version=3.0.0`` while the request used
    to hardcode ``medical_v3.0``, so the provider rejected every extraction with
    MEDICAL_ASSET_UNAVAILABLE before any network call — normalized_facts stayed
    empty and the failure was silent.
    """

    version, dictionary = load_claim_dictionary()

    class _Backend:
        def __init__(self):
            self.calls = 0

        def complete_json(self, system_prompt, user_prompt):
            del system_prompt, user_prompt
            self.calls += 1
            return {"status": "success", "facts": [], "warnings": []}

    backend = _Backend()
    provider = QwenUnderstandingProvider(
        backend=backend,
        provider_kind="cloud",
        provider_name="qwen",
        model="test-model",
        claim_dictionary_version=version,
        claim_dictionary=dictionary,
    )
    chain = UnderstandingProviderChain(cloud=provider, local=None)

    facts = _run_provider(
        chain, source_id="src_test", source_type="document", text="近期入睡困难。"
    )

    assert facts == []
    # reached the provider instead of failing the version gate
    assert backend.calls == 1


def test_extraction_request_uses_the_chain_claim_dictionary_version():
    """The version comes from the chain, not from a fixed literal."""

    chain = SimpleNamespace(
        providers=[SimpleNamespace(claim_dictionary_version="3.0.0")]
    )
    seen = {}

    def complete_json(request):
        seen["request"] = request
        return UnderstandingProviderResponse(status="success", facts=[], warnings=[])

    chain.complete_json = complete_json

    _run_provider(chain, source_id="src_test", source_type="document", text="材料")

    assert seen["request"].allowed_claim_dictionary_version == "3.0.0"


def test_document_case_summary_uses_normalized_facts_instead_of_ocr(
    monkeypatch, db_session_factory
):
    monkeypatch.setattr(
        understanding_service, "build_provider_chain", lambda: _mock_chain()
    )
    headers, session_id = _setup_guest()
    db = db_session_factory()
    user_pk = _user_pk(db, headers)
    document_id = _seed_document(
        db,
        user_pk=user_pk,
        session_id=session_id,
        ocr_text="九、诊断\n十、处理意见\n1.肝郁气滞\n近期入睡困难，白天精神不足。",
    )
    db.close()

    response = _post(headers, session_id, [_document_source(document_id)])
    assert response.status_code == 201, response.text
    summary = _v3_data(response)["case_summary"]["summary"]

    assert summary == "资料中记录的近期状态：睡眠后仍感疲惫。"
    for forbidden in ("九、诊断", "处理意见", "肝郁气滞", "近期入睡困难"):
        assert forbidden not in summary

    confirmed = _confirm(headers, _v3_data(response)["understanding_id"])
    assert confirmed.status_code == 201, confirmed.text
    confirmed_summary = _v3_data(confirmed)["understanding"]["case_summary"]["summary"]
    assert confirmed_summary == "资料中记录的近期状态：睡眠后仍感疲惫。"


def test_document_case_summary_falls_back_to_ocr_when_no_facts(
    monkeypatch, db_session_factory
):
    monkeypatch.setattr(
        understanding_service,
        "build_provider_chain",
        lambda: _mock_chain(facts=[]),
    )
    headers, session_id = _setup_guest()
    db = db_session_factory()
    user_pk = _user_pk(db, headers)
    document_id = _seed_document(
        db, user_pk=user_pk, session_id=session_id,
        ocr_text="主诉：近期睡眠恢复不足。",
    )
    db.close()

    response = _post(headers, session_id, [_document_source(document_id)])
    assert response.status_code == 201, response.text
    understanding = _v3_data(response)
    assert understanding["normalized_facts"] == []
    summary = understanding["case_summary"]["summary"]

    assert not summary.startswith("资料中记录的近期状态：")
    assert "睡眠恢复不足" in summary
    assert understanding["degradation"] == {
        "active": True,
        "reason_codes": ["FACT_EXTRACTION_EMPTY_CLAIMS"],
    }


def test_extraction_reports_provider_not_called():
    facts, reasons = extract_facts_for_sources(None, [_resolved_document()])

    assert facts == []
    assert reasons == ["FACT_EXTRACTION_PROVIDER_NOT_CALLED"]


def test_extraction_reports_schema_invalid_from_provider_chain():
    class _FailingChain:
        providers = [SimpleNamespace(claim_dictionary_version="3.0.0")]
        last_failure_codes = ["MODEL_SCHEMA_INVALID"]

        def complete_json(self, request):
            del request
            raise ProviderFailureV3(
                "PROVIDER_UNAVAILABLE",
                retryable=True,
                safe_message="provider failed",
            )

    facts, reasons = extract_facts_for_sources(
        _FailingChain(), [_resolved_document()]
    )

    assert facts == []
    assert reasons == ["FACT_EXTRACTION_SCHEMA_INVALID"]


def test_extraction_reports_claim_dictionary_mismatch():
    class _MismatchChain:
        providers = [SimpleNamespace(claim_dictionary_version="3.0.0")]
        last_failure_codes = []

        def complete_json(self, request):
            del request
            raise ProviderFailureV3(
                "MEDICAL_ASSET_UNAVAILABLE",
                retryable=False,
                safe_message="claim dictionary version mismatch",
            )

    facts, reasons = extract_facts_for_sources(
        _MismatchChain(), [_resolved_document()]
    )

    assert facts == []
    assert reasons == ["FACT_EXTRACTION_CLAIM_DICTIONARY_MISMATCH"]


def test_extraction_reports_normalization_filtered_all_facts():
    class _InvalidFactsChain:
        providers = [SimpleNamespace(claim_dictionary_version="3.0.0")]
        last_provider_kind = "cloud"

        def complete_json(self, request):
            del request
            return UnderstandingProviderResponse(
                status="success",
                facts=[],
                warnings=[],
            ).model_copy(update={"facts": [SimpleNamespace() ]})

    facts, reasons = extract_facts_for_sources(
        _InvalidFactsChain(), [_resolved_document()]
    )

    assert facts == []
    assert reasons == ["FACT_EXTRACTION_NORMALIZATION_FILTERED_ALL"]


def _real_dictionary_chain(facts_payload):
    """A real Qwen understanding Provider over the approved claim dictionary.

    Returns ``(chain, backend)``; the backend never performs a network call.
    """

    version, dictionary = load_claim_dictionary()

    class _Backend:
        def __init__(self):
            self.calls = 0

        def complete_json(self, system_prompt, user_prompt):
            del system_prompt, user_prompt
            self.calls += 1
            return {"status": "success", "facts": facts_payload, "warnings": []}

    backend = _Backend()
    provider = QwenUnderstandingProvider(
        backend=backend,
        provider_kind="cloud",
        provider_name="qwen",
        model="test-model",
        claim_dictionary_version=version,
        claim_dictionary=dictionary,
    )
    return UnderstandingProviderChain(cloud=provider, local=None), backend


def _dictionary_metadata_mismatched_facts():
    """Approved claims whose dictionary metadata the model plausibly guessed wrong.

    ``unrefreshing_sleep`` / ``low_energy`` are real approved claim codes; the
    display_name/category/value.type the model "chose" are not the dictionary's.
    """

    return [
        {
            "claim_code": "unrefreshing_sleep",
            "display_name": "睡眠后仍感疲惫",
            "category": "sleep",
            "value": {"type": "severity", "value": "moderate"},
            "time_window": "past_7_days",
            "negated": False,
            "subject": "self",
            "span": {"start": 0, "end": 6},
            "extraction_confidence": 0.8,
        },
        {
            "claim_code": "low_energy",
            "display_name": "精力不足",
            "category": "energy",
            "value": {"type": "coded_text", "value": "mild"},
            "time_window": "past_7_days",
            "negated": False,
            "subject": "self",
            "span": {"start": 7, "end": 12},
            "extraction_confidence": 0.7,
        },
    ]


def test_metadata_mismatch_no_longer_loses_grounded_facts():
    chain, backend = _real_dictionary_chain(_dictionary_metadata_mismatched_facts())

    facts, reasons = extract_facts_for_sources(
        chain, [_resolved_document("近期睡眠不解乏，白天精力不足。")]
    )

    assert backend.calls == 1, "authoritative normalization must not need a repair"
    assert reasons == []
    assert [fact["fact_code"] for fact in facts] == ["unrefreshing_sleep", "low_energy"]
    assert [fact["display_name"] for fact in facts] == ["睡眠不解乏", "精力不足"]
    assert [fact["category"] for fact in facts] == [
        "physical_signal",
        "physical_signal",
    ]
    assert facts[0]["value"] == {"type": "severity", "value": "moderate"}
    assert facts[1]["value"] == {"type": "severity", "value": "mild"}
    assert facts[0]["extraction"]["method"] == "qwen"
    assert facts[0]["source_refs"] == [
        {"source_id": "src_test", "source_type": "document", "span_ref": None}
    ]
    assert chain.providers[0].last_metadata_normalizations == (
        "facts.0.display_name",
        "facts.0.category",
        "facts.1.category",
        "facts.1.value.type",
    )


def test_normalized_facts_feed_the_recent_state_summary():
    chain, _backend = _real_dictionary_chain(_dictionary_metadata_mismatched_facts())

    facts, reasons = extract_facts_for_sources(
        chain, [_resolved_document("近期睡眠不解乏，白天精力不足。")]
    )

    assert reasons == []
    assert summarize_facts(facts) == "资料中记录的近期状态：睡眠不解乏、精力不足。"


def test_unrepairable_provider_schema_still_falls_back_safely():
    payload = _dictionary_metadata_mismatched_facts()[:1]
    payload[0]["claim_code"] = "made_up_claim"
    chain, backend = _real_dictionary_chain(payload)

    facts, reasons = extract_facts_for_sources(
        chain, [_resolved_document("近期睡眠不解乏。")]
    )

    assert backend.calls == 2
    assert facts == []
    assert reasons == ["FACT_EXTRACTION_SCHEMA_INVALID"]


def test_document_understanding_publishes_facts_despite_metadata_mismatch(
    monkeypatch, db_session_factory
):
    chain, backend = _real_dictionary_chain(_dictionary_metadata_mismatched_facts())
    monkeypatch.setattr(understanding_service, "build_provider_chain", lambda: chain)
    headers, session_id = _setup_guest()
    db = db_session_factory()
    user_pk = _user_pk(db, headers)
    document_id = _seed_document(
        db, user_pk=user_pk, session_id=session_id,
        ocr_text="九、诊断\n十、处理意见\n1.肝郁气滞\n近期睡眠不解乏，白天精力不足。",
    )
    db.close()

    response = _post(headers, session_id, [_document_source(document_id)])
    assert response.status_code == 201, response.text
    understanding = _v3_data(response)

    assert backend.calls == 1
    assert understanding["degradation"] == {"active": False, "reason_codes": []}
    assert [fact["fact_code"] for fact in understanding["normalized_facts"]] == [
        "unrefreshing_sleep",
        "low_energy",
    ]
    assert understanding["normalized_facts"][0]["display_name"] == "睡眠不解乏"
    assert understanding["normalized_facts"][0]["category"] == "physical_signal"
    assert (
        understanding["case_summary"]["summary"]
        == "资料中记录的近期状态：睡眠不解乏、精力不足。"
    )


def test_understanding_fact_source_refs_commit_with_foreign_keys_enforced(
    monkeypatch, fk_enforced_api_database
):
    """FK-order regression for the create-understanding write batch.

    ``fact_source_refs.fact_row_id`` is a FK to ``normalized_facts.fact_row_id``
    and the two mappers have no ``relationship()``, so the ORM cannot derive a
    parent/child dependency: on the production engine (``PRAGMA
    foreign_keys=ON``, see ``backend/app/core/database.py``) a single implicit
    flush inserted the refs before their parents and the whole request failed
    with ``sqlite3.IntegrityError: FOREIGN KEY constraint failed`` — facts were
    extracted successfully and then lost with a 500.
    """

    session_factory, engine = fk_enforced_api_database
    inserted: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def _record_inserts(
        _conn, _cursor, statement, _parameters, _context, _executemany
    ):
        stripped = statement.lstrip()
        if stripped.upper().startswith("INSERT INTO"):
            inserted.append(stripped.split("(", 1)[0].split()[-1].strip().strip('"'))

    chain, backend = _real_dictionary_chain(_dictionary_metadata_mismatched_facts())
    monkeypatch.setattr(understanding_service, "build_provider_chain", lambda: chain)

    headers, session_id = _setup_guest()
    db = session_factory()
    user_pk = _user_pk(db, headers)
    document_id = _seed_document(
        db, user_pk=user_pk, session_id=session_id,
        ocr_text="九、诊断\n十、处理意见\n1.肝郁气滞\n近期睡眠不解乏，白天精力不足。",
    )
    db.close()
    inserted.clear()

    response = _post(headers, session_id, [_document_source(document_id)])

    assert response.status_code == 201, response.text
    understanding = _v3_data(response)
    assert backend.calls == 1
    assert [fact["fact_code"] for fact in understanding["normalized_facts"]] == [
        "unrefreshing_sleep",
        "low_energy",
    ]
    # the summary is composed from the persisted facts, not the OCR fallback
    assert (
        understanding["case_summary"]["summary"]
        == "资料中记录的近期状态：睡眠不解乏、精力不足。"
    )

    # parents are written before the children that reference them
    assert "normalized_facts" in inserted
    assert "fact_source_refs" in inserted
    assert max(
        index for index, table in enumerate(inserted) if table == "normalized_facts"
    ) < min(
        index for index, table in enumerate(inserted) if table == "fact_source_refs"
    )

    db = session_factory()
    try:
        # the assertions above are only meaningful with real FK enforcement
        assert db.execute(text("PRAGMA foreign_keys")).scalar() == 1
        with pytest.raises(IntegrityError):
            db.execute(
                text(
                    "INSERT INTO fact_source_refs "
                    "(fact_row_id, source_type, source_id) "
                    "VALUES ('factrow_orphan', 'document', 'src_orphan')"
                )
            )
            db.commit()
        db.rollback()

        fact_rows = db.query(NormalizedFactRow).all()
        assert len(fact_rows) == 2
        assert {row.fact_code for row in fact_rows} == {
            "unrefreshing_sleep",
            "low_energy",
        }
        assert {row.owner_type for row in fact_rows} == {"understanding"}
        assert {row.understanding_id for row in fact_rows} == {
            understanding["understanding_id"]
        }
        assert {row.understanding_revision for row in fact_rows} == {1}
        assert {row.extraction_method for row in fact_rows} == {"qwen"}

        refs = db.query(FactSourceRefRow).all()
        assert len(refs) == 2
        assert {ref.fact_row_id for ref in refs} == {
            row.fact_row_id for row in fact_rows
        }
        source_ids = {
            row.source_id
            for row in db.query(UnderstandingSourceRow).filter(
                UnderstandingSourceRow.understanding_id
                == understanding["understanding_id"]
            )
        }
        assert source_ids
        assert {ref.source_id for ref in refs} == source_ids
        assert {ref.source_type for ref in refs} == {"document"}
    finally:
        db.close()


def test_confirmed_revision_facts_commit_with_foreign_keys_enforced(
    monkeypatch, fk_enforced_api_database
):
    """The second ``persist_normalized_facts`` call site is FK-clean too.

    A confirmed full-text edit writes a new revision plus its own
    normalized_facts / fact_source_refs batch, so it must keep the same
    parent-before-child write order under ``PRAGMA foreign_keys=ON``.
    """

    session_factory, _engine = fk_enforced_api_database
    chain, backend = _real_dictionary_chain(_dictionary_metadata_mismatched_facts())
    monkeypatch.setattr(understanding_service, "build_provider_chain", lambda: chain)

    headers, session_id = _setup_guest()
    db = session_factory()
    user_pk = _user_pk(db, headers)
    document_id = _seed_document(
        db, user_pk=user_pk, session_id=session_id,
        ocr_text="近期睡眠不解乏，白天精力不足。",
    )
    db.close()

    understanding_id = _v3_data(
        _post(headers, session_id, [_document_source(document_id)])
    )["understanding_id"]

    response = _confirm(
        headers,
        understanding_id,
        decision="confirm_with_changes",
        edited_summary_text="资料中提到最近睡眠不解乏，白天精力不足。",
        reprocess_requested=True,
    )

    assert response.status_code == 201, response.text
    assert _v3_data(response)["revision"] == 2

    db = session_factory()
    try:
        assert db.execute(text("PRAGMA foreign_keys")).scalar() == 1
        fact_rows = (
            db.query(NormalizedFactRow)
            .filter(NormalizedFactRow.understanding_revision == 2)
            .all()
        )
        assert len(fact_rows) == 2
        refs = (
            db.query(FactSourceRefRow)
            .filter(
                FactSourceRefRow.fact_row_id.in_(
                    [row.fact_row_id for row in fact_rows]
                )
            )
            .all()
        )
        assert {ref.fact_row_id for ref in refs} == {
            row.fact_row_id for row in fact_rows
        }
    finally:
        db.close()
