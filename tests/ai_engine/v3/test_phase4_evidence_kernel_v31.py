"""Sprint 6 Phase 4 — EvidenceKernelV1 / SafeExplanationAtomV1 unit contract.

Engine-level (no database, no HTTP): the kernel is a deterministic projection of
already-authoritative inputs and can never be influenced by provider free text,
provider ordering or provider-declared support.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from backend.ai_engine.v3.diagnosis_provider import DiagnosisProvider
from backend.ai_engine.v3.grounding import (
    AUTHORITY_FIREWALL_VERSION,
    EVIDENCE_KERNEL_VERSION,
    GROUNDING_STATUS_BUILT,
    GROUNDING_STATUS_LEGACY_UNVERIFIED,
    KERNEL_PRESENTATION_KEY,
    KNOWLEDGE_CONTEXT_ATOM_TEXT,
    SAFE_EXPLANATION_ATOM_VERSION,
    authoritative_state_tendency,
    build_evidence_kernel,
    build_safe_explanation_atoms,
    canonical_checksum,
    grounding_status_of,
    presentation_with_kernel,
)
from backend.ai_engine.v3.v31_pipeline import execute_v31_ai_pipeline
from tests.ai_engine.v3.test_v31_pipeline import (
    _confirmed_state,
    _mapping,
    _rag_result,
    _rules,
    _snapshot,
)


class _Rag:
    def query(self, query):
        del query
        return _rag_result()


class _Backend:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    async def acomplete_json(self, system_prompt, user_prompt):
        del system_prompt, user_prompt
        self.calls += 1
        return self.payload


def _payload(*, display_name, support, reasoning, chunk_ids=("chunk_1",)):
    return {
        "status": "success",
        "candidate_tendencies": [
            {
                "syndrome_code": "syd_005",
                "display_name": display_name,
                "relative_support": support,
                "supporting_fact_ids": ["fact_1"],
                "contradicting_fact_ids": [],
                "knowledge_chunk_ids": list(chunk_ids),
                "reasoning_summary": reasoning,
            }
        ],
        "abstained": False,
        "abstain_reason": None,
    }


def _run_pipeline(payload):
    provider = DiagnosisProvider(
        backend=_Backend(payload),
        allowed_syndrome_codes={"syd_005"},
        allowed_fact_ids={"fact_1"},
        allowed_chunk_ids={"chunk_1"},
    )
    return asyncio.run(
        execute_v31_ai_pipeline(
            confirmed_user_state=_confirmed_state(),
            assessment_snapshot=_snapshot(),
            rag_store=_Rag(),
            diagnosis_provider=provider,
            tone_mapping=_mapping(),
            generation_parameter_rules=_rules(),
            user_goal={"primary_goal": "sleep"},
        )
    )


def _normalized(kernel):
    payload = json.loads(json.dumps(kernel.payload()))
    payload.pop("content_checksum", None)
    payload.pop("assessment_id", None)
    payload.get("rag", {}).pop("retrieval_id", None)
    payload.get("decision", {}).pop("decision_checksum", None)
    payload.get("decision", {}).pop("read_model_checksum", None)
    return payload


def test_kernel_version_identities_are_frozen():
    assert EVIDENCE_KERNEL_VERSION == "evidence_kernel_v1"
    assert SAFE_EXPLANATION_ATOM_VERSION == "safe_explanation_atom_v1"
    assert AUTHORITY_FIREWALL_VERSION == "authority_firewall_v1"


def test_kernel_is_deterministic_across_provider_free_text_and_order():
    first = _run_pipeline(
        _payload(
            display_name="alpha",
            support=0.1,
            reasoning="first phrasing",
        )
    )
    second = _run_pipeline(
        _payload(
            display_name="omega",
            support=0.99,
            reasoning="completely different and much stronger phrasing",
        )
    )

    assert first.evidence_kernel is not None
    assert second.evidence_kernel is not None
    assert _normalized(first.evidence_kernel) == _normalized(second.evidence_kernel)
    # Same authoritative inputs => a stable content checksum formula.
    payload = first.evidence_kernel.payload()
    checksum = payload.pop("content_checksum")
    assert checksum == canonical_checksum(payload)


def test_kernel_never_carries_provider_free_text_or_support():
    pipeline = _run_pipeline(
        _payload(display_name="alpha", support=0.42, reasoning="provider phrasing")
    )
    serialized = json.dumps(pipeline.evidence_kernel.payload(), ensure_ascii=False)

    assert "provider phrasing" not in serialized
    assert "alpha" not in serialized
    assert "relative_support" not in serialized
    assert "reasoning_summary" not in serialized
    assert "display_name" not in serialized


def test_kernel_builder_has_no_provider_input():
    import inspect

    parameters = set(inspect.signature(build_evidence_kernel).parameters)
    assert not any("provider" in name for name in parameters)
    assert not any("response" in name for name in parameters)
    assert not any("candidate" in name for name in parameters)


def test_kernel_records_the_current_run_and_current_facts():
    pipeline = _run_pipeline(
        _payload(display_name="alpha", support=0.8, reasoning="provider phrasing")
    )
    kernel = pipeline.evidence_kernel

    assert kernel.assessment_revision == 1
    assert [item.fact_evidence_id for item in kernel.confirmed_facts] == ["fact_1"]
    assert kernel.rag.hit_ids == ("chunk_1",)
    assert kernel.rag.status == "success"
    assert kernel.decision.regulation_mode == pipeline.read_model.regulation_mode
    assert kernel.generation.bpm == pipeline.generation_spec.bpm
    assert kernel.audit.knowledge_version == pipeline.rag_result.knowledge_version
    assert kernel.audit.provider_free_text_authoritative is False
    assert kernel.audit.semantic_entailment_verified is False
    assert kernel.grounding_status == GROUNDING_STATUS_BUILT


def test_safe_explanation_atoms_are_deterministic_and_structured():
    pipeline = _run_pipeline(
        _payload(display_name="alpha", support=0.8, reasoning="provider phrasing")
    )
    atoms = pipeline.evidence_kernel.explanation_atoms

    assert [atom.atom_type for atom in atoms] == [
        "state_context",
        "analysis_rationale",
        "generation_readiness",
        "knowledge_context",
    ]
    for atom in atoms:
        assert atom.display_text.strip()
        assert atom.display_text != "provider phrasing"
    knowledge = atoms[-1]
    assert knowledge.rag_refs == ("chunk_1",)
    assert knowledge.display_text == KNOWLEDGE_CONTEXT_ATOM_TEXT
    # No atom claims that the chunk proves a medical sentence.
    assert "证明" not in knowledge.display_text


def test_knowledge_atom_absent_without_current_hits():
    read_model = SimpleNamespace(
        schema_version="five_tone_analysis_read_model_v3.3",
        state_tendency="state",
        analysis_rationales=[SimpleNamespace(summary="rationale")],
        generation=SimpleNamespace(message="ready"),
        primary_tone=None,
    )
    atoms = build_safe_explanation_atoms(
        read_model=read_model,
        decision=None,
        fact_ids=["f1"],
        rag_hit_ids=(),
        knowledge_version=None,
    )
    assert [atom.atom_type for atom in atoms] == [
        "state_context",
        "analysis_rationale",
        "generation_readiness",
    ]
    assert all(not atom.rag_refs for atom in atoms)


def test_authoritative_state_tendency_uses_only_the_read_model_state_text():
    """Phase 4 blocking fix: the headline is state/tendency text, not a tone."""

    assert authoritative_state_tendency(SimpleNamespace(state_tendency="")) is None
    assert (
        authoritative_state_tendency(SimpleNamespace(state_tendency="   ")) is None
    )
    assert (
        authoritative_state_tendency(
            SimpleNamespace(
                state_tendency="整体状态倾向已根据确认信息整理。",
                primary_tone=SimpleNamespace(display_name="角调"),
            )
        )
        == "整体状态倾向已根据确认信息整理。"
    )
    # A read model without any state text falls back to the safe nullable
    # behaviour instead of borrowing the tone label.
    assert (
        authoritative_state_tendency(
            SimpleNamespace(primary_tone=SimpleNamespace(display_name="角调"))
        )
        is None
    )


def test_presentation_with_kernel_is_additive_and_marks_legacy_rows():
    presentation = {"title": "辨证分析", "primary_tendency": None, "basis_summaries": ["x"]}
    assert grounding_status_of(presentation) == GROUNDING_STATUS_LEGACY_UNVERIFIED

    pipeline = _run_pipeline(
        _payload(display_name="alpha", support=0.8, reasoning="provider phrasing")
    )
    merged = presentation_with_kernel(presentation, pipeline.evidence_kernel)

    assert merged["title"] == presentation["title"]
    assert merged["primary_tendency"] is None
    assert merged["basis_summaries"] == ["x"]
    assert KERNEL_PRESENTATION_KEY in merged
    assert grounding_status_of(merged) == GROUNDING_STATUS_BUILT
    # The original mapping is not mutated.
    assert KERNEL_PRESENTATION_KEY not in presentation


def test_presentation_without_kernel_is_unchanged():
    presentation = {"title": "辨证分析", "basis_summaries": ["x"]}
    assert presentation_with_kernel(presentation, None) == presentation
