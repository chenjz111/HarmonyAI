"""Actual persisted diagnosis snapshots carry current text and current facts."""
from types import SimpleNamespace
import asyncio
import json
import pytest

from backend.app.models.v3.assessment import AssessmentV3, AssessmentRevisionV3
from backend.app.models import Session as SessionModel
from backend.app.services.v3.diagnosis_service import (
    _build_v31_assessment_snapshot,
    _load_confirmed_user_state,
)
from backend.ai_engine.v3.diagnosis_pipeline import build_diagnosis_query, execute_diagnosis_provider
from backend.ai_engine.v3.diagnosis_provider import DiagnosisProvider
from tests.api.v3.test_assessment_summary_authority import create_summary_assessment, client, _v3_data
from tests.api.v3.test_diagnosis_v31_pipeline_entry import _manifest, _rag_result


@pytest.mark.parametrize("mode", ["document", "questionnaire", "combined"])
@pytest.mark.parametrize("edited", [False, True])
def test_actual_diagnosis_input_uses_current_persisted_summary(monkeypatch, db_session_factory, mode, edited):
    questionnaire_options = (
        {7: ["palpitation_at_rest"], 8: ["postmeal_heaviness"]}
        if mode == "questionnaire"
        else None
    )
    headers, session_id, original = create_summary_assessment(
        monkeypatch,
        db_session_factory,
        mode,
        questionnaire_options=questionnaire_options,
    )
    text = (
        "近期仅有餐后困重。"
        if edited and mode == "questionnaire"
        else "近期仅有胁肋不适、胁肋胀闷不适，休息后缓解。"
        if edited
        else original["state_summary"]
    )
    body = {"expected_revision": 1, "expected_input_revision": original["input_revision"],
            "decision": "confirm_with_changes" if edited else "confirm", "changes": []}
    if edited:
        body["edited_summary_text"] = text
    result = client.post(f"/api/v3/assessments/{original['assessment_id']}/confirmations", headers=headers, json=body)
    assert result.status_code in {200, 201}, result.text
    current = _v3_data(result)
    captured = []
    class Backend:
        async def acomplete_json(self, system_prompt, user_prompt):
            captured.append(json.loads(user_prompt))
            return {"status": "success", "candidate_tendencies": [{
                "syndrome_code": "syndrome_1", "display_name": "测试倾向", "relative_support": 0.8,
                "supporting_fact_ids": [], "contradicting_fact_ids": [],
                "knowledge_chunk_ids": ["chunk_1"], "reasoning_summary": "依据当前确认状态整理的倾向。",
            }], "abstained": False, "abstain_reason": None}
    provider = DiagnosisProvider(backend=Backend(), allowed_syndrome_codes={"syndrome_1"},
                                allowed_fact_ids=set(), allowed_chunk_ids={"chunk_1"})
    with db_session_factory() as db:
        assessment = db.get(AssessmentV3, original["assessment_id"])
        revision = db.query(AssessmentRevisionV3).filter_by(assessment_id=original["assessment_id"], revision=current["revision"]).one()
        snapshot = _build_v31_assessment_snapshot(db, request=SimpleNamespace(diagnosis_id="diag_authority"),
            assessment=assessment, assessment_revision=revision, deps=SimpleNamespace(
                rag_store=SimpleNamespace(manifest=_manifest(), approved_chunk_ids={"chunk_1"}),
                diagnosis_provider=provider, medical_rule_version="test", allowed_syndrome_codes={"syndrome_1"}))
        confirmed_state = _load_confirmed_user_state(
            db, assessment=assessment, assessment_revision=revision,
            session_row=db.query(SessionModel).filter_by(session_id=session_id).one(),
        )
    # PR-022: an edited confirmed summary is the downstream current-state
    # authority. Persisted structured rows remain provenance, but they cannot
    # override or reactivate state the user removed from the text.
    assert snapshot["confirmed_state_text"] == (
        text if edited else current["state_summary"]
    )
    query = build_diagnosis_query(snapshot)
    expected_codes = (
        {"palpitation_at_rest", "postmeal_heaviness"}
        if mode == "questionnaire"
        else {"anger_tendency", "flank_discomfort"}
    )
    active_codes = set() if edited else expected_codes
    assert set(query.claim_codes) == active_codes
    assert {f["claim_code"] for f in snapshot["facts"]} == active_codes
    assert {
        f.claim_code for f in confirmed_state.normalized_projection
    } == {f["claim_code"] for f in snapshot["facts"]}
    active_ids = {f["fact_evidence_id"] for f in current["fact_evidence"]}
    assert active_ids, "PR-022 keeps original evidence rows as provenance"
    assert set(query.supporting_fact_ids) | set(query.contradicting_fact_ids) == (
        set() if edited else active_ids
    )
    execution = asyncio.run(execute_diagnosis_provider(provider=provider, request={"assessment_id": original["assessment_id"]},
        facts=snapshot["facts"], rag_result=_rag_result(), confirmed_state_text=snapshot["confirmed_state_text"]))
    assert execution.status == "success"
    assert captured[0]["confirmed_state_text"] == snapshot["confirmed_state_text"]
    assert {f["claim_code"] for f in captured[0]["facts"]} == active_codes
    if edited:
        assert text in json.dumps(captured[0], ensure_ascii=False)
        removed = "palpitation_at_rest" if mode == "questionnaire" else "anger_tendency"
        assert removed not in json.dumps(captured[0])
