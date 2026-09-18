"""Three source modes compose meaningful summaries and preserve structured authority.

Phase 2 (Option B): the editable narrative is presentation only. Structured
evidence identity plus ``confirmation_status`` is the evidence authority, so a
narrative edit never adds, removes, confirms, rejects or re-authorizes a fact.
"""
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
def test_narrative_edit_keeps_every_structured_row_in_the_active_revision(
    monkeypatch, db_session_factory, mode
):
    """Phase 2: a narrative edit is presentation only — no row is dropped."""

    headers, _, original = create_summary_assessment(monkeypatch, db_session_factory, mode)
    narrative = "近期仅有胁肋不适、胁肋胀闷不适。"
    response = client.post(f"/api/v3/assessments/{original['assessment_id']}/confirmations", headers=headers, json={
        "expected_revision": 1, "expected_input_revision": original["input_revision"],
        "decision": "confirm_with_changes", "changes": [], "edited_summary_text": narrative,
    })
    assert response.status_code == 201, response.text
    current = _v3_data(response)
    assert current["presentation"]["summary"] == narrative
    assert current["state_summary"] != narrative
    assert current["state_summary"].startswith("已确认的近期状态：")
    assert {
        f["fact_evidence_id"] for f in current["fact_evidence"]
    } == {f["fact_evidence_id"] for f in original["fact_evidence"]}
    assert {f["claim_code"] for f in current["fact_evidence"]} == {
        f["claim_code"] for f in original["fact_evidence"]
    }
    assert all(
        f["confirmation_status"] == "confirmed" for f in current["fact_evidence"]
    )
    with db_session_factory() as db:
        old = db.query(FactEvidenceRow).filter_by(assessment_id=original["assessment_id"], assessment_revision=1).all()
        assert {f.claim_code for f in old} == {f["claim_code"] for f in original["fact_evidence"]}
        assert len(old) == len(original["fact_evidence"])


@pytest.mark.parametrize("text", ["近期仅有胁肋不适。", "近期状态平稳。"])
def test_document_narrative_edit_never_selects_evidence(monkeypatch, db_session_factory, text):
    """Phase 2 (D3): text alone cannot adopt evidence, so nothing is confirmed."""

    _, _, result = create_summary_assessment(
        monkeypatch, db_session_factory, "document", understanding_edit=text
    )
    assert result["presentation"]["summary"] == text
    # The understanding revision keeps every structured fact, but a narrative
    # edit never promotes one to ``confirmed``; adoption is explicit.
    assert result["fact_evidence"] == []


def test_plain_confirmation_recomputes_derived_state_from_confirmed_evidence(
    monkeypatch, db_session_factory
):
    headers, _, original = create_summary_assessment(monkeypatch, db_session_factory, "combined")
    response = client.post(
        f"/api/v3/assessments/{original['assessment_id']}/confirmations",
        headers=headers,
        json={
            "expected_revision": 1,
            "expected_input_revision": original["input_revision"],
            "decision": "confirm",
            "changes": [],
        },
    )
    assert response.status_code == 200, response.text
    current = _v3_data(response)
    assert current["revision"] == 1
    assert current["status"] == "confirmed"
    assert all(
        f["confirmation_status"] == "confirmed" for f in current["fact_evidence"]
    )
    assert {f["claim_code"] for f in current["fact_evidence"]} == {
        f["claim_code"] for f in original["fact_evidence"]
    }
    # Phase 2 (D4): the authoritative state text is the deterministic projection
    # of the confirmed structured evidence, never the narrative.
    assert current["state_summary"].startswith("已确认的近期状态：")
