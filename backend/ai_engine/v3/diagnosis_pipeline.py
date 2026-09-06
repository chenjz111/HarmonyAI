"""Deterministic query construction and validation around Agent2."""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json

from pydantic import ValidationError

from backend.app.schemas.v3.diagnosis import DiagnosisProviderResponse, RagQuery


class DiagnosisPipelineFailure(RuntimeError):
    """Safe validation failure for an untrusted provider result."""

    def __init__(self, error_code: str, safe_message: str) -> None:
        self.error_code = error_code
        self.safe_message = safe_message
        super().__init__(f"{error_code}: {safe_message}")


def build_diagnosis_query(snapshot: Mapping[str, object]) -> RagQuery:
    """Create a stable RAG query from already-approved snapshot projections."""

    approved_organs = set(_strings(snapshot.get("approved_organ_codes")))
    approved_claims = set(_strings(snapshot.get("approved_claim_codes")))
    organs = sorted(set(_strings(snapshot.get("organ_codes"))) & approved_organs)
    claims = sorted(set(_strings(snapshot.get("claim_codes"))) & approved_claims)
    supporting = sorted(set(_strings(snapshot.get("supporting_fact_ids"))))
    contradicting = sorted(set(_strings(snapshot.get("contradicting_fact_ids"))))
    canonical = {
        "knowledge_version": str(snapshot["knowledge_version"]),
        "manifest_checksum": str(snapshot["manifest_checksum"]),
        "organ_codes": organs,
        "claim_codes": claims,
        "supporting_fact_ids": supporting,
        "contradicting_fact_ids": contradicting,
    }
    query_id = f"query_{sha256(_canonical_json(canonical)).hexdigest()[:24]}"
    return RagQuery(
        query_id=query_id,
        knowledge_version=canonical["knowledge_version"],
        ingestion_manifest_checksum=canonical["manifest_checksum"],
        organ_codes=organs,
        claim_codes=claims,
        supporting_fact_ids=supporting,
        contradicting_fact_ids=contradicting,
        top_k=int(snapshot.get("top_k", 5)),
    )


def validate_diagnosis_provider_response(
    response: DiagnosisProviderResponse,
    *,
    allowed_syndrome_codes: set[str],
    allowed_fact_ids: set[str],
    allowed_chunk_ids: set[str],
) -> DiagnosisProviderResponse:
    """Reject provider candidates that are not grounded in approved inputs."""

    try:
        checked = DiagnosisProviderResponse.model_validate(response)
    except (ValidationError, TypeError, ValueError) as error:
        raise DiagnosisPipelineFailure(
            "DIAGNOSIS_SCHEMA_INVALID",
            "辨证服务返回格式无效。",
        ) from error
    for candidate in checked.candidate_tendencies:
        if candidate.syndrome_code not in allowed_syndrome_codes:
            raise DiagnosisPipelineFailure(
                "SYNDROME_NOT_APPROVED",
                "辨证结果包含未批准的证型。",
            )
        if not set(candidate.supporting_fact_ids) <= allowed_fact_ids:
            raise DiagnosisPipelineFailure(
                "FACT_REFERENCE_INVALID",
                "辨证结果引用了无效事实。",
            )
        if not set(candidate.contradicting_fact_ids) <= allowed_fact_ids:
            raise DiagnosisPipelineFailure(
                "FACT_REFERENCE_INVALID",
                "辨证结果引用了无效事实。",
            )
        if not set(candidate.knowledge_chunk_ids) <= allowed_chunk_ids:
            raise DiagnosisPipelineFailure(
                "CHUNK_REFERENCE_INVALID",
                "辨证结果引用了无效知识片段。",
            )
    return checked


def _strings(value: object) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [item.value if hasattr(item, "value") else str(item) for item in value]


def _canonical_json(value: Mapping[str, object]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
