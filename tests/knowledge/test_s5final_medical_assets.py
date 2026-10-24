# -*- coding: utf-8 -*-
"""S5-FINAL Issue #108 medical closeout assets — automated tests
Coverage (per Owner review of PR #114):
1) four JSON assets parse
2) canonical checksums consistent
3) relevance verdicts & reason codes legal
4) only VALID may enter downstream
5) UserGoal codes match questionnaire-v3.0.1 exactly
6) UserGoal is not Medical/Fact/Organ Evidence
7) RAG corpus holds explanation knowledge only; deterministic rules not vectorized; no fake chunks
8) five-tone expression has no diagnosis/treatment-promise/exaggeration wording
9) questionnaire-v3.0.1 untouched (checksum equals frozen authority)
"""
import json
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KV = ROOT / "knowledge" / "v3"
Q_FROZEN_SHA = "69a01d0753908e3e48e41ea947219818436f24eb4e97aeca260f4b4ca4951031"

ASSETS = [
    "document-relevance-rules-v3.1.json",
    "usergoal-vocabulary-v3.1.json",
    "five-tone-safe-expression-rules-v3.1.json",
    "rag-corpus-manifest-v3.1.json",
]
RELEVANCE_VERDICTS = {"VALID", "INVALID", "IRRELEVANT", "INSUFFICIENT"}


def _canon(d):
    return json.dumps(d, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _load(name):
    with open(KV / name, encoding="utf-8") as fh:
        return json.load(fh)


def _leaf_strings(o, out, in_forbidden=False):
    if isinstance(o, dict):
        for k, v in o.items():
            _leaf_strings(v, out, in_forbidden or k == "forbidden")
    elif isinstance(o, list):
        for x in o:
            _leaf_strings(x, out, in_forbidden)
    elif isinstance(o, str):
        out.append((o, in_forbidden))


def test_01_json_parseable():
    for a in ASSETS:
        assert isinstance(_load(a), dict), a


def test_02_canonical_checksums_consistent():
    for a in ASSETS:
        d = _load(a)
        embedded = d.pop("content_checksum", None)
        h = hashlib.sha256(_canon(d).encode("utf-8")).hexdigest()
        assert embedded == "sha256:" + h, a


def test_03_relevance_verdicts_and_reason_codes_legal():
    dr = _load("document-relevance-rules-v3.1.json")
    whitelist = dr["reason_code_whitelist"]
    assert whitelist
    codes = []
    for w in whitelist:
        assert w["verdict"] in RELEVANCE_VERDICTS, w
        assert w["code"] and w["meaning"], w
        assert w["reason"] and w["reason"].strip(), w  # freeze §3: reason non-empty
        codes.append(w["code"])
    assert len(codes) == len(set(codes)), "duplicate reason codes"
    for v in RELEVANCE_VERDICTS:
        assert any(w["verdict"] == v for w in whitelist), v


def test_04_only_valid_enters_downstream():
    dr = _load("document-relevance-rules-v3.1.json")
    gate = dr["downstream_gate"]
    assert set(gate.keys()) == {"may_enter_summary", "may_form_evidence", "may_enter_agent2"}
    for flag, allowed in gate.items():
        assert allowed == ["VALID"], flag


def test_04b_insufficient_uses_frozen_exception_flow():
    dr = _load("document-relevance-rules-v3.1.json")
    insufficient = next(v for v in dr["verdicts"] if v["verdict"] == "INSUFFICIENT")

    assert insufficient["action"] == "block_to_exception_page"
    assert "共用异常页" in insufficient["evidence_usage"]
    assert "重新选择资料" in insufficient["evidence_usage"]
    assert "no-document" in insufficient["evidence_usage"]

    decision = next(row for row in dr["decision_table"] if row["then"] == "INSUFFICIENT")
    assert "共用异常页" in decision["note"]
    assert "PENDING_CONTRACT" not in _canon(dr)
    assert "分流由合同决策" not in _canon(dr)


def test_05_usergoal_codes_match_questionnaire():
    ug = _load("usergoal-vocabulary-v3.1.json")
    q = _load("questionnaire-v3.0.1.json")
    ug_codes = {c["code"] for c in ug["approved_codes"]}
    q_codes = {o["code"] for o in q["user_goal"]["options"]}
    assert ug_codes == q_codes, (ug_codes ^ q_codes)


def test_06_usergoal_not_evidence():
    ug = _load("usergoal-vocabulary-v3.1.json")
    assert ug["evidence_role"] == "preference"
    assert ug["source_validity_signal"] is False
    assert set(ug["not_evidence"]) == {"MedicalEvidence", "FactEvidence", "OrganEvidence"}


def test_07_rag_corpus_explanation_only_no_chunks():
    cp = _load("rag-corpus-manifest-v3.1.json")
    assert cp["sources"], "no sources"
    for s in cp["sources"]:
        assert s.get("corpus_category") == "explanation_knowledge", s
        assert "解释" in s.get("rag_role", ""), s
        assert s.get("reviewer") and s.get("content_hash") and s.get("source_reference"), s
    assert cp.get("rag_boundary", {}).get("not_vectorized_rule_assets"), "rule-asset exclusion list must exist"
    assert "chunks" not in cp and "corpus_text" not in cs_serialized(cp), "fake chunks forbidden"
    st = cp["completion_status"]
    assert st["medical_source_review"] == "COMPLETED"
    assert st["actual_corpus_chunks"].startswith("NOT_DONE")
    assert st["embedding_ingestion"].startswith("PENDING")
    assert st["production_rag"] == "NOT_APPROVED_PENDING"


def cs_serialized(o):
    return _canon(o)


NEGATION = ("禁止", "不得", "不构成", "不形成", "不能", "不是", "不属于", "不表达",
            "不视为", "不含", "非", "无", "不建议", "免责", "仅供参考", "不提供",
            "不承担", "不作为", "不伪装", "除", "未", "仅", "只允许", "只能")
BANNED = ("治愈", "疗效", "治疗有效", "可治疗", "根治", "彻底治愈", "确诊",
          "你患有", "你的证型是", "保证康复", "包治")


def test_08_five_tone_no_diagnosis_promise_exaggeration():
    ft = _load("five-tone-safe-expression-rules-v3.1.json")
    leaves = []
    _leaf_strings(ft, leaves)
    hits = []
    for text, in_forbidden in leaves:
        if in_forbidden:
            continue
        if any(neg in text for neg in NEGATION):
            continue
        for b in BANNED:
            if b in text:
                hits.append((b, text[:80]))
    assert not hits, hits


def test_09_questionnaire_untouched():
    q = _load("questionnaire-v3.0.1.json")
    embedded = q.get("content_checksum", "")
    assert embedded == "sha256:" + Q_FROZEN_SHA
    d = dict(q)
    d.pop("content_checksum", None)
    h = hashlib.sha256(_canon(d).encode("utf-8")).hexdigest()
    assert h == Q_FROZEN_SHA
