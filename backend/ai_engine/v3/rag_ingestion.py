"""Validation gates for the Owner-approved V3.1 RAG corpus."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError

from backend.app.schemas.v3.diagnosis import IngestionManifest, KnowledgeChunk


class ProductionCorpusNotReady(RuntimeError):
    """The corpus cannot be used as a production medical index."""

    def __init__(self, error_code: str, safe_message: str) -> None:
        self.error_code = error_code
        self.safe_message = safe_message
        super().__init__(f"{error_code}: {safe_message}")


EMPTY_LABEL_SEMANTICS = "claim_codes_and_organ_codes_intentionally_empty_by_medical_review"
NORMALIZED_SCORE_CONVERSION = "normalized_similarity = 1 / (2 - cosine)"


def approved_text_checksum(text: str) -> str:
    """Hash of an approved chunk's text (Phase 3 live-integrity authority)."""

    return f"sha256:{sha256(str(text).encode('utf-8')).hexdigest()}"


def _content_checksum(payload: Mapping[str, object], field: str) -> str:
    """Return the stable checksum for one manifest or chunk payload.

    The checksum is calculated from the complete JSON payload except for its
    checksum field.  Sorting keys and using compact UTF-8 JSON makes the
    validation independent of file formatting while still detecting content
    changes.
    """

    canonical = {key: value for key, value in payload.items() if key != field}
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def validate_production_corpus(
    manifest: IngestionManifest | Mapping[str, object],
    chunks: Sequence[KnowledgeChunk | Mapping[str, object]],
    *,
    corpus_payload: Mapping[str, object] | None = None,
) -> IngestionManifest:
    """Validate an immutable manifest/chunk set before production ingestion."""

    raw_manifest = (
        manifest.model_dump(mode="json")
        if isinstance(manifest, IngestionManifest)
        else dict(manifest)
    )
    if raw_manifest.get("review_status") != "approved":
        raise ProductionCorpusNotReady(
            "CORPUS_NOT_PRODUCTION_APPROVED",
            "医学语料尚未获得生产放行。",
        )
    try:
        checked_manifest = IngestionManifest.model_validate(raw_manifest)
    except ValidationError as error:
        raise ProductionCorpusNotReady(
            "CORPUS_MANIFEST_INVALID",
            "医学语料清单格式无效。",
        ) from error

    if checked_manifest.manifest_checksum != _content_checksum(
        checked_manifest.model_dump(mode="json"), "manifest_checksum"
    ):
        raise ProductionCorpusNotReady(
            "CORPUS_MANIFEST_CHECKSUM_MISMATCH",
            "医学语料清单校验和不匹配。",
        )

    if (checked_manifest.source_cosine_threshold is None) != (
        checked_manifest.score_conversion is None
    ):
        raise ProductionCorpusNotReady(
            "CORPUS_SCORE_METADATA_INVALID",
            "医学语料清单的来源阈值与换算规则必须成对记录。",
        )
    if checked_manifest.source_cosine_threshold is not None:
        expected_runtime_score = 1.0 / (2.0 - checked_manifest.source_cosine_threshold)
        if (
            checked_manifest.retrieval_score_semantics != "normalized_similarity"
            or checked_manifest.score_conversion != NORMALIZED_SCORE_CONVERSION
            or abs(checked_manifest.minimum_score - expected_runtime_score) > 0.000001
        ):
            raise ProductionCorpusNotReady(
                "CORPUS_SCORE_METADATA_INVALID",
                "医学语料清单的来源阈值与运行时阈值换算不一致。",
            )
    if checked_manifest.corpus_checksum is not None:
        if corpus_payload is not None and checked_manifest.corpus_checksum != _content_checksum(
            corpus_payload, "content_checksum"
        ):
            raise ProductionCorpusNotReady(
                "CORPUS_CHECKSUM_MISMATCH",
                "医学语料包校验和不匹配。",
            )

    if (
        checked_manifest.embedding_model != "text-embedding-v4"
        or checked_manifest.embedding_version != "text-embedding-v4@1024"
    ):
        raise ProductionCorpusNotReady(
            "EMBEDDING_NOT_APPROVED",
            "生产医学语料必须使用已批准的 text-embedding-v4 1024 维 Embedding。",
        )
    if len(chunks) != checked_manifest.chunk_count:
        raise ProductionCorpusNotReady(
            "CORPUS_CHUNK_COUNT_MISMATCH",
            "医学语料块数量与清单不一致。",
        )

    validated_chunks: list[KnowledgeChunk] = []
    for raw_chunk in chunks:
        raw = (
            raw_chunk.model_dump(mode="json")
            if isinstance(raw_chunk, KnowledgeChunk)
            else dict(raw_chunk)
        )
        if raw.get("review_status") != "approved":
            raise ProductionCorpusNotReady(
                "CORPUS_CHUNK_NOT_APPROVED",
                "存在尚未批准的医学语料块。",
            )
        try:
            chunk = KnowledgeChunk.model_validate(raw)
        except ValidationError as error:
            raise ProductionCorpusNotReady(
                "CORPUS_CHUNK_INVALID",
                "医学语料块格式无效。",
            ) from error
        if chunk.content_checksum != _content_checksum(
            chunk.model_dump(mode="json"), "content_checksum"
        ):
            raise ProductionCorpusNotReady(
                "CORPUS_CHUNK_CHECKSUM_MISMATCH",
                "医学语料块校验和不匹配。",
            )
        if chunk.knowledge_version != checked_manifest.knowledge_version:
            raise ProductionCorpusNotReady(
                "CORPUS_VERSION_MISMATCH",
                "医学语料块版本与清单不一致。",
            )
        if (
            checked_manifest.medical_review_version is not None
            and chunk.medical_review_version != checked_manifest.medical_review_version
        ):
            raise ProductionCorpusNotReady(
                "CORPUS_MEDICAL_REVIEW_VERSION_MISMATCH",
                "医学语料块审核版本与清单不一致。",
            )
        validated_chunks.append(chunk)

    if checked_manifest.chunk_checksums is not None:
        expected_checksums = [
            {
                "chunk_id": chunk.chunk_id,
                "content_checksum": chunk.content_checksum,
            }
            for chunk in validated_chunks
        ]
        actual_checksums = [
            item.model_dump(mode="json") for item in checked_manifest.chunk_checksums
        ]
        if actual_checksums != expected_checksums:
            raise ProductionCorpusNotReady(
                "CORPUS_CHUNK_CHECKSUM_MANIFEST_MISMATCH",
                "医学语料清单未完整绑定语料块校验和。",
            )

    all_labels_empty = bool(validated_chunks) and all(
        not chunk.claim_codes and not chunk.organ_codes for chunk in validated_chunks
    )
    if all_labels_empty and checked_manifest.label_semantics != EMPTY_LABEL_SEMANTICS:
        raise ProductionCorpusNotReady(
            "CORPUS_EMPTY_LABEL_SEMANTICS_MISSING",
            "医学语料标签有意留空时，清单必须记录医学审核语义。",
        )
    if checked_manifest.label_semantics is not None and not all_labels_empty:
        raise ProductionCorpusNotReady(
            "CORPUS_LABEL_SEMANTICS_INVALID",
            "清单的空标签语义与语料块标签状态不一致。",
        )

    return checked_manifest


def load_production_corpus(
    manifest_path: str | Path,
    chunks_path: str | Path,
) -> tuple[IngestionManifest, list[KnowledgeChunk]]:
    """Load and validate owner-supplied manifest/chunks without fallback data."""

    try:
        manifest_payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        chunks_payload = json.loads(Path(chunks_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProductionCorpusNotReady(
            "CORPUS_FILES_INVALID",
            "医学语料文件无法读取或格式无效。",
        ) from error

    if isinstance(manifest_payload, Mapping) and isinstance(
        manifest_payload.get("manifest"), Mapping
    ):
        manifest_payload = manifest_payload["manifest"]
    if isinstance(manifest_payload, Mapping) and manifest_payload.get("candidate_status") == "PENDING_MEDICAL_CONTENT_REVIEW":
        raise ProductionCorpusNotReady(
            "CORPUS_NOT_PRODUCTION_APPROVED",
            "候选医学语料尚未获得生产放行。",
        )
    corpus_payload = chunks_payload if isinstance(chunks_payload, Mapping) else None
    if isinstance(chunks_payload, Mapping):
        chunks_payload = chunks_payload.get("chunks")
    if not isinstance(manifest_payload, Mapping) or not isinstance(chunks_payload, list):
        raise ProductionCorpusNotReady(
            "CORPUS_FILES_INVALID",
            "医学语料文件格式无效。",
        )
    try:
        manifest = IngestionManifest.model_validate(manifest_payload)
        chunks = [KnowledgeChunk.model_validate(item) for item in chunks_payload]
    except (TypeError, ValueError, ValidationError) as error:
        raise ProductionCorpusNotReady(
            "CORPUS_FILES_INVALID",
            "医学语料文件内容无效。",
        ) from error
    return validate_production_corpus(
        manifest,
        chunks,
        corpus_payload=corpus_payload,
    ), chunks


# --------------------------------------------------------------------------- #
# Sprint 6 Phase 3 — approved/versioned RAG query policy (R3-D3 / R3-D6)
# --------------------------------------------------------------------------- #

RAG_QUERY_POLICY_SCHEMA_ID = "rag_query_policy"
RAG_QUERY_POLICY_ASSET_VERSION = "rag-query-policy-v3.2-r1"
# Canonical checksum of knowledge/v3/rag-query-policy-v3.2-approved.json (same
# "configured approved release" convention as the dominance/music assets).
APPROVED_RAG_QUERY_POLICY_CHECKSUM = (
    "sha256:aabee0682d47b4c3f1ade3dd3531b8dd4ce98b1ee86d6c8f911b343c20d7b495"
)
DEFAULT_RAG_QUERY_POLICY_FILENAME = "rag-query-policy-v3.2-approved.json"
RAG_QUERY_POLICY_PATH_ENV = "V31_RAG_QUERY_POLICY_PATH"
RAG_QUERY_POLICY_CHECKSUM_ENV = "V31_RAG_QUERY_POLICY_CHECKSUM"
RAG_QUERY_POLICY_VERSION_ENV = "V31_RAG_QUERY_POLICY_VERSION"
# The approved query policy restates the frozen retrieval semantics. The organ
# display set is the same approved set the organ-mapping asset must expose.
APPROVED_POLICY_ORGAN_CODES = frozenset(
    {"liver", "heart", "spleen", "lung", "kidney"}
)


class RagQueryPolicyNotReady(RuntimeError):
    """The approved RAG query policy cannot be used as retrieval authority."""

    def __init__(self, error_code: str, safe_message: str) -> None:
        self.error_code = error_code
        self.safe_message = safe_message
        super().__init__(f"{error_code}: {safe_message}")


class RagQueryIntentTerm(BaseModel):
    intent: str
    terms: list[str]


class RagQueryReference(BaseModel):
    schema_id: str
    schema_version: str
    content_checksum: str


class RagQueryPolicy(BaseModel):
    """Approved, checksum-protected authority for RAG query construction."""

    schema_id: Literal["rag_query_policy"]
    schema_version: str
    asset_version: str
    review_status: Literal["approved"]
    query_builder_version: str
    top_k: int
    distance_metric: str
    retrieval_score_semantics: str
    source_cosine_threshold: float
    minimum_score: float
    score_conversion: str
    score_comparison_epsilon: float
    default_query_intent: str
    organ_display_names: dict[str, str]
    query_intent_terms: dict[str, RagQueryIntentTerm]
    claim_dictionary_reference: RagQueryReference
    content_checksum: str

    @property
    def builder_identity(self) -> str:
        """Persisted query-builder identity including the policy release."""

        return f"{self.query_builder_version}+{self.asset_version}"

    def intent_for(self, claim_code: str) -> tuple[str, tuple[str, ...]] | None:
        entry = self.query_intent_terms.get(claim_code)
        if entry is None:
            return None
        return entry.intent, tuple(entry.terms)


def _asset_root() -> Path:
    # backend/ai_engine/v3/rag_ingestion.py -> repository root
    return Path(__file__).resolve().parents[3] / "knowledge" / "v3"


_RAG_QUERY_POLICY_CACHE: dict[tuple[str, str, str], RagQueryPolicy] = {}


def load_rag_query_policy(
    path: str | Path | None = None,
    *,
    environment: Mapping[str, str] | None = None,
    expected_version: str | None = None,
    expected_checksum: str | None = None,
) -> RagQueryPolicy:
    """Load, verify and return the approved RAG query policy.

    Fails closed on a missing/unreadable asset, an unapproved release, a
    checksum or version mismatch, an inconsistent score pair and a stale claim
    dictionary reference. This is the single authority for ``top_k``, the query
    display mapping, the intent vocabulary and the frozen retrieval semantics.
    """

    values = environment if environment is not None else {}
    configured_path = (values.get(RAG_QUERY_POLICY_PATH_ENV) or "").strip()
    configured_checksum = (
        values.get(RAG_QUERY_POLICY_CHECKSUM_ENV) or ""
    ).strip() or (expected_checksum or APPROVED_RAG_QUERY_POLICY_CHECKSUM)
    configured_version = (
        values.get(RAG_QUERY_POLICY_VERSION_ENV) or ""
    ).strip() or (expected_version or RAG_QUERY_POLICY_ASSET_VERSION)

    if path is not None:
        policy_path = Path(path)
    elif configured_path:
        policy_path = Path(configured_path)
    else:
        policy_path = _asset_root() / DEFAULT_RAG_QUERY_POLICY_FILENAME

    # Only the default approved repository asset is cached: an explicit path or
    # an environment override must always be re-read and re-verified so tamper
    # detection can never be masked by a previous successful load.
    cache_key = (str(policy_path),)
    cacheable = path is None and not configured_path
    if cacheable:
        cached = _RAG_QUERY_POLICY_CACHE.get(cache_key)
        if cached is not None:
            return cached

    try:
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RagQueryPolicyNotReady(
            "RAG_QUERY_POLICY_NOT_READY",
            "RAG 查询策略资产无法读取或格式无效。",
        ) from error
    if not isinstance(payload, Mapping):
        raise RagQueryPolicyNotReady(
            "RAG_QUERY_POLICY_INVALID",
            "RAG 查询策略资产格式无效。",
        )
    if payload.get("review_status") != "approved":
        raise RagQueryPolicyNotReady(
            "RAG_QUERY_POLICY_NOT_APPROVED",
            "RAG 查询策略尚未获得批准。",
        )
    try:
        policy = RagQueryPolicy.model_validate(dict(payload))
    except (TypeError, ValueError, ValidationError) as error:
        raise RagQueryPolicyNotReady(
            "RAG_QUERY_POLICY_INVALID",
            "RAG 查询策略资产内容无效。",
        ) from error

    if policy.asset_version != configured_version:
        raise RagQueryPolicyNotReady(
            "RAG_QUERY_POLICY_VERSION_MISMATCH",
            "RAG 查询策略版本与已批准版本不一致。",
        )
    recomputed = _content_checksum(policy.model_dump(mode="json"), "content_checksum")
    if policy.content_checksum != recomputed or policy.content_checksum != configured_checksum:
        raise RagQueryPolicyNotReady(
            "RAG_QUERY_POLICY_CHECKSUM_MISMATCH",
            "RAG 查询策略校验和不匹配。",
        )
    if policy.distance_metric != "cosine":
        raise RagQueryPolicyNotReady(
            "RAG_QUERY_POLICY_INVALID",
            "RAG 查询策略距离度量未获批准。",
        )
    if (
        policy.score_conversion != NORMALIZED_SCORE_CONVERSION
        or policy.retrieval_score_semantics != "normalized_similarity"
    ):
        raise RagQueryPolicyNotReady(
            "RAG_QUERY_POLICY_INVALID",
            "RAG 查询策略分值与换算语义未获批准。",
        )
    expected_minimum = 1.0 / (2.0 - policy.source_cosine_threshold)
    if abs(policy.minimum_score - expected_minimum) > 0.000001:
        raise RagQueryPolicyNotReady(
            "RAG_QUERY_POLICY_INVALID",
            "RAG 查询策略阈值与换算规则不一致。",
        )
    if policy.score_comparison_epsilon < 0:
        raise RagQueryPolicyNotReady(
            "RAG_QUERY_POLICY_INVALID",
            "RAG 查询策略比较容差无效。",
        )
    if set(policy.organ_display_names) != APPROVED_POLICY_ORGAN_CODES:
        raise RagQueryPolicyNotReady(
            "RAG_QUERY_POLICY_REFERENCE_MISMATCH",
            "RAG 查询策略五脏展示映射未获批准。",
        )
    _verify_claim_dictionary_reference(policy.claim_dictionary_reference)
    if cacheable:
        _RAG_QUERY_POLICY_CACHE[cache_key] = policy
    return policy


def _verify_claim_dictionary_reference(reference: RagQueryReference) -> None:
    from backend.app.services.v3.knowledge_assets import load_claim_dictionary

    version, _entries = load_claim_dictionary()
    if reference.schema_id != "claim_dictionary_v3" or reference.schema_version != version:
        raise RagQueryPolicyNotReady(
            "RAG_QUERY_POLICY_REFERENCE_MISMATCH",
            "RAG 查询策略引用的声明字典版本不一致。",
        )
