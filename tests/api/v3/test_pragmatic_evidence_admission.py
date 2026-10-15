"""Offline pragmatic admission contract; all extraction uses controlled fakes."""

from backend.app.models.v3.understanding import UnderstandingRevision
from tests.api.v3.test_confirmation_infrastructure import _pending, _confirm
from tests.api.v3.test_owner_flow import _seed_db, _v3_data
from tests.api.v3.test_owner_flow import client
import pytest


def test_internal_json_roundtrip_and_legacy_read_are_private(monkeypatch):
    headers, _, run = _pending(monkeypatch)
    uid = run["understanding_id"]
    before = _v3_data(client.get(f"/api/v3/understandings/{uid}", headers=headers))
    marker = {"contract_version": "storage-probe", "run_id": uid,
              "revision": 1, "summary_checksum": "sha256:internal-only",
              "candidates": [{"fact_id": before["normalized_facts"][0]["fact_id"]}]}
    with _seed_db() as db:
        row = db.get(UnderstandingRevision, (uid, 1))
        row.presentation_json = {**row.presentation_json, "evidence_admission": marker}
        db.commit()
    with _seed_db() as db:
        assert db.get(UnderstandingRevision, (uid, 1)).presentation_json["evidence_admission"] == marker
    assert _v3_data(client.get(f"/api/v3/understandings/{uid}", headers=headers)) == before
    with _seed_db() as db:
        row = db.get(UnderstandingRevision, (uid, 1))
        row.presentation_json = {**row.presentation_json, "evidence_admission": {"partial": True}}
        db.flush()
        db.rollback()
    with _seed_db() as db:
        assert db.get(UnderstandingRevision, (uid, 1)).presentation_json["evidence_admission"] == marker


@pytest.mark.parametrize("text", [
    "就诊日期：2024-08-21；导出日期：2026-10-03。",
    "就诊日期：2024-08-21；就诊日期：2026-10-03。",
    "出生日期：2026-10-03；主诉：疲惫。",
])
def test_ambiguous_or_metadata_dates_never_claim_recent(text):
    from datetime import date
    from backend.app.services.v3.document_summary import document_time_context
    assert document_time_context(text, today=date(2026, 10, 5))[0] == "source_recorded"


def test_reextraction_preserves_document_time_context():
    from tests.api.v3.test_understanding_ai_extraction import _mock_chain, _mock_fact
    from backend.app.services.v3.understanding_extraction import re_extract_facts
    chain = _mock_chain(facts=[_mock_fact().model_copy(update={"time_window": "source_recorded"})])
    facts, _ = re_extract_facts(chain, "睡眠后仍感疲惫。", source_time_window="source_recorded")
    assert facts[0]["time_window"] == "source_recorded"
    assert facts[0]["source_refs"][0]["span_ref"]


def test_missing_source_span_cannot_admit_a_candidate():
    from backend.app.services.v3.evidence_admission import admit_projection, AdmissionFailure
    from tests.api.v3.test_understanding_ai_extraction import _mock_fact
    fact = _mock_fact().model_dump(mode="json")
    fact.update(fact_id="new", fact_code=fact.pop("claim_code"), source_refs=[], confirmation_status="unconfirmed")
    with pytest.raises(AdmissionFailure):
        admit_projection([fact], sources={}, summary="睡眠后仍感疲惫。")


def test_admission_cas_failure_rolls_back_facts_and_audit(monkeypatch):
    from backend.app.services.v3 import understanding_service
    from backend.app.models.v3.understanding import NormalizedFact, UnderstandingRun
    headers, _, run = _pending(monkeypatch)
    uid = run["understanding_id"]
    def fail_cas(*args):
        raise understanding_service.InputRevisionConflict
    monkeypatch.setattr(understanding_service, "_cas_bind_understanding", fail_cas)
    response = _confirm(headers, uid, {"expected_revision": 1, "expected_input_revision": 3,
        "decision": "confirm_with_changes", "edited_summary_text": "睡眠后仍感疲惫。",
        "reprocess_requested": True})
    assert response.status_code == 409
    with _seed_db() as db:
        assert db.get(UnderstandingRevision, (uid, 2)) is None
        assert db.get(UnderstandingRun, uid).current_revision == 1
        assert db.query(NormalizedFact).filter_by(understanding_id=uid, understanding_revision=2).count() == 0


@pytest.mark.parametrize("text, negated, subject, value", [
    ("无睡眠后仍感疲惫。", False, "self", "moderate"),
    ("母亲睡眠后仍感疲惫。", False, "self", "moderate"),
    ("轻度睡眠后仍感疲惫。", False, "self", "severe"),
])
def test_reliably_identified_candidate_contradictions_block(text, negated, subject, value):
    import json
    from backend.app.services.v3.evidence_admission import admit_projection, AdmissionFailure
    fact = {"fact_id": "candidate", "fact_code": "sleep_unrefreshing", "display_name": "睡眠后仍感疲惫",
        "negated": negated, "subject": subject, "time_window": "source_recorded",
        "confirmation_status": "unconfirmed", "value": {"type": "severity", "value": value},
        "source_refs": [{"source_id": "source", "source_type": "user_correction",
            "span_ref": json.dumps({"start": 0, "end": len(text)})}]}
    with pytest.raises(AdmissionFailure):
        admit_projection([fact], sources={"source": {"kind": "user_correction", "text": text,
            "time_window": "source_recorded"}}, summary=text)


def test_explicit_positive_correction_cannot_keep_negative_current_fact():
    import json
    from backend.app.services.v3.evidence_admission import admit_projection, AdmissionFailure
    text = "无睡眠后仍感疲惫。"
    fact = {"fact_id": "old", "fact_code": "sleep_unrefreshing", "display_name": "睡眠后仍感疲惫",
        "negated": True, "subject": "self", "time_window": "source_recorded",
        "confirmation_status": "confirmed", "value": {"type": "severity", "value": "moderate"},
        "source_refs": [{"source_id": "doc", "source_type": "document",
            "span_ref": json.dumps({"start": 0, "end": len(text)})}]}
    with pytest.raises(AdmissionFailure):
        admit_projection([fact], sources={"doc": {"kind": "document", "text": text,
            "time_window": "source_recorded"}}, summary="睡眠后仍感疲惫。")


def test_summary_omission_keeps_independent_source_evidence():
    import json
    from backend.app.services.v3.evidence_admission import admit_projection
    text = "睡眠后仍感疲惫。"
    fact = {"fact_id": "old", "fact_code": "sleep_unrefreshing", "display_name": "睡眠后仍感疲惫",
        "negated": False, "subject": "self", "time_window": "source_recorded",
        "confirmation_status": "confirmed", "value": {"type": "severity", "value": "moderate"},
        "source_refs": [{"source_id": "doc", "source_type": "document",
            "span_ref": json.dumps({"start": 0, "end": len(text)})}]}
    facts, audit = admit_projection([fact], sources={"doc": {"kind": "document", "text": text,
        "time_window": "source_recorded"}}, summary="资料摘要已精简。")
    assert facts[0]["fact_id"] == "old"
    assert audit[0]["admission_actor"] == "system"


def test_provider_unavailable_never_writes_admission(monkeypatch):
    from backend.app.services.v3 import understanding_service
    headers, _, run = _pending(monkeypatch)
    uid = run["understanding_id"]
    monkeypatch.setattr(understanding_service, "build_provider_chain", lambda: None)
    response = _confirm(headers, uid, {"expected_revision": 1, "expected_input_revision": 3,
        "decision": "confirm_with_changes", "edited_summary_text": "睡眠后仍感疲惫。",
        "reprocess_requested": True})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "STRUCTURED_RECONCILIATION_FAILED"
    with _seed_db() as db:
        assert db.get(UnderstandingRevision, (uid, 2)) is None


def test_admitted_original_source_is_not_suppressed_downstream(monkeypatch, db_session_factory):
    from backend.app.services.v3 import understanding_service
    from backend.app.services.v3.diagnosis_service import _edited_summary_override
    from backend.app.models.v3.assessment import AssessmentV3, AssessmentRevisionV3
    from backend.app.models.v3.understanding import FactSourceRef, NormalizedFact, UnderstandingSource
    from tests.api.v3.test_assessment_summary_authority import create_summary_assessment
    headers, _, result = create_summary_assessment(monkeypatch, db_session_factory,
        "document", understanding_edit="近期仍有烦躁和胁肋不适。")
    confirmed = client.post(f"/api/v3/assessments/{result['assessment_id']}/confirmations", headers=headers,
        json={"expected_revision": 1, "expected_input_revision": result["input_revision"],
              "decision": "confirm", "changes": []})
    assert confirmed.status_code == 200, confirmed.text
    # Exercise the consumer boundary with an original-source ref instead of a
    # correction-only ref. Both are legal under the approved admission contract.
    with db_session_factory() as db:
        assessment = db.get(AssessmentV3, result["assessment_id"])
        upstream = db.get(UnderstandingRevision, (assessment.understanding_id, assessment.understanding_revision))
        source = db.query(UnderstandingSource).filter_by(understanding_id=assessment.understanding_id).one()
        row = db.query(NormalizedFact).filter_by(understanding_id=assessment.understanding_id,
            understanding_revision=assessment.understanding_revision).first()
        ref = db.query(FactSourceRef).filter_by(fact_row_id=row.fact_row_id).one()
        ref.source_id, ref.source_type = source.source_id, source.source_type
        # Original undated OCR is source_recorded, not the correction's recent
        # context. Keep the full persisted chain coherent for this legal case.
        row.time_window = "source_recorded"
        from backend.app.models.v3.assessment import FactEvidence
        for evidence in db.query(FactEvidence).filter_by(normalized_fact_row_id=row.fact_row_id):
            evidence.time_window = row.time_window
        snapshot = dict(upstream.presentation_json)
        import copy
        snapshot = copy.deepcopy(snapshot)
        for fact in snapshot["normalized_facts"]:
            if fact["fact_id"] == row.fact_id:
                fact["source_refs"][0].update(source_id=source.source_id, source_type=source.source_type)
                fact["time_window"] = row.time_window
        for candidate in snapshot["evidence_admission"]["candidates"]:
            if candidate["fact_id"] == row.fact_id:
                candidate["source_refs"][0].update(source_id=source.source_id, source_type=source.source_type)
                candidate["source_span"][0]["source_id"] = source.source_id
                candidate["source_checksums"] = [source.text_hash]
        upstream.presentation_json = snapshot
        db.flush()
        revision = db.get(AssessmentRevisionV3, (assessment.assessment_id, 1))
        assert _edited_summary_override(db, assessment, revision) is None


def test_one_click_edit_commits_system_admission_without_public_audit(monkeypatch):
    headers, _, run = _pending(monkeypatch)
    uid = run["understanding_id"]
    from tests.api.v3.test_understanding_ai_extraction import _mock_chain, _mock_fact
    from backend.app.services.v3 import understanding_service
    monkeypatch.setattr(understanding_service, "build_provider_chain", lambda: _mock_chain(
        facts=[_mock_fact().model_copy(update={"time_window": "source_recorded"})]))
    response = _confirm(headers, uid, {
        "expected_revision": 1, "expected_input_revision": 3,
        "decision": "confirm_with_changes", "changes": [],
        "edited_summary_text": "睡眠后仍感疲惫。", "reprocess_requested": True,
    })
    assert response.status_code == 201, response.text
    result = _v3_data(response)
    assert result["status"] == "confirmed"
    facts = result["understanding"]["normalized_facts"]
    assert facts and all(f["confirmation_status"] == "confirmed" for f in facts)
    assert "evidence_admission" not in response.text
    with _seed_db() as db:
        row = db.get(UnderstandingRevision, (uid, result["revision"]))
        audit = row.presentation_json["evidence_admission"]
        assert audit["confirmation_event"]["scope"] == "summary"
        assert audit["revision"] == result["revision"]
        assert audit["input_revision"] == result["input_revision"]
        assert {c["fact_id"] for c in audit["candidates"]} == {f["fact_id"] for f in facts}
        assert all(c["admission_actor"] == "system" for c in audit["candidates"])
        from hashlib import sha256
        assert audit["run_id"] == uid
        assert audit["summary_checksum"] == "sha256:" + sha256("睡眠后仍感疲惫。".encode()).hexdigest()
        from backend.app.models.v3.understanding import NormalizedFact
        assert {f.fact_id for f in db.query(NormalizedFact).filter_by(
            understanding_id=uid, understanding_revision=result["revision"]).all()} == {f["fact_id"] for f in facts}


def test_changed_ocr_checksum_blocks_before_reconciliation(monkeypatch):
    from backend.app.models.document import Document
    from backend.app.models.v3.understanding import UnderstandingSource
    from backend.app.services.v3 import understanding_service
    headers, _, run = _pending(monkeypatch)
    uid = run["understanding_id"]
    with _seed_db() as db:
        source = db.query(UnderstandingSource).filter_by(understanding_id=uid).one()
        document = db.query(Document).filter_by(document_id=source.document_id).one()
        document.ocr_text = "已经替换的原始资料。"
        db.commit()
    calls = []
    monkeypatch.setattr(understanding_service, "build_provider_chain", lambda: calls.append(True))
    response = _confirm(headers, uid, {"expected_revision": 1, "expected_input_revision": 3,
        "decision": "confirm_with_changes", "edited_summary_text": "睡眠后仍感疲惫。",
        "reprocess_requested": True})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "EVIDENCE_ADMISSION_FAILED"
    assert calls == []
    with _seed_db() as db:
        assert db.get(UnderstandingRevision, (uid, 2)) is None


def test_historical_encounter_is_not_replaced_by_print_date():
    from datetime import date
    from backend.app.services.v3.document_summary import document_time_context
    window, recorded = document_time_context(
        "就诊日期：2024-08-21；打印日期：2026-10-03。", today=date(2026, 10, 5)
    )
    assert window == "source_recorded"
    assert recorded == date(2024, 8, 21)


def test_explicit_current_correction_blocks_retained_opposite_fact():
    import json
    from backend.app.services.v3.evidence_admission import admit_projection, AdmissionFailure
    text = "睡眠后仍感疲惫。"
    fact = {"fact_id": "old", "fact_code": "sleep_unrefreshing", "display_name": "睡眠后仍感疲惫",
        "negated": False, "subject": "self", "time_window": "source_recorded",
        "confirmation_status": "confirmed", "value": {"type": "severity", "value": "moderate"},
        "source_refs": [{"source_id": "doc", "source_type": "document",
            "span_ref": json.dumps({"start": 0, "end": len(text)})}]}
    with pytest.raises(AdmissionFailure):
        admit_projection([fact], sources={"doc": {"kind": "document", "text": text,
            "time_window": "source_recorded"}}, summary="无睡眠后仍感疲惫。")


def test_print_date_alone_is_not_a_source_record_date():
    from datetime import date
    from backend.app.services.v3.document_summary import document_time_context
    assert document_time_context(
        "打印日期：2026-10-03；主诉：疲惫。", today=date(2026, 10, 5)
    ) == ("source_recorded", None)
