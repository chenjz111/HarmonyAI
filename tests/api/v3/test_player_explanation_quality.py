"""API integration over disposable DB + fake transport, never live providers."""

import json

from backend.ai_engine.v3.grounding import canonical_checksum
from backend.app.models.v3.assessment import FactEvidence as FactEvidenceRow
from backend.app.models.v3.understanding import NormalizedFact, FactSourceRef
from tests.api.v3.test_phase4_evidence_kernel import _Harness, _candidate, _body
from tests.api import conftest as api_conftest  # noqa: F401


def test_historical_explanation_persists_and_get_does_not_rewrite_checksum(db_session_factory, monkeypatch):
    harness = _Harness(db_session_factory, monkeypatch, payloads=[], organ_support={"spleen": 1.8, "liver": 1.5})
    db = db_session_factory()
    try:
        rows = db.query(FactEvidenceRow).filter_by(assessment_id=harness.assessment_id).all()
        for row in rows:
            row.time_window = "source_recorded"
            source = db.get(NormalizedFact, row.normalized_fact_row_id)
            source.time_window = "source_recorded"
            for ref in db.query(FactSourceRef).filter_by(fact_row_id=source.fact_row_id).all():
                ref.source_type = "document"
                ref.source_id = "historical_doc"
                ref.span_ref = "record:2024-08-21"
        db.commit()
    finally:
        db.close()
    harness.use([{"status": "success", "candidate_tendencies": [_candidate(knowledge_chunk_ids=["chunk_1"])], "abstained": False, "abstain_reason": None}])
    response = harness.post()
    assert response.status_code == 201, response.text
    diagnosis_id = _body(response)["diagnosis_id"]
    row = harness.run_row(diagnosis_id)
    before = json.loads(json.dumps(row.five_tone_read_model_json))
    checksum = row.five_tone_read_model_checksum
    assert before["regulation_mode"] == "personalized_five_tone"
    assert before["primary_tone"]["tone"] == "gong"
    assert "资料" in before["state_tendency"] and "思虑" in before["state_tendency"]
    assert "近期" not in before["state_tendency"]
    assert "脾" in before["analysis_rationales"][0]["summary"]
    assert "已根据" not in before["analysis_rationales"][0]["summary"]
    assert before["bpm"]["value"] == 60
    assert before["bpm"]["explanation"] is None
    assert checksum == canonical_checksum(before)
    calls = harness.provider.calls
    read = harness.client.get(f"/api/v3/diagnoses/{diagnosis_id}/five-tone-analysis", headers=harness.headers)
    assert read.status_code == 200, read.text
    assert _body(read) == before
    assert harness.provider.calls == calls
    assert harness.run_row(diagnosis_id).five_tone_read_model_checksum == checksum
    assert harness.run_row(diagnosis_id).five_tone_read_model_json == before


def test_negated_source_fact_is_excluded_from_public_positive_reasons(db_session_factory, monkeypatch):
    harness = _Harness(db_session_factory, monkeypatch, payloads=[], organ_support={"spleen": 1.8, "liver": 1.5})
    db = db_session_factory()
    try:
        row = db.query(FactEvidenceRow).filter_by(assessment_id=harness.assessment_id, claim_code="overthinking_tendency").one()
        excluded_id = row.fact_evidence_id
        db.get(NormalizedFact, row.normalized_fact_row_id).negated = 1
        db.commit()
    finally:
        db.close()
    harness.use([{"status": "success", "candidate_tendencies": [_candidate(knowledge_chunk_ids=["chunk_1"])], "abstained": False, "abstain_reason": None}])
    response = harness.post()
    assert response.status_code == 201, response.text
    read = harness.run_row(_body(response)["diagnosis_id"]).five_tone_read_model_json
    assert "思虑" not in read["state_tendency"]
    assert excluded_id not in read["analysis_rationales"][0]["evidence_refs"]


def test_unknown_and_negated_historical_basis_keep_one_limit_through_persistence_and_get(db_session_factory, monkeypatch):
    harness = _Harness(db_session_factory, monkeypatch, payloads=[], organ_support={"spleen": 1.8, "liver": 1.5})
    db = db_session_factory()
    try:
        rows = db.query(FactEvidenceRow).filter_by(assessment_id=harness.assessment_id).all()
        for row in rows:
            source = db.get(NormalizedFact, row.normalized_fact_row_id)
            row.time_window = source.time_window = "source_recorded"
            if row.claim_code == "overthinking_tendency":
                source.subject = "unknown"
            elif row.claim_code == "poor_appetite":
                source.negated = 1
        db.commit()
    finally:
        db.close()
    harness.use([{"status": "success", "candidate_tendencies": [_candidate(knowledge_chunk_ids=["chunk_1"])], "abstained": False, "abstain_reason": None}])
    response = harness.post()
    assert response.status_code == 201, response.text
    diagnosis_id = _body(response)["diagnosis_id"]
    row = harness.run_row(diagnosis_id)
    stored = row.five_tone_read_model_json
    texts = [stored["analysis_rationales"][0]["summary"], stored["mode_explanation"]["explanation"], stored["primary_tone"]["explanation"]]
    assert sum(text.count("缺少可公开引用的具体状态依据") for text in texts) == 1
    assert stored["primary_tone"]["tone"] == "gong"
    assert "脾对应宫调" in texts[2]
    assert "思虑" not in stored["state_tendency"] and "食欲" not in stored["state_tendency"]
    assert "资料记录" in stored["state_tendency"] and "近期" not in stored["state_tendency"]
    assert row.five_tone_read_model_checksum == canonical_checksum(stored)
    calls = harness.provider.calls
    read = harness.client.get(f"/api/v3/diagnoses/{diagnosis_id}/five-tone-analysis", headers=harness.headers)
    assert read.status_code == 200 and _body(read) == stored
    assert harness.provider.calls == calls
