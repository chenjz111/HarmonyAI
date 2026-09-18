"""Anonymous OCR summaries and immutable full-text confirmation authority."""
from datetime import datetime, timezone

from backend.app.schemas.v3.understanding import UnderstandingSource
from backend.app.services.v3 import understanding_service as service
from tests.api.v3.test_understanding_ai_extraction import (
    _mock_chain, _setup_guest, _seed_document, _user_pk, _post,
    _document_source, _v3_data, _confirm, client,
)


def test_document_summary_prioritizes_clinical_sections_across_ordered_documents():
    texts = [
        "示例医院\n门诊病历\n姓名：匿名甲\n联系电话：13800000000\n门诊号：123456789\n"
        + "示例医院宣传语\n" * 30
        + "主诉：反复头痛三日。\n现病史：夜间加重，无发热。\n四诊：舌淡，脉细。\n"
        + "诊断：记录为紧张性头痛。\n医师签名：匿名乙\n印章：示例医院",
        "示例检验中心\n检查结果：血红蛋白偏低。\n处理建议：一周后复查。",
    ]
    resolved = [service._ResolvedSource(
        UnderstandingSource(source_id=f"src_{i}", source_type="document",
                            processing_status="ready", text_ref=f"doc_{i}",
                            captured_at=datetime.now(timezone.utc)),
        "ready", text=text, document_id=f"doc_{i}",
    ) for i, text in enumerate(texts)]
    summary = service._build_case_summary(resolved, 1)
    assert summary["source_document_ids"] == ["doc_0", "doc_1"]
    for clinical in ["反复头痛三日", "夜间加重，无发热", "舌淡，脉细", "记录为紧张性头痛", "血红蛋白偏低", "一周后复查"]:
        assert clinical in summary["summary"]
    for excluded in ["示例医院", "匿名甲", "13800000000", "123456789", "匿名乙", "印章", "门诊病历", "示例检验中心"]:
        assert excluded not in summary["summary"]
    assert "肝" not in summary["summary"]


def test_full_text_edit_projects_facts_without_provider_and_retains_provenance(monkeypatch, db_session_factory):
    monkeypatch.setattr(service, "build_provider_chain", lambda: _mock_chain())
    headers, session_id = _setup_guest()
    with db_session_factory() as db:
        doc = _seed_document(db, user_pk=_user_pk(db, headers), session_id=session_id,
                             ocr_text="主诉：睡眠后仍感疲惫。")
    original = _v3_data(_post(headers, session_id, [_document_source(doc)]))
    def forbidden_provider():
        raise AssertionError("Full-text confirmation must not construct a provider")
    monkeypatch.setattr(service, "build_provider_chain", forbidden_provider)
    response = _confirm(headers, original["understanding_id"], decision="confirm_with_changes",
                        edited_summary_text="近期状态平稳。", reprocess_requested=True)
    assert response.status_code == 201, response.text
    latest = _v3_data(client.get(f"/api/v3/understandings/{original['understanding_id']}", headers=headers))
    previous = _v3_data(client.get(f"/api/v3/understandings/{original['understanding_id']}?revision=1", headers=headers))
    # Phase 2: the narrative is presentation only, so every structured fact is
    # copied with its prior status instead of being filtered by the text.
    assert [f["fact_id"] for f in latest["normalized_facts"]] == [
        f["fact_id"] for f in original["normalized_facts"]
    ]
    assert latest["case_summary"]["summary"] == "近期状态平稳。"
    assert previous == original


def test_full_text_edit_keeps_canonical_fact_and_source_reference(monkeypatch, db_session_factory):
    monkeypatch.setattr(service, "build_provider_chain", lambda: _mock_chain())
    headers, session_id = _setup_guest()
    with db_session_factory() as db:
        doc = _seed_document(db, user_pk=_user_pk(db, headers), session_id=session_id,
                             ocr_text="睡眠后仍感疲惫。")
    original = _v3_data(_post(headers, session_id, [_document_source(doc)]))
    monkeypatch.setattr(service, "build_provider_chain", lambda: None)
    response = _confirm(headers, original["understanding_id"], decision="confirm_with_changes",
                        edited_summary_text="近期睡眠后仍感疲惫，正在休息。", reprocess_requested=True)
    assert response.status_code == 201, response.text
    latest = _v3_data(client.get(f"/api/v3/understandings/{original['understanding_id']}", headers=headers))
    assert latest["normalized_facts"][0]["fact_id"] == original["normalized_facts"][0]["fact_id"]
    assert latest["normalized_facts"][0]["source_refs"] == original["normalized_facts"][0]["source_refs"]
    # Phase 2 (D3): text alone never promotes a fact to ``confirmed``.
    assert (
        latest["normalized_facts"][0]["confirmation_status"]
        == original["normalized_facts"][0]["confirmation_status"]
        == "unconfirmed"
    )



def test_fact_summary_is_source_grounded_and_excludes_care_instructions():
    """Only approved display names survive; no OCR wording, diagnosis or advice."""

    from backend.app.services.v3.document_summary import summarize_facts

    facts = [
        {"display_name": "睡眠恢复不足", "negated": False},
        {"display_name": "睡眠恢复不足", "negated": False},          # duplicate
        {"display_name": "腰膝酸软", "negated": False},
        {"display_name": "发热", "negated": True},                   # explicitly absent
        {"display_name": "中医诊断：肝郁气滞", "negated": False},      # forbidden term
        {"display_name": "处理意见", "negated": False},               # forbidden term
        {"display_name": "服用医嘱用药", "negated": False},            # forbidden term
        {},                                                          # malformed
        "not-a-dict",
    ]

    summary = summarize_facts(facts)

    assert summary == "资料中记录的近期状态：睡眠恢复不足、腰膝酸软。"
    for forbidden in ("诊断", "处理意见", "医嘱", "肝郁气滞", "发热"):
        assert forbidden not in summary
    # nothing to summarise -> callers keep the OCR fallback
    assert summarize_facts([]) == ""
    assert summarize_facts(None) == ""
    assert summarize_facts([{"display_name": "   "}]) == ""
    assert summarize_facts([{"display_name": "发热", "negated": True}]) == ""
