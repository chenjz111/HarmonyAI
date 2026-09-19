"""Sprint 6 Phase 3 — RAG query-policy authority through the diagnosis service.

P3-D: ``top_k`` and the query-builder identity are authoritative in the
approved/versioned RAG query policy asset, never a hard-coded product literal.
"""

from __future__ import annotations

from types import SimpleNamespace

from backend.ai_engine.v3.rag_ingestion import (
    load_production_corpus,
    load_rag_query_policy,
)
from backend.app.models.v3.assessment import (
    AssessmentRevisionV3,
    AssessmentV3,
)
from backend.app.services.v3.diagnosis_service import _build_v31_assessment_snapshot

from tests.api.v3.test_diagnosis_dominance_routing import _organ_profile
from tests.api.v3.test_diagnosis_v3 import (
    _guest_headers,
    _seed_confirmed_assessment,
    _setup_flow_session,
)

import pytest


APPROVED_MANIFEST = (
    "knowledge/v3/rag-ingestion-manifest-v3.1-approved.json"
)
APPROVED_CHUNKS = "knowledge/v3/rag-corpus-chunks-v3.1-approved.json"


@pytest.fixture
def seeded_snapshot_inputs(db_session_factory):
    manifest, _chunks = load_production_corpus(APPROVED_MANIFEST, APPROVED_CHUNKS)
    headers = _guest_headers()
    db = db_session_factory()
    try:
        _session_id, user_pk, session_row = _setup_flow_session(db, headers)
        assessment_id = _seed_confirmed_assessment(
            db,
            user_pk=user_pk,
            session_row=session_row,
            organ_profile_json=_organ_profile({"liver": 6.0, "spleen": 5.0}),
            assessment_input_revision=session_row.input_revision,
            revision_input_revision=session_row.input_revision,
        )
        assessment = db.get(AssessmentV3, assessment_id)
        revision = (
            db.query(AssessmentRevisionV3)
            .filter_by(assessment_id=assessment_id, revision=1)
            .one()
        )
        yield db, assessment, revision, manifest
    finally:
        db.close()


def _deps(manifest, *, policy=None, store_policy=None):
    store = SimpleNamespace(manifest=manifest)
    if store_policy is not None:
        store.query_policy = store_policy
    deps = {
        "rag_store": store,
        "diagnosis_provider": SimpleNamespace(allowed_chunk_ids=set()),
        "medical_rule_version": "medical-rules-v3.1-r1",
        "allowed_syndrome_codes": {"syndrome_1"},
    }
    if policy is not None:
        deps["rag_query_policy"] = policy
    return SimpleNamespace(**deps)


def test_p3_d_runtime_top_k_and_builder_identity_follow_the_policy(
    seeded_snapshot_inputs,
):
    db, assessment, revision, manifest = seeded_snapshot_inputs
    approved_policy = load_rag_query_policy()
    custom_policy = approved_policy.model_copy(update={"top_k": 3})

    def snapshot(deps):
        return _build_v31_assessment_snapshot(
            db,
            request=SimpleNamespace(diagnosis_id="diag_topk"),
            assessment=assessment,
            assessment_revision=revision,
            deps=deps,
        )

    with_custom = snapshot(_deps(manifest, policy=custom_policy))
    with_store_policy = snapshot(_deps(manifest, store_policy=custom_policy))
    without_policy = snapshot(_deps(manifest))

    assert with_custom["top_k"] == 3
    assert with_store_policy["top_k"] == 3
    assert with_custom["query_builder_version"] == custom_policy.builder_identity
    assert with_store_policy["query_builder_version"] == custom_policy.builder_identity

    # With no injected policy the approved repository asset is the authority,
    # which is the frozen top_k = 5 — never a hard-coded literal.
    assert without_policy["top_k"] == approved_policy.top_k == 5
    assert without_policy["query_builder_version"] == approved_policy.builder_identity


def test_p3_d_approved_policy_is_the_only_top_k_authority_in_source():
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[3]
    service_source = (
        repo_root / "backend" / "app" / "services" / "v3" / "diagnosis_service.py"
    ).read_text(encoding="utf-8")
    pipeline_source = (
        repo_root / "backend" / "ai_engine" / "v3" / "diagnosis_pipeline.py"
    ).read_text(encoding="utf-8")

    assert '"top_k": 5' not in service_source
    assert "query_policy.top_k" in service_source
    assert 'snapshot.get("top_k", 5)' not in pipeline_source
    assert "load_rag_query_policy().top_k" in pipeline_source


def test_p3_i_persisted_rag_audit_is_truthful_and_policy_aware(
    db_session_factory, monkeypatch
):
    """The persisted audit keeps its documented hash domains (Phase 3, B2).

    ``chunk_content_checksum`` stays the approved manifest/corpus *payload*
    checksum — the persistence contract requires it to match the manifest — and
    ``text_ciphertext`` keeps the historical request-hash form. Phase 3 must not
    silently redefine either column, or pre-Phase-3 rows stop being comparable.
    Live-text integrity is verified at retrieval and at the provider boundary,
    not by rewriting these columns.
    """

    from backend.app.models.v3.diagnosis import RagRetrievalHit, RagRetrievalRun
    from backend.app.services.v3.diagnosis_service import _request_hash
    from backend.ai_engine.v3.diagnosis_pipeline import _rag_context
    from backend.ai_engine.v3.rag_ingestion import approved_text_checksum
    from tests.ai_engine.v3.test_v31_pipeline import _rag_result
    from tests.api.v3 import test_diagnosis_dominance_routing as routing

    # The approved store binds every chunk id to its manifest/corpus payload
    # checksum; inject that same contract into the shared fake chain.
    approved_payload_checksum = "sha256:" + "0f" * 32
    original_dependencies = routing._pipeline_dependencies

    def _dependencies_with_checksums(calls, **kwargs):
        dependencies = original_dependencies(calls, **kwargs)
        dependencies.rag_store.chunk_checksums = {
            "chunk_1": approved_payload_checksum
        }
        return dependencies

    monkeypatch.setattr(
        routing, "_pipeline_dependencies", _dependencies_with_checksums
    )

    _headers, response = routing._run_diagnosis(
        db_session_factory,
        monkeypatch,
        organ_support={"liver": 6.0, "spleen": 5.0},
    )
    assert response.status_code == 201, response.text

    db = db_session_factory()
    try:
        run = db.query(RagRetrievalRun).one()
        hits = db.query(RagRetrievalHit).filter_by(rag_run_id=run.rag_run_id).all()
    finally:
        db.close()

    approved_policy = load_rag_query_policy()
    assert run.query_builder_version == approved_policy.builder_identity
    assert run.top_k == approved_policy.top_k == 5
    assert run.distance_metric == approved_policy.distance_metric
    # The audit restates the bound manifest's minimum score; the approved store
    # enforces policy == manifest at ingest (see the policy-drift test), so a
    # real run can only ever persist the frozen 0.740741.
    assert run.minimum_score is not None

    hit = _rag_result().hits[0]
    assert [row.chunk_id for row in hits] == [hit.chunk_id]

    # The provider-facing RAG context, the persisted audit row and the approved
    # store all carry the one manifest payload checksum.
    context = _rag_context(_rag_result(), {"chunk_1": approved_payload_checksum})
    assert [item["content_checksum"] for item in context] == [
        approved_payload_checksum
    ]

    row = hits[0]
    assert row.chunk_content_checksum == approved_payload_checksum
    # ... while text_ciphertext keeps the historical request-hash form.
    assert row.text_ciphertext == _request_hash({"text": hit.text})

    # Regression guard for Phase 3 (B2): the two columns are distinct hash
    # domains, and chunk_content_checksum is never sha256(text).
    assert row.chunk_content_checksum != row.text_ciphertext
    assert row.chunk_content_checksum != approved_text_checksum(hit.text)
    assert row.text_ciphertext != approved_text_checksum(hit.text)
    assert row.chunk_content_checksum == context[0]["content_checksum"]
