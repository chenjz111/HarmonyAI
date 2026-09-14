"""Three source modes compose meaningful summaries and preserve old evidence."""
import uuid
import pytest

from backend.app.models import Session as SessionModel
from backend.app.models.v3.assessment import FactEvidence as FactEvidenceRow
from backend.app.services.v3 import understanding_service
from tests.api.v3.test_assessment_v3 import (
    client, _setup_guest, _confirmed_understanding, _seed_questionnaire,
    _assessment_body, _v3_data, _mock_chain, _provider_fact,
)


def create_summary_assessment(
    monkeypatch,
    db_session_factory,
    mode,
    understanding_edit=None,
    questionnaire_options=None,
):
    monkeypatch.setattr(understanding_service, "build_provider_chain", lambda: _mock_chain([
        _provider_fact("anger_tendency", "烦躁易怒倾向", "emotional_state"),
        _provider_fact("flank_discomfort", "胁肋不适", "somatic"),
    ]))
    headers, session_id = _setup_guest()
    with db_session_factory() as db:
        understanding_id = None if mode == "questionnaire" else _confirmed_understanding(headers, session_id, db, facts=None, edited_summary_text=understanding_edit)
        body = _assessment_body(session_id, understanding_id, 3) if understanding_id else {
            "schema_version": "assessment_v3.1", "session_id": session_id,
            "expected_input_revision": 2, "understanding_ref": None,
        }
        if mode != "document":
            selected_by_question = questionnaire_options or {6: ["flank_discomfort"]}
            answers = [
                {"question_id": f"q{i:02d}", "answer_type": "frequency_0_4", "value": 3 if questionnaire_options is None and i == 1 else 0}
                for i in range(1, 6)
            ] + [
                {"question_id": f"q{i:02d}", "answer_type": "multi_choice_evidence", "value": selected_by_question.get(i, ["none"])}
                for i in range(6, 11)
            ]
            qid, manifest = _seed_questionnaire(db, headers=headers, session_id=session_id, answers=answers)
            body["questionnaire_ref"] = {"questionnaire_submission_id": qid, **{k: manifest[k] for k in ["schema_id", "schema_version", "manifest_version", "content_checksum"]}}
            if not understanding_id:
                session = db.query(SessionModel).filter_by(session_id=session_id).one()
                session.input_mode = "without_document"
                session.input_revision = 2
                session.active_questionnaire_submission_id = qid
                db.commit()
    response = client.post("/api/v3/assessments", headers={**headers, "Idempotency-Key": uuid.uuid4().hex}, json=body)
    assert response.status_code == 201, response.text
    return headers, session_id, _v3_data(response)


@pytest.mark.parametrize("mode", ["document", "questionnaire", "combined"])
def test_initial_summary_reflects_each_source_mode(monkeypatch, db_session_factory, mode):
    headers, _, result = create_summary_assessment(monkeypatch, db_session_factory, mode)
    text = result["state_summary"]
    assert text == result["presentation"]["summary"]
    if mode != "questionnaire":
        und = _v3_data(client.get(f"/api/v3/understandings/{result['understanding_ref']['understanding_id']}", headers=headers))
        assert text.startswith(und["case_summary"]["summary"])
        if mode == "document":
            assert text == und["case_summary"]["summary"]
    if mode != "document":
        assert "烦躁易怒倾向" in text
        assert "胁肋胀闷不适" in text
    assert "已根据你本次提供并确认的信息完成状态评估" not in text


@pytest.mark.parametrize("mode", ["document", "questionnaire", "combined"])
def test_full_text_edit_suppresses_removed_facts_only_in_active_revision(monkeypatch, db_session_factory, mode):
    headers, _, original = create_summary_assessment(monkeypatch, db_session_factory, mode)
    response = client.post(f"/api/v3/assessments/{original['assessment_id']}/confirmations", headers=headers, json={
        "expected_revision": 1, "expected_input_revision": original["input_revision"],
        "decision": "confirm_with_changes", "changes": [], "edited_summary_text": "近期仅有胁肋不适、胁肋胀闷不适。",
    })
    assert response.status_code == 201, response.text
    current = _v3_data(response)
    assert {f["claim_code"] for f in current["fact_evidence"]} == {"flank_discomfort"}
    assert current["state_summary"] == "近期仅有胁肋不适、胁肋胀闷不适。"
    with db_session_factory() as db:
        old = db.query(FactEvidenceRow).filter_by(assessment_id=original["assessment_id"], assessment_revision=1).all()
        assert {f.claim_code for f in old} == {"anger_tendency", "flank_discomfort"}
        assert len(old) == len(original["fact_evidence"])


@pytest.mark.parametrize("text,codes", [("近期仅有胁肋不适。", {"flank_discomfort"}), ("近期状态平稳。", set())])
def test_document_edit_can_continue_to_assessment_with_retained_or_empty_facts(monkeypatch, db_session_factory, text, codes):
    _, _, result = create_summary_assessment(monkeypatch, db_session_factory, "document", understanding_edit=text)
    assert result["state_summary"] == text
    assert {f["claim_code"] for f in result["fact_evidence"]} == codes


def test_full_text_edit_recomputes_derived_state_from_active_facts(monkeypatch, db_session_factory):
    headers, _, original = create_summary_assessment(monkeypatch, db_session_factory, "combined")
    response = client.post(
        f"/api/v3/assessments/{original['assessment_id']}/confirmations",
        headers=headers,
        json={
            "expected_revision": 1,
            "expected_input_revision": original["input_revision"],
            "decision": "confirm_with_changes",
            "changes": [],
            "edited_summary_text": "近期状态平稳，仅补充一些自己的感受。",
        },
    )
    assert response.status_code == 201, response.text
    current = _v3_data(response)
    assert current["fact_evidence"] == []
    assert current["organ_evidence_links"] == []
    assert current["conflicts"] == []
    assert current["evidence_coverage"] == 0
    assert current["source_diversity"] == 0
    assert current["organ_profile"]["status"] == "insufficient"


def test_full_text_edit_recomputes_derived_state_from_active_facts(monkeypatch, db_session_factory):
    headers, _, original = create_summary_assessment(monkeypatch, db_session_factory, "combined")
    response = client.post(
        f"/api/v3/assessments/{original['assessment_id']}/confirmations",
        headers=headers,
        json={
            "expected_revision": 1,
            "expected_input_revision": original["input_revision"],
            "decision": "confirm_with_changes",
            "changes": [],
            "edited_summary_text": "近期状态平稳，仅补充一些自己的感受。",
        },
    )
    assert response.status_code == 201, response.text
    current = _v3_data(response)
    assert current["fact_evidence"] == []
    assert current["organ_evidence_links"] == []
    assert current["conflicts"] == []
    assert current["evidence_coverage"] == 0
    assert current["source_diversity"] == 0
    assert current["organ_profile"]["status"] == "insufficient"
