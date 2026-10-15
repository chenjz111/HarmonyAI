"""Offline consumer contract: audit presence alone must never release evidence."""
from copy import deepcopy
from types import SimpleNamespace
import uuid

import pytest

from backend.app.models import Session as SessionModel
from backend.app.models.document import Document
from backend.app.models.v3.assessment import AssessmentV3, AssessmentRevisionV3, FactEvidence
from backend.app.models.v3.understanding import UnderstandingRevision, UnderstandingRun, NormalizedFact, FactSourceRef, UnderstandingSource
from backend.app.services.v3 import diagnosis_service, understanding_service
from tests.api.v3.test_assessment_v3 import (
    client, _setup_guest, _confirmed_understanding, _assessment_body,
    _mock_chain, _provider_fact, _v3_data,
)


@pytest.fixture
def admitted(monkeypatch, db_session_factory, request):
    # Real confirmation preserves an omitted original historical fact, while
    # admitting a separate correction. No provenance rows are manufactured.
    initial = [_provider_fact("anger_tendency", "烦躁易怒倾向", "emotional_state", time_window="source_recorded"),
               _provider_fact("flank_discomfort", "胁肋不适", "somatic", time_window="source_recorded")]
    corrections = initial if getattr(request, "param", "mixed") == "correction" else initial[1:]
    chains = iter([_mock_chain(initial), _mock_chain(corrections)])
    monkeypatch.setattr(understanding_service, "build_provider_chain", lambda: next(chains))
    headers, session_id = _setup_guest()
    summary = "胁肋不适。资料摘要已精简。"
    with db_session_factory() as db:
        uid = _confirmed_understanding(headers, session_id, db, None,
            edited_summary_text=summary, ocr_text="就诊日期：2024-08-21。烦躁易怒。胁肋不适。")
    response = client.post("/api/v3/assessments", headers={**headers, "Idempotency-Key": uuid.uuid4().hex},
        json=_assessment_body(session_id, uid, 3))
    assert response.status_code == 201, response.text
    result = _v3_data(response)
    response = client.post(f"/api/v3/assessments/{result['assessment_id']}/confirmations", headers=headers,
        json={"expected_revision": 1, "expected_input_revision": 3, "decision": "confirm", "changes": []})
    assert response.status_code == 200, response.text
    return headers, session_id, uid, result["assessment_id"], summary


def _rows(db, case):
    _, sid, uid, aid, _ = case
    return (db.get(AssessmentV3, aid), db.get(AssessmentRevisionV3, (aid, 1)),
            db.get(UnderstandingRevision, (uid, 2)), db.query(SessionModel).filter_by(session_id=sid).one())


def test_natural_admission_consumes_both_sources_and_keeps_public_summary(admitted, db_session_factory):
    with db_session_factory() as db:
        assessment, revision, upstream, session = _rows(db, admitted)
        assert diagnosis_service._edited_summary_override(db, assessment, revision) is None
        state = diagnosis_service._load_confirmed_user_state(db, assessment=assessment,
            assessment_revision=revision, session_row=session)
        assert {f.claim_code for f in state.normalized_projection} == {"anger_tendency", "flank_discomfort"}
        assert state.confirmed_state_text == admitted[-1]
        refs = db.query(FactSourceRef).join(NormalizedFact).filter(NormalizedFact.understanding_revision == 2).all()
        assert {r.source_type for r in refs} == {"document", "user_correction"}


@pytest.mark.parametrize("damage", [
    "missing", "unsupported", "malformed", "run", "revision", "input", "previous",
    "summary_checksum", "event", "event_checksum", "missing_candidate", "extra_candidate", "duplicate",
    "blocked", "reason", "actor", "basis", "checks", "span", "source_checksum", "source_ref",
    "projection_value", "projection_polarity", "stale_run", "stale_input", "old_fact",
    "unconfirmed", "rejected", "evidence_value", "evidence_direction", "ocr_changed", "temporal",
    "evidence_rejected", "event_missing", "binding", "source_owner", "no_fact_refs", "untracked_fact",
])
@pytest.mark.parametrize("admitted", ["mixed", "correction"], indirect=True)
def test_invalid_admission_cannot_release_projection(admitted, db_session_factory, damage):
    with db_session_factory() as db:
        assessment, revision, upstream, session = _rows(db, admitted)
        presentation = deepcopy(upstream.presentation_json)
        audit = presentation["evidence_admission"]
        candidate = audit["candidates"][0]
        row = db.query(NormalizedFact).filter_by(understanding_id=admitted[2], understanding_revision=2,
            fact_id=candidate["fact_id"]).one()
        evidence = db.query(FactEvidence).filter_by(normalized_fact_row_id=row.fact_row_id).one()
        if damage == "missing": presentation.pop("evidence_admission")
        elif damage == "unsupported": audit["contract_version"] = "future"
        elif damage == "malformed": presentation["evidence_admission"] = ["bad"]
        elif damage in {"run", "revision", "input", "previous"}:
            key = {"run": "run_id", "revision": "revision", "input": "input_revision", "previous": "previous_revision"}[damage]
            audit[key] = "wrong"
        elif damage == "summary_checksum": audit["summary_checksum"] = "sha256:wrong"
        elif damage == "event": audit["confirmation_event"]["scope"] = "facts"
        elif damage == "event_checksum": audit["confirmation_event"]["request_checksum"] = "sha256:wrong"
        elif damage == "missing_candidate": audit["candidates"].pop()
        elif damage == "extra_candidate": audit["candidates"].append({**candidate, "fact_id": "hidden"})
        elif damage == "duplicate": audit["candidates"].append(deepcopy(candidate))
        elif damage == "blocked": candidate["disposition"] = "blocked"
        elif damage == "reason": candidate["reason_codes"] = ["EXPLICIT_CURRENT_CORRECTION"]
        elif damage == "actor": candidate["admission_actor"] = "user"
        elif damage == "basis": candidate["admission_basis"] = "unknown"
        elif damage == "checks": candidate["checks_performed"] = []
        elif damage == "span": candidate["source_span"][0]["end"] = 99999
        elif damage == "source_checksum": candidate["source_checksums"] = ["sha256:wrong"]
        elif damage == "source_ref": candidate["source_refs"][0]["source_id"] = "forged"
        elif damage == "projection_value": presentation["normalized_facts"][0]["value"]["value"] = 0
        elif damage == "projection_polarity": presentation["normalized_facts"][0]["negated"] = True
        elif damage == "stale_run": db.get(UnderstandingRun, admitted[2]).current_revision = 1
        elif damage == "stale_input": session.input_revision += 1
        elif damage == "old_fact":
            old = db.query(NormalizedFact).filter_by(understanding_id=admitted[2], understanding_revision=1).first()
            evidence.normalized_fact_row_id = old.fact_row_id
        elif damage in {"unconfirmed", "rejected"}: row.confirmation_status = damage
        elif damage == "evidence_value": evidence.value_json = {"type": "frequency_0_4", "value": 0}
        elif damage == "evidence_direction": evidence.direction = "contradicting"
        elif damage == "ocr_changed": db.query(Document).filter_by(session_id=admitted[1]).one().ocr_text = "替换后的资料"
        elif damage == "temporal":
            row.time_window = evidence.time_window = "past_7_days"
            for fact in presentation["normalized_facts"]:
                if fact["fact_id"] == row.fact_id: fact["time_window"] = "past_7_days"
        elif damage == "evidence_rejected": evidence.confirmation_status = "rejected"
        elif damage == "event_missing":
            from backend.app.models.v3.session import V3IdempotencyRecord
            db.query(V3IdempotencyRecord).filter_by(operation=f"confirm_v3_understanding:{admitted[2]}").delete()
        elif damage == "binding":
            from backend.app.models.v3.session import SessionInputRevision
            db.get(SessionInputRevision, (session.id, session.input_revision)).active_understanding_revision = 1
        elif damage == "source_owner": db.query(UnderstandingSource).filter_by(understanding_id=admitted[2]).one().processing_status = "skipped"
        elif damage == "no_fact_refs": db.query(FactSourceRef).filter_by(fact_row_id=row.fact_row_id).delete()
        elif damage == "untracked_fact":
            extra = db.query(NormalizedFact).filter_by(understanding_id=admitted[2], understanding_revision=1,
                fact_code="flank_discomfort").one()
            extra.understanding_revision = 2
            extra.confirmation_status = "confirmed"
        upstream.presentation_json = presentation
        db.flush()
        correction_only = all(r.source_type == "user_correction" for r in db.query(FactSourceRef).join(NormalizedFact)
            .filter(NormalizedFact.understanding_revision == 2).all())
        # Missing audit is genuinely legacy: its existing correction-only
        # qualification remains valid. An invalid *present* audit never opts in.
        legacy = damage == "missing" and correction_only
        # Changes to unused original OCR do not invalidate correction-only facts.
        unused_original = correction_only and damage == "ocr_changed"
        allowed = legacy or unused_original
        assert diagnosis_service._edited_summary_override(db, assessment, revision) == (None if allowed else admitted[-1])
        state = diagnosis_service._load_confirmed_user_state(db, assessment=assessment,
            assessment_revision=revision, session_row=session) if damage != "stale_run" else None
        if state is not None:
            assert bool(state.normalized_projection) == allowed
            assert state.confirmed_state_text == admitted[-1]


def test_explicit_correction_cannot_be_bypassed_by_coherent_forged_projection(admitted, db_session_factory):
    from backend.app.services.v3.evidence_admission import checksum
    with db_session_factory() as db:
        assessment, revision, upstream, session = _rows(db, admitted)
        text = "无烦躁易怒。"
        presentation = deepcopy(upstream.presentation_json)
        presentation["evidence_admission"]["summary_checksum"] = checksum(text)
        upstream.case_summary_json = {**upstream.case_summary_json, "summary": text}
        upstream.presentation_json = presentation
        revision.presentation_json = {**revision.presentation_json, "summary": text}
        revision.state_summary = text
        db.flush()
        assert diagnosis_service._edited_summary_override(db, assessment, revision) == text


def test_admission_cannot_outlive_active_document_input(admitted, db_session_factory):
    with db_session_factory() as db:
        assessment, revision, upstream, session = _rows(db, admitted)
        session.active_document_set_id = None
        db.flush()
        assert diagnosis_service._edited_summary_override(db, assessment, revision) == admitted[-1]


@pytest.mark.parametrize("blocked", [False, True])
def test_new_assessment_revision_cannot_bypass_admission(admitted, db_session_factory, blocked):
    headers, _, _, aid, summary = admitted
    response = client.post(f"/api/v3/assessments/{aid}/confirmations", headers=headers,
        json={"expected_revision": 1, "expected_input_revision": 3,
              "decision": "confirm_with_changes", "changes": [], "edited_summary_text": summary})
    assert response.status_code == 201, response.text
    with db_session_factory() as db:
        assessment, _, upstream, _ = _rows(db, admitted)
        revision = db.get(AssessmentRevisionV3, (aid, 2))
        if blocked:
            presentation = deepcopy(upstream.presentation_json)
            presentation["evidence_admission"]["candidates"][0]["disposition"] = "blocked"
            upstream.presentation_json = presentation
            db.flush()
        assert diagnosis_service._edited_summary_override(db, assessment, revision) == (summary if blocked else None)


def test_assessment_to_diagnosis_router_consumes_admitted_historical_evidence(admitted, monkeypatch, db_session_factory):
    from backend.app.core import agent_config
    from backend.ai_engine.v3.diagnosis_provider import DiagnosisProvider
    from tests.api.v3.test_diagnosis_v31_pipeline_entry import _manifest, _rag_result
    from tests.api.v3.test_diagnosis_v3 import _diagnosis_body
    from tests.ai_engine.v3.test_v31_pipeline import _mapping, _rules
    import json
    captured = []
    class Rag:
        manifest = _manifest()
        approved_chunk_ids = {"chunk_1"}
        chunk_checksums = {}
        chunk_text_checksums = {}
        def query(self, query, **kwargs): return _rag_result()
    class Backend:
        async def acomplete_json(self, system_prompt, user_prompt):
            captured.append(json.loads(user_prompt))
            return {"status": "success", "candidate_tendencies": [{"syndrome_code": "syndrome_1",
                "display_name": "测试倾向", "relative_support": 0.8, "supporting_fact_ids": [],
                "contradicting_fact_ids": [], "knowledge_chunk_ids": ["chunk_1"], "reasoning_summary": "依据确认资料整理。"}],
                "abstained": False, "abstain_reason": None}
    provider = DiagnosisProvider(backend=Backend(), allowed_syndrome_codes={"syndrome_1"},
        allowed_fact_ids=set(), allowed_chunk_ids={"chunk_1"}, medical_rule_version="test")
    monkeypatch.setattr(diagnosis_service, "_v31_real_mode", lambda: True)
    monkeypatch.setattr(agent_config, "get_v31_ai_pipeline_dependencies", lambda: SimpleNamespace(
        rag_store=Rag(), diagnosis_provider=provider, tone_mapping=_mapping(), generation_parameter_rules=_rules(),
        allowed_syndrome_codes={"syndrome_1"}, medical_rule_version="test"))
    headers, sid, _, aid, summary = admitted
    response = client.post("/api/v3/diagnoses", headers={**headers, "Idempotency-Key": uuid.uuid4().hex},
        json=_diagnosis_body(sid, aid, 3))
    assert response.status_code == 201, response.text
    assert captured
    assert captured[0]["confirmed_state_text"] == summary
    assert {f["claim_code"] for f in captured[0]["facts"]} == {"anger_tendency", "flank_discomfort"}
    assert {f["time_window"] for f in captured[0]["facts"]} == {"source_recorded"}
    assert "近期" not in captured[0]["confirmed_state_text"]
