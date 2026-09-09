"""Release gates for the PR #114-bound V3.1 candidate corpus.

The candidate package is deliberately a source-scope package, not a
production ``KnowledgeChunk`` package.  This module verifies that no text or
metadata was added while converting the reviewed source registry into the
candidate handoff.  Production promotion remains an explicit Owner action.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path


class CorpusReleaseFailure(RuntimeError):
    """A candidate package failed an explicit release-boundary check."""

    def __init__(self, error_code: str, safe_message: str) -> None:
        self.error_code = error_code
        self.safe_message = safe_message
        super().__init__(f"{error_code}: {safe_message}")


@dataclass(frozen=True)
class CandidateCorpusPackage:
    """Validated candidate manifest and source-scoped chunk payloads."""

    manifest: Mapping[str, object]
    chunks: Sequence[Mapping[str, object]]
    source_registry_checksum: str


def _checksum(payload: Mapping[str, object], field: str = "content_checksum") -> str:
    canonical = {key: value for key, value in payload.items() if key != field}
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def _require_equal(actual: object, expected: object, error_code: str, message: str) -> None:
    if actual != expected:
        raise CorpusReleaseFailure(error_code, message)


def validate_candidate_against_source_registry(
    candidate: Mapping[str, object],
    source_registry: Mapping[str, object],
) -> CandidateCorpusPackage:
    """Validate candidate chunks byte-for-byte against PR #114 registry scope."""

    declared_registry_checksum = source_registry.get("content_checksum")
    _require_equal(
        declared_registry_checksum,
        _checksum(source_registry),
        "CORPUS_REGISTRY_CHECKSUM_MISMATCH",
        "PR #114 来源登记校验和不匹配。",
    )
    _require_equal(
        candidate.get("content_checksum"),
        _checksum(candidate),
        "CORPUS_CANDIDATE_CHECKSUM_MISMATCH",
        "候选语料包校验和不匹配。",
    )
    _require_equal(
        candidate.get("candidate_status"),
        "PENDING_MEDICAL_CONTENT_REVIEW",
        "CORPUS_CANDIDATE_STATUS_INVALID",
        "候选语料尚未处于可审查状态。",
    )
    _require_equal(
        candidate.get("source_registry_checksum"),
        declared_registry_checksum,
        "CORPUS_REGISTRY_CHECKSUM_MISMATCH",
        "候选语料引用的来源登记版本不一致。",
    )

    sources = source_registry.get("sources")
    chunks = candidate.get("chunks")
    if not isinstance(sources, list) or not isinstance(chunks, list):
        raise CorpusReleaseFailure(
            "CORPUS_CANDIDATE_FORMAT_INVALID",
            "候选语料包结构无效。",
        )
    _require_equal(
        candidate.get("chunk_count"),
        len(chunks),
        "CORPUS_CHUNK_COUNT_MISMATCH",
        "候选语料块数量不一致。",
    )
    _require_equal(
        len(sources),
        len(chunks),
        "CORPUS_CHUNK_COUNT_MISMATCH",
        "候选语料块没有覆盖全部来源登记。",
    )

    validated_chunks: list[Mapping[str, object]] = []
    seen_source_ids: set[str] = set()
    for source, chunk in zip(sources, chunks, strict=True):
        if not isinstance(source, Mapping) or not isinstance(chunk, Mapping):
            raise CorpusReleaseFailure(
                "CORPUS_CANDIDATE_FORMAT_INVALID",
                "候选语料块结构无效。",
            )
        source_id = source.get("source_id")
        chunk_source_id = chunk.get("source_id")
        if chunk_source_id != source_id or chunk_source_id in seen_source_ids:
            raise CorpusReleaseFailure(
                "CORPUS_SOURCE_ID_MISMATCH",
                "候选语料块与来源登记绑定不一致。",
            )
        seen_source_ids.add(str(chunk_source_id))

        _require_equal(
            chunk.get("source_content_hash"),
            source.get("content_hash"),
            "CORPUS_SOURCE_HASH_MISMATCH",
            "候选语料块引用的来源内容校验和不一致。",
        )
        source_fields = {
            "source_title": "title",
            "source_reference": "source_reference",
        }
        for field, source_field in source_fields.items():
            _require_equal(
                chunk.get(field),
                source.get(source_field),
                "CORPUS_SOURCE_SCOPE_MISMATCH",
                "候选语料块的来源元数据超出来源登记范围。",
            )
        for field in ("text", "display_summary"):
            _require_equal(
                chunk.get(field),
                source.get("use"),
                "CORPUS_SOURCE_SCOPE_MISMATCH",
                "候选语料块文本必须与来源登记 use 字段完全一致。",
            )
        _require_equal(
            chunk.get("claim_codes"),
            [],
            "CORPUS_MEDICAL_TRANSFORMATION_FORBIDDEN",
            "候选语料包不得添加医学 claim 标签。",
        )
        _require_equal(
            chunk.get("organ_codes"),
            [],
            "CORPUS_MEDICAL_TRANSFORMATION_FORBIDDEN",
            "候选语料包不得添加脏腑标签。",
        )
        for field in ("review_status", "source_registry_review_status", "source_registry_reviewed_at", "source_registry_reviewer"):
            expected = "pending_medical_review" if field == "review_status" else source.get(
                {"source_registry_review_status": "review_status", "source_registry_reviewed_at": "reviewed_at", "source_registry_reviewer": "reviewer"}[field]
            )
            _require_equal(
                chunk.get(field),
                expected,
                "CORPUS_SOURCE_SCOPE_MISMATCH",
                "候选语料块的审核元数据与来源登记不一致。",
            )
        _require_equal(
            chunk.get("content_checksum"),
            _checksum(chunk),
            "CORPUS_CHUNK_CHECKSUM_MISMATCH",
            "候选语料块校验和不匹配。",
        )
        validated_chunks.append(dict(chunk))

    return CandidateCorpusPackage(
        manifest={},
        chunks=tuple(validated_chunks),
        source_registry_checksum=str(declared_registry_checksum),
    )


def validate_candidate_manifest(
    manifest: Mapping[str, object],
    package: CandidateCorpusPackage,
    candidate: Mapping[str, object],
) -> None:
    """Validate the candidate ingestion metadata without promoting it."""

    _require_equal(
        manifest.get("content_checksum"),
        _checksum(manifest),
        "CORPUS_MANIFEST_CHECKSUM_MISMATCH",
        "候选 ingestion manifest 校验和不匹配。",
    )
    for field, expected in (
        ("candidate_status", "PENDING_MEDICAL_CONTENT_REVIEW"),
        ("source_registry_checksum", package.source_registry_checksum),
        ("candidate_corpus_checksum", candidate.get("content_checksum")),
        ("knowledge_version", candidate.get("knowledge_version")),
        ("embedding_model", "text-embedding-v4"),
        ("embedding_dimension", 1024),
        ("embedding_version", "text-embedding-v4@1024"),
        ("distance_metric", "cosine"),
        ("index_status", "NOT_BUILT_OWNER_PENDING"),
        ("chunk_count", len(package.chunks)),
    ):
        _require_equal(
            manifest.get(field),
            expected,
            "CORPUS_MANIFEST_METADATA_MISMATCH",
            "候选 ingestion manifest 与候选语料包不一致。",
        )
    _require_equal(
        manifest.get("chunk_checksums"),
        [
            {"chunk_id": chunk["chunk_id"], "content_checksum": chunk["content_checksum"]}
            for chunk in package.chunks
        ],
        "CORPUS_MANIFEST_CHUNK_CHECKSUM_MISMATCH",
        "候选 ingestion manifest 未完整绑定语料块校验和。",
    )


def load_candidate_corpus(
    candidate_manifest_path: str | Path,
    candidate_chunks_path: str | Path,
    source_registry_path: str | Path,
) -> CandidateCorpusPackage:
    """Load and validate the candidate package for review or Owner promotion."""

    try:
        manifest = json.loads(Path(candidate_manifest_path).read_text(encoding="utf-8"))
        candidate = json.loads(Path(candidate_chunks_path).read_text(encoding="utf-8"))
        registry = json.loads(Path(source_registry_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CorpusReleaseFailure(
            "CORPUS_FILES_INVALID",
            "候选语料文件无法读取或格式无效。",
        ) from error
    if not all(isinstance(payload, Mapping) for payload in (manifest, candidate, registry)):
        raise CorpusReleaseFailure("CORPUS_FILES_INVALID", "候选语料文件结构无效。")

    package = validate_candidate_against_source_registry(candidate, registry)
    validate_candidate_manifest(manifest, package, candidate)
    return CandidateCorpusPackage(
        manifest=dict(manifest),
        chunks=package.chunks,
        source_registry_checksum=package.source_registry_checksum,
    )
