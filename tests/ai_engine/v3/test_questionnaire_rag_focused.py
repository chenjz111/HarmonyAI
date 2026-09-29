from __future__ import annotations

import pytest

from backend.ai_engine.v3.diagnosis_pipeline import (
    build_focused_diagnosis_queries,
    merge_focused_rag_results,
)
from backend.app.schemas.v3.diagnosis import RagHit, RagResult
from backend.ai_engine.v3.v31_pipeline import _query_focused_rag, _query_focused_rag_with_provenance
from backend.app.schemas.v3.common import Degradation


def _snapshot(claim_codes, *, removed=()):
    facts = [
        {"fact_evidence_id": f"fact_{code}", "claim_code": code, "direction": "supporting"}
        for code in claim_codes
    ]
    for code in removed:
        claim = str(code).removeprefix("fact_")
        facts.append({"fact_evidence_id": str(code), "claim_code": claim, "direction": "contradicting"})
    return {
        "knowledge_version": "medical_v3.1-approved.1",
        "manifest_checksum": "sha256:manifest",
        "top_k": 5,
        "approved_organ_codes": ["liver", "heart", "spleen", "lung", "kidney"],
        "approved_claim_codes": list(claim_codes),
        "claim_codes": list(claim_codes),
        "supporting_fact_ids": [f"fact_{code}" for code in claim_codes],
        "contradicting_fact_ids": list(removed),
        "facts": facts,
    }


def test_focused_queries_use_only_eligible_confirmed_claims_and_preserve_dual_boundary_mapping():
    queries = build_focused_diagnosis_queries(
        _snapshot(["flank_discomfort", "exertional_breathlessness", "nocturia"])
    )
    assert [(group, query.organ_codes, query.claim_codes) for group, query in queries] == [
        ("focus_lung", ["lung"], ["exertional_breathlessness"]),
        ("focus_kidney", ["kidney"], ["exertional_breathlessness"]),
    ]


def test_focused_queries_exclude_removed_claims_and_unsupported_only_is_empty():
    assert build_focused_diagnosis_queries(_snapshot(["flank_discomfort", "nocturia"])) == []
    assert build_focused_diagnosis_queries(
        _snapshot(["anger_tendency", "eye_discomfort"], removed=["fact_anger_tendency"])
    ) == [("focus_liver", build_focused_diagnosis_queries(_snapshot(["eye_discomfort"]))[0][1])]


def _result(hits):
    return RagResult(
        retrieval_id="r",
        status="success" if hits else "empty",
        knowledge_version="medical_v3.1-approved.1",
        embedding_version="text-embedding-v4@1024",
        retrieval_score_semantics="normalized_similarity",
        hits=hits,
        degradation={"active": False, "reason_codes": []},
    )


def _status_result(status, reasons=()):
    return RagResult(
        retrieval_id="r",
        status=status,
        knowledge_version="medical_v3.1-approved.1",
        embedding_version="text-embedding-v4@1024",
        retrieval_score_semantics="normalized_similarity",
        hits=[],
        degradation=Degradation(active=status == "degraded", reason_codes=list(reasons)),
    )


def _hit(chunk_id, score):
    return RagHit(
        chunk_id=chunk_id,
        source_id="src",
        source_title="title",
        section="section",
        retrieval_score=score,
        text="approved",
        display_summary="approved",
        review_status="approved",
    )


def test_focused_merge_is_highest_score_then_stable_group_order():
    merged = merge_focused_rag_results(
        [("focus_lung", _result([_hit("shared", 0.76), _hit("lung", 0.8)])),
         ("focus_kidney", _result([_hit("shared", 0.81), _hit("kidney", 0.79)]))]
    )
    assert [hit.chunk_id for hit in merged.hits] == ["shared", "lung", "kidney"]
    assert [hit.retrieval_score for hit in merged.hits] == [0.81, 0.8, 0.79]


def test_focused_merge_preserves_child_failure_and_degradation_status():
    merged = merge_focused_rag_results(
        [("focus_lung", _result([_hit("lung", 0.8)])),
         ("focus_kidney", _status_result("failed", ["RAG_INDEX_UNAVAILABLE"]))]
    )
    assert merged.status == "failed"
    assert merged.hits == []
    assert "RAG_INDEX_UNAVAILABLE" in merged.degradation.reason_codes

    degraded = merge_focused_rag_results(
        [("focus_lung", _result([_hit("lung", 0.8)])),
         ("focus_kidney", _status_result("degraded", ["RAG_INDEX_UNAVAILABLE"]))]
    )
    assert degraded.status == "degraded"
    assert [hit.chunk_id for hit in degraded.hits] == ["lung"]


def test_focused_runtime_issues_one_query_per_active_group_without_combined_summary():
    calls = []

    class Store:
        def query(self, query):
            calls.append(query)
            return _result([_hit(query.organ_codes[0], 0.8)])

    snapshot = _snapshot(["exertional_breathlessness"])
    from backend.ai_engine.v3.diagnosis_pipeline import build_focused_diagnosis_queries

    focused = build_focused_diagnosis_queries(snapshot)
    result = _query_focused_rag(Store(), focused, {**snapshot, "confirmed_state_text": "十项跨域状态"})
    assert result.status == "success"
    assert [(q.organ_codes, q.claim_codes) for q in calls] == [
        (["lung"], ["exertional_breathlessness"]),
        (["kidney"], ["exertional_breathlessness"]),
    ]


def test_unsupported_only_runtime_makes_zero_store_calls_and_mixed_keeps_supported_group():
    calls = []

    class Store:
        def query(self, query):
            calls.append(query)
            return _result([_hit(query.organ_codes[0], 0.8)])

    from backend.ai_engine.v3.diagnosis_pipeline import build_focused_diagnosis_queries

    unsupported = build_focused_diagnosis_queries(
        _snapshot(["flank_discomfort", "postmeal_heaviness", "nocturia"])
    )
    assert _query_focused_rag(Store(), unsupported, _snapshot([])).status == "empty"
    assert calls == []
    mixed = build_focused_diagnosis_queries(
        _snapshot(["flank_discomfort", "eye_discomfort"])
    )
    assert [(group, query.claim_codes) for group, query in mixed] == [
        ("focus_liver", ["eye_discomfort"])
    ]


def test_focused_runtime_returns_ordered_query_and_hit_provenance():
    class Store:
        def query(self, query):
            return _result([_hit("shared", 0.8)])

    from backend.ai_engine.v3.diagnosis_pipeline import build_focused_diagnosis_queries

    focused = build_focused_diagnosis_queries(_snapshot(["exertional_breathlessness"]))
    result, provenance = _query_focused_rag_with_provenance(Store(), focused, _snapshot([]))
    assert result.status == "success"
    assert provenance == {"shared": ("focus_lung", "focus_kidney")}
    assert [group for group, _query in focused] == ["focus_lung", "focus_kidney"]


def test_provenance_facts_cannot_reactivate_removed_current_claims():
    snapshot = _snapshot(["anger_tendency"])
    snapshot["claim_codes"] = []
    assert build_focused_diagnosis_queries(snapshot) == []


def test_missing_current_fact_records_do_not_fall_back_to_claim_labels():
    snapshot = _snapshot(["anger_tendency"])
    snapshot["facts"] = []
    assert build_focused_diagnosis_queries(snapshot) == []


def test_focused_builder_rejects_top_k_drift():
    snapshot = _snapshot(["anger_tendency"])
    snapshot["top_k"] = 6
    with pytest.raises(ValueError, match="POLICY"):
        build_focused_diagnosis_queries(snapshot)


def test_merge_rejects_cross_version_results():
    other = _result([_hit("other", 0.81)]).model_copy(update={"knowledge_version": "wrong"})
    with pytest.raises(ValueError, match="IDENTITY"):
        merge_focused_rag_results([("focus_lung", _result([_hit("lung", 0.8)])), ("focus_kidney", other)])
