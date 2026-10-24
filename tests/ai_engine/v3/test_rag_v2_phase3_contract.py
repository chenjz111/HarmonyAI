"""Sprint 6 Phase 3 — RAG V2 contract hardening (Option A).

Owner-frozen decisions exercised here:

* R3-D1 live chunk text integrity is verified at runtime;
* R3-D2 an unbuilt/partial index is a readiness failure, never ``RAG_EMPTY``;
* R3-D3 ``top_k`` comes from the approved/versioned query policy asset;
* R3-D4 the deterministic structured-derived query is unchanged;
* R3-D6 the threshold / epsilon semantics stay frozen;
* R3-D8 the Phase 1B boundary is preserved without touching its vocabulary.

Every test is provider-free: a fake Chroma client and a fake embedding are used
except in the dedicated real-Chroma persistence test, which uses a temporary
directory and a deterministic local embedding.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest

from backend.ai_engine.v3.diagnosis_pipeline import (
    build_diagnosis_query,
    execute_diagnosis_provider,
)
from backend.ai_engine.v3.rag_ingestion import (
    APPROVED_RAG_QUERY_POLICY_CHECKSUM,
    RAG_QUERY_POLICY_ASSET_VERSION,
    RagQueryPolicyNotReady,
    _content_checksum,
    approved_text_checksum,
    load_rag_query_policy,
    load_production_corpus,
)
from backend.ai_engine.v3.rag_store import RagStoreFailure, VersionedRagStore
from backend.app.schemas.v3.common import Degradation
from backend.app.schemas.v3.diagnosis import RagResult

from tests.ai_engine.v3.test_rag_store_v31 import (
    FakeClient,
    FakeEmbedding,
    ScenarioClient,
    _chunk,
    _manifest,
    _query,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
POLICY_PATH = REPO_ROOT / "knowledge" / "v3" / "rag-query-policy-v3.2-approved.json"
APPROVED_MANIFEST = (
    REPO_ROOT / "knowledge" / "v3" / "rag-ingestion-manifest-v3.1-approved.json"
)
APPROVED_CHUNKS = REPO_ROOT / "knowledge" / "v3" / "rag-corpus-chunks-v3.1-approved.json"


def _policy_payload() -> dict:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def _write_policy(tmp_path, payload: dict) -> Path:
    payload = dict(payload)
    payload["content_checksum"] = _content_checksum(payload, "content_checksum")
    path = tmp_path / "rag-query-policy.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path


def _written_checksum(path: Path) -> str:
    return json.loads(path.read_text(encoding="utf-8"))["content_checksum"]


def _bound_metadata(manifest) -> dict:
    """Collection metadata that satisfies the Phase 3 identity contract."""

    return {
        "knowledge_version": manifest.knowledge_version,
        "embedding_version": manifest.embedding_version,
        "manifest_checksum": manifest.manifest_checksum,
        "hnsw:space": "cosine",
    }


def _store(*, client=None, policy=None, chunks=None, manifest=None, embedding=None):
    return VersionedRagStore(
        persist_directory="unused",
        collection_name="harmony_v31",
        embedding_provider=embedding or FakeEmbedding(),
        client=client or FakeClient(),
        production=False,
        query_policy=policy,
    )


def _approved_store(*, distance=0.1):
    """A store bound to the real approved corpus semantics via a fake client."""

    store = _store(client=ScenarioClient(distance), chunks=[_chunk()])
    store.ingest(_manifest(), [_chunk()])
    return store


class _RecordingProvider:
    """Provider double that records every call and never runs for a failure."""

    provider_name = "fake"
    backend = None
    allowed_syndrome_codes = {"syndrome_1"}
    allowed_fact_ids: set = set()
    medical_rule_version = None

    def __init__(self, allowed_chunk_ids=("chunk_1",)):
        self.allowed_chunk_ids = set(allowed_chunk_ids)
        self.calls = 0
        self.kwargs = None

    async def acomplete_json(self, **kwargs):
        self.calls += 1
        self.kwargs = kwargs
        from backend.app.schemas.v3.diagnosis import (
            DiagnosisProviderResponse,
            ProviderCandidateTendency,
        )

        return DiagnosisProviderResponse(
            status="success",
            candidate_tendencies=[
                ProviderCandidateTendency(
                    syndrome_code="syndrome_1",
                    display_name="safe tendency",
                    relative_support=0.8,
                    supporting_fact_ids=[],
                    contradicting_fact_ids=[],
                    knowledge_chunk_ids=list(kwargs.get("rag_chunk_ids") or []),
                    reasoning_summary="x",
                )
            ],
            abstained=False,
            abstain_reason=None,
        )


def _run(coro):
    return asyncio.run(coro)


# --------------------------------------------------------------------------- #
# Policy asset identity (R3-D3 / R3-D6)
# --------------------------------------------------------------------------- #


def test_p3_policy_asset_is_approved_versioned_and_checksum_protected():
    policy = load_rag_query_policy()

    assert policy.review_status == "approved"
    assert policy.asset_version == RAG_QUERY_POLICY_ASSET_VERSION
    assert policy.content_checksum == APPROVED_RAG_QUERY_POLICY_CHECKSUM
    assert policy.builder_identity == (
        f"{policy.query_builder_version}+{policy.asset_version}"
    )
    # Frozen retrieval semantics (R3-D6).
    assert policy.top_k == 5
    assert policy.distance_metric == "cosine"
    assert policy.retrieval_score_semantics == "normalized_similarity"
    assert policy.source_cosine_threshold == 0.65
    assert policy.minimum_score == 0.740741
    assert policy.score_comparison_epsilon == 1e-6
    assert policy.score_conversion == "normalized_similarity = 1 / (2 - cosine)"
    # Query mapping authority lives in the asset, not in store code.
    assert set(policy.organ_display_names) == {
        "liver",
        "heart",
        "spleen",
        "lung",
        "kidney",
    }
    assert policy.intent_for("anger_tendency") == (
        "五志五脏对应关系和相关说明",
        ("怒",),
    )
    assert policy.default_query_intent == "状态关联和相关说明"
    # The referenced claim dictionary is the approved one.
    assert policy.claim_dictionary_reference.schema_id == "claim_dictionary_v3"


def test_p3_c_policy_checksum_tamper_fails_closed(tmp_path):
    payload = _policy_payload()
    payload["top_k"] = 9  # tampered, checksum left as the approved value
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(RagQueryPolicyNotReady, match="RAG_QUERY_POLICY_CHECKSUM_MISMATCH"):
        load_rag_query_policy(path)


def test_p3_c_policy_unapproved_release_fails_closed(tmp_path):
    payload = _policy_payload()
    payload["review_status"] = "pending"
    with pytest.raises(RagQueryPolicyNotReady, match="RAG_QUERY_POLICY_NOT_APPROVED"):
        load_rag_query_policy(_write_policy(tmp_path, payload))


def test_p3_c_policy_version_mismatch_fails_closed(tmp_path):
    payload = _policy_payload()
    payload["asset_version"] = "rag-query-policy-v9.9-r9"
    with pytest.raises(RagQueryPolicyNotReady, match="RAG_QUERY_POLICY_VERSION_MISMATCH"):
        load_rag_query_policy(_write_policy(tmp_path, payload))


def test_p3_c_policy_invalid_score_pair_fails_closed(tmp_path):
    payload = _policy_payload()
    payload["minimum_score"] = 0.5
    path = _write_policy(tmp_path, payload)
    with pytest.raises(RagQueryPolicyNotReady, match="RAG_QUERY_POLICY_INVALID"):
        load_rag_query_policy(path, expected_checksum=_written_checksum(path))


def test_p3_c_policy_organ_mapping_tamper_fails_closed(tmp_path):
    payload = _policy_payload()
    payload["organ_display_names"] = {"liver": "肝"}
    path = _write_policy(tmp_path, payload)
    with pytest.raises(
        RagQueryPolicyNotReady, match="RAG_QUERY_POLICY_REFERENCE_MISMATCH"
    ):
        load_rag_query_policy(path, expected_checksum=_written_checksum(path))


def test_p3_c_policy_claim_dictionary_reference_mismatch_fails_closed(tmp_path):
    payload = _policy_payload()
    payload["claim_dictionary_reference"] = {
        **payload["claim_dictionary_reference"],
        "schema_version": "9.9.9",
    }
    path = _write_policy(tmp_path, payload)
    with pytest.raises(
        RagQueryPolicyNotReady, match="RAG_QUERY_POLICY_REFERENCE_MISMATCH"
    ):
        load_rag_query_policy(path, expected_checksum=_written_checksum(path))


def test_p3_c_missing_policy_asset_fails_closed(tmp_path):
    with pytest.raises(RagQueryPolicyNotReady, match="RAG_QUERY_POLICY_NOT_READY"):
        load_rag_query_policy(tmp_path / "absent.json")


def test_p3_k_policy_manifest_semantics_drift_fails_closed_before_ingest():
    tampered = load_rag_query_policy().model_copy(update={"minimum_score": 0.5})
    store = _store(policy=tampered)

    with pytest.raises(RagStoreFailure, match="RAG_QUERY_POLICY_MISMATCH"):
        store.ingest(_manifest(), [_chunk()])


# --------------------------------------------------------------------------- #
# P3-A / P3-B — query authority (R3-D4)
# --------------------------------------------------------------------------- #


def _snapshot(**overrides):
    payload = {
        "knowledge_version": "medical_v3.1",
        "manifest_checksum": "sha256:manifest-v31",
        "organ_codes": ["heart"],
        "claim_codes": ["unrefreshing_sleep"],
        "supporting_fact_ids": ["fev_a"],
        "contradicting_fact_ids": [],
        "approved_organ_codes": ["liver", "heart", "spleen", "lung", "kidney"],
        "approved_claim_codes": ["unrefreshing_sleep", "anger_tendency"],
    }
    payload.update(overrides)
    return payload


def test_p3_a_presentation_narrative_never_changes_the_query():
    baseline = build_diagnosis_query(_snapshot())

    with_narrative = build_diagnosis_query(
        _snapshot(confirmed_state_text="完全不同的一段叙述文本")
    )
    with_presentation = build_diagnosis_query(
        _snapshot(presentation_summary="presentation only", state_summary="display")
    )

    assert with_narrative.query_id == baseline.query_id
    assert with_presentation.query_id == baseline.query_id
    assert with_narrative.model_dump() == baseline.model_dump()


def test_p3_a_store_query_text_is_narrative_independent():
    embedding = FakeEmbedding()
    store = _store(embedding=embedding, client=ScenarioClient(0.1))
    store.ingest(_manifest(), [_chunk()])
    query = _query()

    store.query(query, confirmed_state_text="叙述 A")
    first = embedding.texts[-1]
    store.query(query, confirmed_state_text="完全不同的叙述 B")
    second = embedding.texts[-1]

    head = "已批准资料中关于心与睡眠不解乏的状态关联和相关说明。"
    assert first.startswith(head)
    assert second.startswith(head)
    # Only the structured-derived state text differs; the query authority is
    # the deterministic structured template.
    assert first.split("\n")[0] == second.split("\n")[0]


def test_p3_b_structured_change_changes_the_query_deterministically():
    baseline = build_diagnosis_query(_snapshot())

    dropped_claim = build_diagnosis_query(_snapshot(claim_codes=[]))
    added_contradiction = build_diagnosis_query(
        _snapshot(contradicting_fact_ids=["fev_b"])
    )
    replaced_fact = build_diagnosis_query(_snapshot(supporting_fact_ids=["fev_z"]))

    assert dropped_claim.query_id != baseline.query_id
    assert added_contradiction.query_id != baseline.query_id
    assert replaced_fact.query_id != baseline.query_id
    # Determinism: identical structured state always yields the same query.
    assert build_diagnosis_query(_snapshot()).query_id == baseline.query_id


# --------------------------------------------------------------------------- #
# P3-D — top_k authority
# --------------------------------------------------------------------------- #


def test_p3_d_query_builder_never_hard_codes_top_k():
    source = (
        REPO_ROOT / "backend" / "ai_engine" / "v3" / "diagnosis_pipeline.py"
    ).read_text(encoding="utf-8")
    assert 'snapshot.get("top_k", 5)' not in source
    assert "load_rag_query_policy().top_k" in source

    service_source = (
        REPO_ROOT / "backend" / "app" / "services" / "v3" / "diagnosis_service.py"
    ).read_text(encoding="utf-8")
    assert '"top_k": 5' not in service_source
    assert 'int(query_policy.top_k)' in service_source


# --------------------------------------------------------------------------- #
# P3-E — frozen threshold / epsilon boundaries (R3-D6)
# --------------------------------------------------------------------------- #


def _score_to_distance(score: float) -> float:
    # score = 1 / (2 - (1 - distance)) = 1 / (1 + distance)
    return 1.0 / score - 1.0


def test_p3_e_threshold_boundaries_are_frozen_and_inclusive():
    policy = load_rag_query_policy()
    minimum = policy.minimum_score
    exact_distance = _score_to_distance(minimum)

    cases = {
        "above": (exact_distance - 1e-3, "success"),
        "exactly_at": (exact_distance, "success"),
        "epsilon_below": (exact_distance + 5e-7, "success"),
        "clearly_below": (exact_distance + 1e-3, "empty"),
    }
    for label, (distance, expected) in cases.items():
        store = _store(client=ScenarioClient(distance))
        store.ingest(_manifest(), [_chunk()])
        result = store.query(_query())
        assert result.status == expected, (label, distance, result.status)
        if expected == "success":
            assert len(result.hits) == 1
            assert result.hits[0].retrieval_score == pytest.approx(
                1.0 / (1.0 + distance)
            )
        else:
            assert result.hits == []


# --------------------------------------------------------------------------- #
# P3-F / P3-G / P3-H — legal no-match vs index-not-ready (R3-D2)
# --------------------------------------------------------------------------- #


def test_p3_f_healthy_populated_index_without_match_is_legal_rag_empty():
    store = _store(client=ScenarioClient(0.9))
    store.ingest(_manifest(), [_chunk()])

    result = store.query(_query())

    assert result.status == "empty"
    assert result.hits == []

    provider = _RecordingProvider()
    execution = _run(
        execute_diagnosis_provider(
            provider=provider,
            request={"assessment_id": "asmt_1", "revision": 1},
            facts=[],
            rag_result=result,
        )
    )

    assert execution.status == "abstained"
    assert execution.reason_code == "RAG_EMPTY"
    assert execution.attempts == 0
    assert provider.calls == 0


def test_p3_g_zero_count_index_is_a_readiness_failure_not_rag_empty():
    manifest = _manifest()

    class EmptyCollection:
        metadata = _bound_metadata(manifest)

        def count(self):
            return 0

        def get(self, ids=None, include=None):
            return {"ids": [], "metadatas": []}

        def query(self, **kwargs):
            raise AssertionError("an unbuilt index must not be queried")

    class EmptyClient:
        def get_or_create_collection(self, *, name, metadata, embedding_function):
            del name, metadata, embedding_function
            return EmptyCollection()

    store = _store(client=EmptyClient())
    # Bind the approved manifest without an ingest (the index was never built).
    store._manifest = manifest
    store._collection = EmptyCollection()
    store._approved_chunk_ids = frozenset({"chunk_001"})
    store._chunk_checksums = {"chunk_001": "sha256:chunk-001"}
    store._chunk_text_checksums = {
        "chunk_001": approved_text_checksum("approved explanation text")
    }

    with pytest.raises(RagStoreFailure, match="RAG_INDEX_COUNT_MISMATCH"):
        store.query(_query())


def test_p3_h_partial_index_loss_is_a_readiness_failure_not_rag_empty():
    manifest = _manifest()

    class TwoRowCollection:
        metadata = _bound_metadata(manifest)

        def count(self):
            return 2

        def get(self, ids=None, include=None):
            return {"ids": [], "metadatas": []}

    store = _store()
    store._manifest = manifest  # expects exactly 1 chunk
    store._collection = TwoRowCollection()
    store._approved_chunk_ids = frozenset({"chunk_001"})
    store._chunk_checksums = {"chunk_001": "sha256:chunk-001"}
    store._chunk_text_checksums = {}

    with pytest.raises(RagStoreFailure, match="RAG_INDEX_COUNT_MISMATCH"):
        store.query(_query())


def test_p3_g2_unbound_index_is_not_ready():
    store = _store()
    with pytest.raises(RagStoreFailure, match="RAG_NOT_READY"):
        store.query(_query())


# --------------------------------------------------------------------------- #
# P3-I — live content integrity (R3-D1)
# --------------------------------------------------------------------------- #


def test_p3_i_changed_live_chunk_text_fails_closed_in_the_store():
    client = ScenarioClient(0.1)
    store = _store(client=client)
    store.ingest(_manifest(), [_chunk()])

    collection = next(iter(client.collections.values()))
    row_id = next(iter(collection.rows))
    stored = collection.rows[row_id]
    collection.rows[row_id] = (
        stored[0],
        "tampered approved explanation text",
        stored[2],
        stored[3],
    )

    with pytest.raises(RagStoreFailure, match="RAG_CHUNK_CONTENT_CHECKSUM_MISMATCH"):
        store.query(_query())


def test_p3_i_changed_metadata_checksum_fails_closed_in_the_store():
    client = ScenarioClient(0.1)
    store = _store(client=client)
    store.ingest(_manifest(), [_chunk()])

    collection = next(iter(client.collections.values()))
    row_id = next(iter(collection.rows))
    stored = collection.rows[row_id]
    metadata = dict(stored[2])
    metadata["content_checksum"] = "sha256:tampered"
    collection.rows[row_id] = (stored[0], stored[1], metadata, stored[3])

    with pytest.raises(RagStoreFailure, match="RAG_CHUNK_METADATA_MISMATCH"):
        store.query(_query())


def _hit_result(text: str, chunk_id: str = "chunk_1") -> RagResult:
    from backend.app.schemas.v3.diagnosis import RagHit

    return RagResult(
        retrieval_id="rag_1",
        status="success",
        knowledge_version="medical_v3.1",
        embedding_version="text-embedding-v4@1024",
        retrieval_score_semantics="normalized_similarity",
        hits=[
            RagHit(
                chunk_id=chunk_id,
                source_id="source_1",
                source_title="approved source",
                section="section",
                retrieval_score=0.9,
                text=text,
                display_summary="approved summary",
                review_status="approved",
            )
        ],
        degradation=Degradation(active=False, reason_codes=[]),
    )


def test_p3_i_pipeline_verifies_the_approved_live_text_hash():
    provider = _RecordingProvider()
    execution = _run(
        execute_diagnosis_provider(
            provider=provider,
            request={"assessment_id": "asmt_1", "revision": 1},
            facts=[],
            rag_result=_hit_result("unapproved live text"),
            rag_text_checksums={"chunk_1": approved_text_checksum("approved text")},
        )
    )

    assert execution.status == "failed"
    assert execution.reason_code == "RAG_CHUNK_CONTENT_CHECKSUM_MISMATCH"
    assert provider.calls == 0


def test_p3_i_pipeline_requires_a_verifiable_hash_when_one_is_supplied():
    provider = _RecordingProvider()
    execution = _run(
        execute_diagnosis_provider(
            provider=provider,
            request={"assessment_id": "asmt_1", "revision": 1},
            facts=[],
            rag_result=_hit_result("approved text"),
            rag_text_checksums={"other_chunk": "sha256:x"},
        )
    )

    assert execution.status == "failed"
    assert execution.reason_code == "RAG_CHUNK_TEXT_UNVERIFIABLE"
    assert provider.calls == 0


def test_p3_i_verified_hit_reaches_the_provider():
    provider = _RecordingProvider()
    execution = _run(
        execute_diagnosis_provider(
            provider=provider,
            request={"assessment_id": "asmt_1", "revision": 1},
            facts=[],
            rag_result=_hit_result("approved text"),
            rag_text_checksums={"chunk_1": approved_text_checksum("approved text")},
        )
    )

    assert execution.status == "success"
    assert provider.calls == 1


class _PendingReviewClient(FakeClient):
    """Client whose stored row metadata claims a non-approved review status."""

    def get_or_create_collection(self, *, name, metadata, embedding_function):
        collection = super().get_or_create_collection(
            name=name, metadata=metadata, embedding_function=embedding_function
        )
        original_query = collection.query

        def query(**kwargs):
            raw = original_query(**kwargs)
            raw["metadatas"] = [
                [{**item, "review_status": "pending"} for item in row]
                for row in raw["metadatas"]
            ]
            return raw

        collection.query = query
        return collection


def test_p3_d1_store_never_returns_a_non_approved_row():
    store = _store(client=_PendingReviewClient())
    store.ingest(_manifest(), [_chunk()])

    result = store.query(_query())

    assert result.status == "empty"
    assert result.hits == []


def test_p3_d1_pipeline_rejects_a_non_approved_hit():
    from backend.app.schemas.v3.diagnosis import RagHit

    approved_hit = _hit_result("approved text").hits[0]
    unapproved_hit = RagHit.model_construct(
        **{
            **approved_hit.model_dump(),
            "review_status": "pending",
        }
    )
    result = _hit_result("approved text").model_copy(
        update={"hits": [unapproved_hit]}
    )

    provider = _RecordingProvider()
    execution = _run(
        execute_diagnosis_provider(
            provider=provider,
            request={"assessment_id": "asmt_1", "revision": 1},
            facts=[],
            rag_result=result,
        )
    )

    assert execution.status == "failed"
    assert execution.reason_code == "RAG_UNAPPROVED_CHUNK"
    assert provider.calls == 0


# --------------------------------------------------------------------------- #
# P3-J — absolute allow-list
# --------------------------------------------------------------------------- #


def test_p3_j_empty_allow_list_with_a_successful_hit_fails_closed():
    provider = _RecordingProvider(allowed_chunk_ids=())
    execution = _run(
        execute_diagnosis_provider(
            provider=provider,
            request={"assessment_id": "asmt_1", "revision": 1},
            facts=[],
            rag_result=_hit_result("approved text"),
        )
    )

    assert execution.status == "failed"
    assert execution.reason_code == "CHUNK_REFERENCE_INVALID"
    assert provider.calls == 0


def test_p3_j_approved_but_unlisted_hit_fails_closed():
    provider = _RecordingProvider(allowed_chunk_ids={"another_chunk"})
    execution = _run(
        execute_diagnosis_provider(
            provider=provider,
            request={"assessment_id": "asmt_1", "revision": 1},
            facts=[],
            rag_result=_hit_result("approved text"),
        )
    )

    assert execution.status == "failed"
    assert execution.reason_code == "CHUNK_REFERENCE_INVALID"
    assert provider.calls == 0


def test_p3_j_allow_list_check_is_unconditional_in_the_pipeline_source():
    source = (
        REPO_ROOT / "backend" / "ai_engine" / "v3" / "diagnosis_pipeline.py"
    ).read_text(encoding="utf-8")
    assert "if approved_chunk_ids and hit.chunk_id not in approved_chunk_ids" not in source
    assert "if hit.chunk_id not in approved_chunk_ids" in source


# --------------------------------------------------------------------------- #
# P3-K — manifest / version / metric / identity mismatches
# --------------------------------------------------------------------------- #


def test_p3_k_wrong_collection_identity_fails_before_results_are_trusted():
    store = _store(client=ScenarioClient(0.1))
    store.ingest(_manifest(), [_chunk()])
    store._collection.metadata["manifest_checksum"] = "sha256:other"

    with pytest.raises(RagStoreFailure, match="RAG_MANIFEST_MISMATCH"):
        store.query(_query())


def test_p3_k_wrong_collection_knowledge_version_fails_closed():
    store = _store(client=ScenarioClient(0.1))
    store.ingest(_manifest(), [_chunk()])
    store._collection.metadata["knowledge_version"] = "medical_v9"

    with pytest.raises(RagStoreFailure, match="RAG_KNOWLEDGE_VERSION_MISMATCH"):
        store.query(_query())


def test_p3_k_wrong_metric_fails_closed():
    from tests.ai_engine.v3.test_rag_store_v31 import WrongDistanceClient

    store = _store(client=WrongDistanceClient())
    store._manifest = _manifest()
    store._collection = SimpleNamespace(
        metadata={"hnsw:space": "l2"},
        count=lambda: 1,
    )
    with pytest.raises(RagStoreFailure, match="RAG_DISTANCE_METRIC_MISMATCH"):
        store.query(_query())


def test_p3_k_query_manifest_checksum_mismatch_fails_closed():
    store = _store(client=ScenarioClient(0.1))
    store.ingest(_manifest(), [_chunk()])

    with pytest.raises(RagStoreFailure, match="RAG_MANIFEST_MISMATCH"):
        store.query(_query().model_copy(update={"ingestion_manifest_checksum": "sha256:other"}))


def test_p3_k_query_knowledge_version_mismatch_fails_closed():
    store = _store(client=ScenarioClient(0.1))
    store.ingest(_manifest(), [_chunk()])

    with pytest.raises(RagStoreFailure, match="RAG_KNOWLEDGE_VERSION_MISMATCH"):
        store.query(_query().model_copy(update={"knowledge_version": "medical_v9"}))


def test_p3_k_unapproved_query_mapping_fails_closed_without_embedding():
    store = VersionedRagStore(
        persist_directory="unused",
        collection_name="harmony_v31",
        embedding_provider=FakeEmbedding(),
        client=ScenarioClient(0.1),
        production=False,
        claim_display_names={},
        organ_display_names={"heart": "心"},
    )
    store.ingest(_manifest(), [_chunk()])

    with pytest.raises(RagStoreFailure, match="RAG_QUERY_MAPPING_NOT_APPROVED"):
        store.query(_query())
    assert store.embedding_provider.input_types == ["document"]


# --------------------------------------------------------------------------- #
# P3-M — concrete store failures never become a music mode
# --------------------------------------------------------------------------- #


def _degraded_from_store(store) -> RagResult:
    from backend.ai_engine.v3.v31_pipeline import _query_rag

    return _query_rag(store, _query(), {"confirmed_state_text": "state"})


@pytest.mark.parametrize(
    "distance_or_error,expected",
    [
        ("not_ready", "RAG_NOT_READY"),
        ("count_mismatch", "RAG_INDEX_COUNT_MISMATCH"),
    ],
)
def test_p3_m_readiness_failures_never_reach_mode_resolution(distance_or_error, expected):
    if distance_or_error == "not_ready":
        store = _store()
    else:
        manifest = _manifest()
        store = _store()
        store._manifest = manifest
        store._collection = SimpleNamespace(
            metadata=_bound_metadata(manifest), count=lambda: 0
        )

    from backend.ai_engine.v3.rag_store import RagStoreFailure as _Failure

    with pytest.raises(_Failure, match=expected):
        store.query(_query())


def test_p3_m_store_failure_becomes_a_pipeline_failure_not_a_mode():
    class FailingStore:
        approved_chunk_ids = frozenset({"chunk_1"})
        chunk_checksums: dict = {}
        chunk_text_checksums: dict = {}

        def query(self, query, *, confirmed_state_text=None):
            raise RagStoreFailure("RAG_INDEX_UNAVAILABLE", "RAG 索引暂时不可用。")

    degraded = _degraded_from_store(FailingStore())
    assert degraded.status == "degraded"
    assert list(degraded.degradation.reason_codes) == ["RAG_INDEX_UNAVAILABLE"]

    provider = _RecordingProvider()
    execution = _run(
        execute_diagnosis_provider(
            provider=provider,
            request={"assessment_id": "asmt_1", "revision": 1},
            facts=[],
            rag_result=degraded,
        )
    )
    assert execution.status == "failed"
    assert execution.reason_code == "RAG_INDEX_UNAVAILABLE"
    assert provider.calls == 0

    from backend.app.services.v3.organ_dominance_service import (
        classify_abstain_reason,
    )

    # Only a genuine no-match is a legal abstain; the technical code is not.
    assert classify_abstain_reason("RAG_EMPTY") == "legal"
    assert classify_abstain_reason("RAG_INDEX_UNAVAILABLE") == "non_mode"
    assert classify_abstain_reason("RAG_CHUNK_CONTENT_CHECKSUM_MISMATCH") == "unclassified"


def test_p3_m_invalid_store_result_never_becomes_a_mode():
    class BadResultStore:
        approved_chunk_ids = frozenset({"chunk_1"})
        chunk_checksums: dict = {}
        chunk_text_checksums: dict = {}

        def query(self, query, *, confirmed_state_text=None):
            return {"status": "success"}

    with pytest.raises(Exception, match="RAG_INVALID_RESULT"):
        _degraded_from_store(BadResultStore())


# --------------------------------------------------------------------------- #
# P3-L — real Chroma persistence (temporary directory, no network)
# --------------------------------------------------------------------------- #


class _DeterministicEmbedding:
    """Constant 1024-dimension vector: cosine distance 0 for every pair."""

    dimension = 1024

    def embed(self, text, *, input_type):
        del text, input_type
        return [0.5] * self.dimension


def test_p3_l_real_chroma_index_persists_reopens_and_verifies(tmp_path):
    chromadb = pytest.importorskip("chromadb")

    manifest, chunks = load_production_corpus(APPROVED_MANIFEST, APPROVED_CHUNKS)
    persist_directory = tmp_path / "chroma-v31-phase3"

    store = VersionedRagStore(
        persist_directory=str(persist_directory),
        collection_name="harmony_v31",
        embedding_provider=_DeterministicEmbedding(),
        production=True,
    )
    collection_name = store.ingest(manifest, chunks)

    assert collection_name.startswith("harmony_v31_medical_v3.1-approved.1_")
    assert store.collection_count == manifest.chunk_count == 13
    assert set(store.approved_chunk_ids) == {chunk.chunk_id for chunk in chunks}

    query = build_diagnosis_query(
        {
            "knowledge_version": manifest.knowledge_version,
            "manifest_checksum": manifest.manifest_checksum,
            "organ_codes": ["liver"],
            "claim_codes": ["anger_tendency"],
            "supporting_fact_ids": ["fev_a"],
            "contradicting_fact_ids": [],
            "approved_organ_codes": ["liver", "heart", "spleen", "lung", "kidney"],
            "approved_claim_codes": ["anger_tendency", "sleep_disturbance"],
        }
    )
    result = store.query(query)

    assert result.status == "success"
    assert 1 <= len(result.hits) <= manifest.chunk_count
    for hit in result.hits:
        assert hit.chunk_id in store.approved_chunk_ids
        assert store.chunk_text_checksums[hit.chunk_id] == approved_text_checksum(
            hit.text
        )

    # Reopen the same persistent directory: identity, count and integrity hold.
    reopened = VersionedRagStore(
        persist_directory=str(persist_directory),
        collection_name="harmony_v31",
        embedding_provider=_DeterministicEmbedding(),
        production=True,
    )
    assert reopened.ingest(manifest, chunks) == collection_name
    assert reopened.collection_count == manifest.chunk_count
    reopened_result = reopened.query(query)
    assert reopened_result.status == "success"
    assert [hit.chunk_id for hit in reopened_result.hits] == [
        hit.chunk_id for hit in result.hits
    ]

    # The temporary index may be discarded; nothing outside tmp_path was touched.
    del chromadb


# --------------------------------------------------------------------------- #
# B1 — exact approved index population (same-count substitution)
# --------------------------------------------------------------------------- #

TWO_CHUNK_IDS = ("chunk_001", "chunk_002")


def _two_chunk_store(*, distance=0.1):
    store = _store(client=ScenarioClient(distance))
    store.ingest(_manifest(chunk_count=2), [_chunk("chunk_001"), _chunk("chunk_002")])
    return store


def _rows(store):
    return store._collection.rows


def test_b1_s1_exact_approved_set_proceeds():
    store = _two_chunk_store()

    result = store.query(_query())

    assert result.status == "success"
    assert set(store._approved_chunk_ids) == set(TWO_CHUNK_IDS)


def test_b1_s2_missing_approved_id_fails_closed():
    store = _two_chunk_store()
    del _rows(store)["chunk_002"]

    with pytest.raises(RagStoreFailure) as error:
        store.query(_query())
    assert error.value.error_code in {
        "RAG_INDEX_COUNT_MISMATCH",
        "RAG_INDEX_ID_SET_MISMATCH",
    }


def test_b1_s3_extra_rogue_id_fails_closed():
    store = _two_chunk_store()
    rows = _rows(store)
    rows["rogue_chunk"] = (
        "rogue_chunk",
        "rogue text",
        dict(next(iter(rows.values()))[2]),
        [0.1] * 1024,
    )

    with pytest.raises(RagStoreFailure) as error:
        store.query(_query())
    assert error.value.error_code in {
        "RAG_INDEX_COUNT_MISMATCH",
        "RAG_INDEX_ID_SET_MISMATCH",
    }


def test_b1_s4_same_count_substitution_fails_closed():
    """Delete one approved id and add one rogue id: the count is unchanged."""

    store = _two_chunk_store()
    rows = _rows(store)
    metadata = dict(next(iter(rows.values()))[2])
    del rows["chunk_002"]
    rows["rogue_chunk"] = ("rogue_chunk", "rogue text", metadata, [0.1] * 1024)

    assert store._collection.count() == 2  # count check alone cannot see this

    with pytest.raises(RagStoreFailure, match="RAG_INDEX_ID_SET_MISMATCH"):
        store.query(_query())


def test_b1_s4b_same_count_swap_on_a_larger_set_fails_closed():
    store = _store(client=ScenarioClient(0.1))
    ids = ["chunk_001", "chunk_002", "chunk_003"]
    store.ingest(_manifest(chunk_count=3), [_chunk(item) for item in ids])
    rows = _rows(store)
    metadata = dict(rows["chunk_003"][2])
    del rows["chunk_001"]
    rows["rogue_chunk"] = ("rogue_chunk", "rogue text", metadata, [0.1] * 1024)

    assert store._collection.count() == 3

    with pytest.raises(RagStoreFailure, match="RAG_INDEX_ID_SET_MISMATCH"):
        store.query(_query())


def test_b1_s5_exact_index_without_match_is_still_legal_rag_empty():
    store = _two_chunk_store(distance=0.9)

    result = store.query(_query())

    assert result.status == "empty"
    provider = _RecordingProvider()
    execution = _run(
        execute_diagnosis_provider(
            provider=provider,
            request={"assessment_id": "asmt_1", "revision": 1},
            facts=[],
            rag_result=result,
        )
    )
    assert execution.status == "abstained"
    assert execution.reason_code == "RAG_EMPTY"
    assert provider.calls == 0


def test_b1_s6_same_count_substitution_on_real_chroma_fails_closed(tmp_path):
    """B1-S6: the substitution probe on a temporary real Chroma index."""

    pytest.importorskip("chromadb")
    manifest, chunks = load_production_corpus(APPROVED_MANIFEST, APPROVED_CHUNKS)
    store = VersionedRagStore(
        persist_directory=str(tmp_path / "chroma-b1"),
        collection_name="harmony_v31",
        embedding_provider=_DeterministicEmbedding(),
        production=True,
    )
    store.ingest(manifest, chunks)
    query = build_diagnosis_query(
        {
            "knowledge_version": manifest.knowledge_version,
            "manifest_checksum": manifest.manifest_checksum,
            "organ_codes": ["liver"],
            "claim_codes": ["anger_tendency"],
            "supporting_fact_ids": ["fev_a"],
            "contradicting_fact_ids": [],
            "approved_organ_codes": ["liver", "heart", "spleen", "lung", "kidney"],
            "approved_claim_codes": ["anger_tendency"],
        }
    )
    assert store.query(query).status == "success"

    # Same-count substitution: remove one approved chunk, add one rogue chunk.
    collection = store._collection
    removed = sorted(store.approved_chunk_ids)[0]
    collection.delete(ids=[removed])
    collection.add(
        ids=["rogue_chunk_999"],
        documents=["rogue injected text"],
        metadatas=[
            {
                "source_id": "rogue",
                "source_title": "rogue",
                "section": "rogue",
                "display_summary": "rogue",
                "review_status": "approved",
                "knowledge_version": manifest.knowledge_version,
                "content_checksum": approved_text_checksum("rogue injected text"),
            }
        ],
        embeddings=[[0.5] * 1024],
    )
    assert int(collection.count()) == manifest.chunk_count == 13

    with pytest.raises(RagStoreFailure, match="RAG_INDEX_ID_SET_MISMATCH"):
        store.query(query)


def test_b1_id_set_check_fails_closed_for_missing_and_extra_ids_on_real_chroma(
    tmp_path,
):
    pytest.importorskip("chromadb")
    manifest, chunks = load_production_corpus(APPROVED_MANIFEST, APPROVED_CHUNKS)
    store = VersionedRagStore(
        persist_directory=str(tmp_path / "chroma-b1-shapes"),
        collection_name="harmony_v31",
        embedding_provider=_DeterministicEmbedding(),
        production=True,
    )
    store.ingest(manifest, chunks)
    query = build_diagnosis_query(
        {
            "knowledge_version": manifest.knowledge_version,
            "manifest_checksum": manifest.manifest_checksum,
            "organ_codes": ["liver"],
            "claim_codes": ["anger_tendency"],
            "supporting_fact_ids": ["fev_a"],
            "contradicting_fact_ids": [],
            "approved_organ_codes": ["liver", "heart", "spleen", "lung", "kidney"],
            "approved_claim_codes": ["anger_tendency"],
        }
    )
    collection = store._collection
    removed = sorted(store.approved_chunk_ids)[0]
    collection.delete(ids=[removed])

    with pytest.raises(RagStoreFailure, match="RAG_INDEX_COUNT_MISMATCH"):
        store.query(query)


# --------------------------------------------------------------------------- #
# B2 — persisted checksum semantics restored
# --------------------------------------------------------------------------- #


def test_b2_s1_approved_payload_checksum_differs_from_the_text_hash():
    manifest, chunks = load_production_corpus(APPROVED_MANIFEST, APPROVED_CHUNKS)
    sample = chunks[0]

    assert sample.content_checksum != approved_text_checksum(sample.text)
    assert sample.content_checksum == dict(
        (chunk.chunk_id, chunk.content_checksum) for chunk in chunks
    )[sample.chunk_id]


def test_b2_s3_audit_writer_uses_the_manifest_payload_checksum_and_historical_text_hash():
    """The persisted pair keeps its pre-Phase-3 semantics."""

    from backend.ai_engine.v3.diagnosis_pipeline import _rag_context
    from backend.app.services.v3.diagnosis_service import _request_hash

    hit = _hit_result("approved text").hits[0]
    payload_checksum = "sha256:manifest-payload-checksum"

    # Provider context keeps the manifest payload checksum.
    context = _rag_context(_hit_result("approved text"), {"chunk_1": payload_checksum})
    assert context[0]["content_checksum"] == payload_checksum

    # The historical persistence forms are unchanged by Phase 3.
    assert _request_hash({"text": hit.text}).startswith("sha256:")
    assert _request_hash({"text": hit.text}) != approved_text_checksum(hit.text)
    assert _request_hash(
        {"chunk_id": hit.chunk_id, "text": hit.text}
    ) != approved_text_checksum(hit.text)


def test_b2_s4_persisted_audit_columns_are_unchanged():
    """No migration and no schema change: the pair keeps its documented form."""

    from backend.app.models.v3.diagnosis import RagRetrievalHit, RagRetrievalRun

    hit_columns = set(RagRetrievalHit.__table__.columns.keys())
    run_columns = set(RagRetrievalRun.__table__.columns.keys())
    assert "chunk_content_checksum" in hit_columns
    assert "text_ciphertext" in hit_columns
    assert "query_builder_version" in run_columns
    # Live-text integrity is not stored in a new column.
    assert not any("text_hash" in name for name in hit_columns)
    assert not any("integrity" in name for name in hit_columns)
