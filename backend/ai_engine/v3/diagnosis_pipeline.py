"""Deterministic query construction and validation around Agent2."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from hashlib import sha256
import inspect
import json
import time
from typing import Literal
import uuid

from pydantic import TypeAdapter, ValidationError

from backend.app.schemas.v3.common import OrganCode
from backend.app.schemas.v3.diagnosis import (
    AssessmentSnapshotRef,
    DiagnosisProviderFact,
    DiagnosisProviderRequest,
    DiagnosisProviderResponse,
    DiagnosisProviderRagRef,
    RagQuery,
    RagResult,
)
from backend.ai_engine.v3.rag_ingestion import (
    approved_text_checksum,
    load_rag_query_policy,
)


class DiagnosisPipelineFailure(RuntimeError):
    """Safe validation failure for an untrusted provider result."""

    def __init__(
        self,
        error_code: str,
        safe_message: str,
        *,
        safe_diagnostics: Mapping[str, object] | None = None,
    ) -> None:
        self.error_code = error_code
        self.safe_message = safe_message
        self.safe_diagnostics = dict(safe_diagnostics or {})
        super().__init__(f"{error_code}: {safe_message}")


@dataclass(frozen=True)
class DiagnosisProviderExecution:
    """Provider-neutral execution result before service persistence mapping."""

    status: Literal["success", "degraded", "abstained", "failed"]
    response: DiagnosisProviderResponse | None
    reason_code: str | None
    provider_run_id: str | None
    provider_name: str
    provider_model: str | None
    medical_rule_version: str | None
    attempts: int
    latency_ms: int
    request_hash: str
    response_hash: str | None
    retryable: bool
    safe_diagnostics: Mapping[str, object] = field(default_factory=dict)


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
    # Sprint 6 Phase 3 (R3-D3): top_k is never a hard-coded product literal.
    # The caller supplies the approved policy value; a caller that does not is
    # resolved against the approved policy asset instead of a code default.
    top_k = snapshot.get("top_k")
    if top_k is None:
        top_k = load_rag_query_policy().top_k
    return RagQuery(
        query_id=query_id,
        knowledge_version=canonical["knowledge_version"],
        ingestion_manifest_checksum=canonical["manifest_checksum"],
        organ_codes=organs,
        claim_codes=claims,
        supporting_fact_ids=supporting,
        contradicting_fact_ids=contradicting,
        top_k=int(top_k),
    )


def validate_diagnosis_provider_response(
    response: DiagnosisProviderResponse,
    *,
    allowed_syndrome_codes: set[str],
    allowed_fact_ids: set[str],
    allowed_chunk_ids: set[str],
    fact_directions: Mapping[str, str] | None = None,
) -> DiagnosisProviderResponse:
    """Reject provider candidates that are not grounded in approved inputs."""

    try:
        checked = DiagnosisProviderResponse.model_validate(response)
    except (ValidationError, TypeError, ValueError) as error:
        raise DiagnosisPipelineFailure(
            "DIAGNOSIS_SCHEMA_INVALID",
            "辨证服务返回格式无效。",
        ) from error
    seen_syndrome_codes: set[str] = set()
    for candidate in checked.candidate_tendencies:
        if candidate.syndrome_code not in allowed_syndrome_codes:
            raise DiagnosisPipelineFailure(
                "SYNDROME_NOT_APPROVED",
                "辨证结果包含未批准的证型。",
            )
        # Sprint 6 Phase 4 (F4-D5): one candidate per syndrome code. Two rows with
        # the same code are schema-legal but violate the persistence uniqueness
        # contract, so they must fail here as a mapped provider-contract failure
        # instead of surfacing as a raw IntegrityError at insert time.
        if candidate.syndrome_code in seen_syndrome_codes:
            raise DiagnosisPipelineFailure(
                "DUPLICATE_SYNDROME_CODE",
                "辨证结果包含重复的证型。",
            )
        seen_syndrome_codes.add(candidate.syndrome_code)
        if len(candidate.supporting_fact_ids) != len(set(candidate.supporting_fact_ids)):
            raise DiagnosisPipelineFailure(
                "DUPLICATE_EVIDENCE_REFERENCE",
                "辨证结果包含重复事实引用。",
            )
        if len(candidate.contradicting_fact_ids) != len(set(candidate.contradicting_fact_ids)):
            raise DiagnosisPipelineFailure(
                "DUPLICATE_EVIDENCE_REFERENCE",
                "辨证结果包含重复事实引用。",
            )
        if len(candidate.knowledge_chunk_ids) != len(set(candidate.knowledge_chunk_ids)):
            raise DiagnosisPipelineFailure(
                "DUPLICATE_EVIDENCE_REFERENCE",
                "辨证结果包含重复知识片段引用。",
            )
        referenced_fact_ids = set(candidate.supporting_fact_ids) | set(
            candidate.contradicting_fact_ids
        )
        invalid_fact_ids = sorted(referenced_fact_ids - allowed_fact_ids)
        if invalid_fact_ids:
            raise DiagnosisPipelineFailure(
                "FACT_REFERENCE_INVALID",
                "辨证结果引用了无效事实。",
                safe_diagnostics={
                    "error_code": "FACT_REFERENCE_INVALID",
                    "invalid_fact_ids": invalid_fact_ids,
                    "allowed_fact_ids": sorted(allowed_fact_ids),
                },
            )
        if fact_directions is not None:
            for fact_id in candidate.supporting_fact_ids:
                if fact_directions.get(fact_id) not in {None, "supporting"}:
                    raise DiagnosisPipelineFailure(
                        "EVIDENCE_DIRECTION_MISMATCH",
                        "辨证结果的支持性事实方向不一致。",
                    )
            for fact_id in candidate.contradicting_fact_ids:
                if fact_directions.get(fact_id) not in {None, "contradicting"}:
                    raise DiagnosisPipelineFailure(
                        "EVIDENCE_DIRECTION_MISMATCH",
                        "辨证结果的矛盾性事实方向不一致。",
                    )
        if not set(candidate.knowledge_chunk_ids) <= allowed_chunk_ids:
            raise DiagnosisPipelineFailure(
                "CHUNK_REFERENCE_INVALID",
                "辨证结果引用了无效知识片段。",
            )
    return checked


async def execute_diagnosis_provider(
    *,
    provider,
    request: Mapping[str, object] | object,
    facts: list[object] | tuple[object, ...],
    rag_result: RagResult,
    medical_rule_version: str | None = None,
    rag_chunk_checksums: Mapping[str, str] | None = None,
    rag_text_checksums: Mapping[str, str] | None = None,
    confirmed_state_text: str | None = None,
) -> DiagnosisProviderExecution:
    """Run Agent2 only when the approved RAG gate provides grounded hits.

    The envelope deliberately stays separate from the frozen diagnosis
    transport model so that a degraded index never gets represented as a
    fabricated successful candidate list.
    """

    started = time.perf_counter()
    provider_run_id: str | None = None
    provider_name = str(getattr(provider, "provider_name", "qwen"))
    provider_backend = getattr(provider, "backend", None)
    provider_model = getattr(provider_backend, "model", None)
    medical_release = getattr(provider, "medical_rule_version", None)
    request_hash = _request_hash(request) if confirmed_state_text is None else _request_hash({
        "request_hash": _request_hash(request), "confirmed_state_text": confirmed_state_text,
    })

    def execution(
        status: Literal["success", "degraded", "abstained", "failed"],
        *,
        response: DiagnosisProviderResponse | None,
        reason_code: str | None,
        attempts: int = 0,
        retryable: bool = False,
        safe_diagnostics: Mapping[str, object] | None = None,
    ) -> DiagnosisProviderExecution:
        response_hash = (
            _request_hash(response.model_dump(mode="json"))
            if response is not None
            else None
        )
        return DiagnosisProviderExecution(
            status=status,
            response=response,
            reason_code=reason_code,
            provider_run_id=provider_run_id,
            provider_name=provider_name,
            provider_model=str(provider_model) if provider_model is not None else None,
            medical_rule_version=(
                str(medical_release) if medical_release is not None else None
            ),
            attempts=max(0, int(attempts)),
            latency_ms=max(0, int((time.perf_counter() - started) * 1000)),
            request_hash=request_hash,
            response_hash=response_hash,
            retryable=retryable,
            safe_diagnostics=dict(safe_diagnostics or {}),
        )

    if rag_result.status == "empty":
        return execution(
            "abstained", response=None, reason_code="RAG_EMPTY", attempts=0
        )
    if rag_result.status != "success":
        reasons = rag_result.degradation.reason_codes
        return execution(
            "failed",
            response=None,
            reason_code=str(reasons[0]) if reasons else "RAG_UNAVAILABLE",
            attempts=0,
            retryable=rag_result.status == "degraded",
        )

    approved_chunk_ids = set(getattr(provider, "allowed_chunk_ids", ()))
    for hit in rag_result.hits:
        if getattr(hit, "review_status", None) != "approved":
            return execution(
                "failed",
                response=None,
                reason_code="RAG_UNAPPROVED_CHUNK",
                attempts=0,
            )
        # Sprint 6 Phase 3 (R3-D1): absolute membership enforcement. A
        # successful hit with an empty approved set is invalid; the previous
        # conditional guard silently disabled the check when the set was empty.
        if hit.chunk_id not in approved_chunk_ids:
            return execution(
                "failed",
                response=None,
                reason_code="CHUNK_REFERENCE_INVALID",
                attempts=0,
            )
        # Sprint 6 Phase 3 (R3-D1): defence in depth for any caller handing over
        # the approved live-text hashes. The retrieval store already fails
        # closed on its own; this protects the provider boundary as well.
        if rag_text_checksums:
            expected_text_checksum = rag_text_checksums.get(hit.chunk_id)
            if expected_text_checksum is None:
                return execution(
                    "failed",
                    response=None,
                    reason_code="RAG_CHUNK_TEXT_UNVERIFIABLE",
                    attempts=0,
                )
            if approved_text_checksum(hit.text) != expected_text_checksum:
                return execution(
                    "failed",
                    response=None,
                    reason_code="RAG_CHUNK_CONTENT_CHECKSUM_MISMATCH",
                    attempts=0,
                )

    if medical_rule_version is not None and getattr(provider, "medical_rule_version", None) != medical_rule_version:
        return execution(
            "failed",
            response=None,
            reason_code="MEDICAL_RULE_VERSION_MISMATCH",
            attempts=0,
        )

    # Sprint 6 Phase 4 (F4-D3): candidate knowledge citations are limited to the
    # exact hits of *this* run. The set only ever narrows — the retrieval loop
    # above already rejected any hit outside the caller's approved context — so
    # an approved-but-not-retrieved chunk or a previous run's chunk can no longer
    # be cited. Phase 3's corpus integrity controls are untouched.
    current_hit_ids = {str(hit.chunk_id) for hit in rag_result.hits}
    if hasattr(provider, "allowed_chunk_ids"):
        provider.allowed_chunk_ids = set(current_hit_ids)

    from backend.ai_engine.v3.diagnosis_provider import DiagnosisProviderFailure

    provider_run_id = f"provider_{uuid.uuid4().hex}"
    rag_context = _rag_context(rag_result, rag_chunk_checksums or {})
    try:
        provider_kwargs = {
            "request": request,
            "facts": facts,
            "rag_chunk_ids": [hit.chunk_id for hit in rag_result.hits],
        }
        metadata_call = getattr(provider, "acomplete_json_with_metadata", None)
        call = metadata_call if callable(metadata_call) else provider.acomplete_json
        parameters = inspect.signature(call).parameters
        if confirmed_state_text is not None and (
            "confirmed_state_text" in parameters or any(
                parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()
            )
        ):
            provider_kwargs["confirmed_state_text"] = confirmed_state_text
        if callable(metadata_call):
            response, attempts = await metadata_call(**provider_kwargs, rag_context=rag_context)
        else:
            call = provider.acomplete_json
            parameters = inspect.signature(call).parameters
            supports_context = "rag_context" in parameters or any(
                parameter.kind == inspect.Parameter.VAR_KEYWORD
                for parameter in parameters.values()
            )
            if supports_context:
                response = await call(**provider_kwargs, rag_context=rag_context)
            else:
                response = await call(**provider_kwargs)
            attempts = 1
    except DiagnosisProviderFailure as error:
        if error.attempts == 0:
            provider_run_id = None
        return execution(
            "failed",
            response=None,
            reason_code=error.error_code,
            attempts=error.attempts,
            retryable=error.retryable,
            safe_diagnostics=error.safe_diagnostics,
        )

    # Sprint 6 Phase 4 (F4-D4): the pipeline is the shared, final enforcement
    # point. The Qwen adapter keeps its own validation as defence in depth, but
    # an alternate provider or test double must not be able to bypass the
    # contract, so the same validator runs here against the current-run
    # authoritative sets (approved syndromes, current-revision fact ids with
    # their directions, exact current-run chunk ids).
    shared_syndrome_codes = set(
        getattr(provider, "allowed_syndrome_codes", ()) or ()
    )
    if not shared_syndrome_codes:
        if isinstance(request, Mapping):
            shared_syndrome_codes = set(request.get("allowed_syndrome_codes") or ())
        else:
            shared_syndrome_codes = set(
                getattr(request, "allowed_syndrome_codes", ()) or ()
            )
    # The approved fact set is the union of the ids declared by the request
    # facts and the provider's own allow-list. Both are caller-declared
    # authorities, so an empty union still fails closed (a candidate may not
    # invent a fact id when no fact is approved for this revision).
    allowed_fact_ids = {
        str(entry.fact_evidence_id)
        for entry in facts
        if getattr(entry, "fact_evidence_id", None)
    } | {str(item) for item in (getattr(provider, "allowed_fact_ids", ()) or ())}
    try:
        response = validate_diagnosis_provider_response(
            response,
            allowed_syndrome_codes=shared_syndrome_codes,
            allowed_fact_ids=allowed_fact_ids,
            allowed_chunk_ids=current_hit_ids,
            fact_directions=fact_directions(facts),
        )
    except DiagnosisPipelineFailure as error:
        return execution(
            "failed",
            response=None,
            reason_code=error.error_code,
            attempts=attempts,
            safe_diagnostics=error.safe_diagnostics,
        )
    return execution(
        response.status,
        response=response,
        reason_code=(
            None
            if response.status in {"success", "degraded"}
            else response.abstain_reason
        ),
        attempts=attempts,
    )


def _rag_context(
    rag_result: RagResult,
    chunk_checksums: Mapping[str, str],
) -> list[dict[str, str]]:
    """Project only the current approved retrieval hits into the Qwen prompt."""

    context: list[dict[str, str]] = []
    for hit in rag_result.hits:
        checksum = chunk_checksums.get(hit.chunk_id)
        if not checksum:
            checksum = f"sha256:{sha256(hit.text.encode('utf-8')).hexdigest()}"
        context.append(
            {
                "chunk_id": hit.chunk_id,
                "source": hit.source_id,
                "source_title": hit.source_title,
                "content_checksum": checksum,
                "content": hit.text,
                "display_summary": hit.display_summary,
            }
        )
    return context


def _build_diagnosis_provider_request(
    snapshot: Mapping[str, object],
    rag_result: RagResult,
    *,
    allowed_syndrome_codes: set[str] | None = None,
) -> DiagnosisProviderRequest:
    """Build the frozen provider request from an authorized snapshot only."""

    allowed_codes = set(
        allowed_syndrome_codes
        if allowed_syndrome_codes is not None
        else _strings(snapshot.get("allowed_syndrome_codes"))
    )
    if not allowed_codes:
        raise DiagnosisPipelineFailure(
            "MEDICAL_RULE_ASSET_NOT_CONFIGURED",
            "医学规则资产尚未配置。",
        )

    raw_facts = snapshot.get("facts") or []
    try:
        facts = [DiagnosisProviderFact.model_validate(item) for item in raw_facts]
        organ_profile = _organ_profile(snapshot)
        rag_ref = (
            DiagnosisProviderRagRef(
                retrieval_id=rag_result.retrieval_id,
                knowledge_version=rag_result.knowledge_version,
                chunk_ids=[hit.chunk_id for hit in rag_result.hits],
            )
            if rag_result.status == "success"
            else None
        )
        return DiagnosisProviderRequest(
            request_id=str(snapshot.get("request_id") or f"diag_req_{uuid.uuid4().hex}"),
            schema_version="diagnosis_provider_v3.0",
            response_schema_version="diagnosis_provider_response_v3.0",
            prompt_version=str(snapshot.get("prompt_version") or "diagnosis_prompt_v3.1"),
            assessment_ref=AssessmentSnapshotRef(
                assessment_id=str(snapshot.get("assessment_id") or ""),
                revision=int(snapshot.get("assessment_revision", 1)),
            ),
            organ_profile=organ_profile,
            facts=facts,
            conflicts=TypeAdapter(list).validate_python(snapshot.get("conflicts") or []),
            missing_information=TypeAdapter(list).validate_python(
                snapshot.get("missing_information") or []
            ),
            rag=rag_ref,
            allowed_syndrome_codes=sorted(allowed_codes),
            max_candidates=int(snapshot.get("max_candidates", 3)),
        )
    except DiagnosisPipelineFailure:
        raise
    except (TypeError, ValueError, ValidationError) as error:
        raise DiagnosisPipelineFailure(
            "DIAGNOSIS_REQUEST_INVALID",
            "辨证请求格式无效。",
        ) from error


def _organ_profile(snapshot: Mapping[str, object]):
    value = snapshot.get("organ_profile")
    if isinstance(value, Mapping):
        return value
    weights = snapshot.get("organ_weights")
    if not isinstance(weights, Mapping):
        raise DiagnosisPipelineFailure(
            "ASSESSMENT_SNAPSHOT_INVALID",
            "评估快照格式无效。",
        )
    normalized = {
        organ.value: float(weights.get(organ.value, weights.get(organ, 0.0)))
        for organ in OrganCode
    }
    total = sum(normalized.values())
    if total <= 0:
        raise DiagnosisPipelineFailure(
            "ASSESSMENT_SNAPSHOT_INVALID",
            "评估快照格式无效。",
        )
    return {
        "status": "available",
        "weights": {key: value / total for key, value in normalized.items()},
        "score_semantics": "relative_evidence_distribution",
    }


def fact_directions(facts: Sequence[object] | Mapping[str, object]) -> dict[str, str]:
    """Map ``fact_evidence_id`` -> declared direction for direction validation.

    Shared by the provider adapter and the pipeline-level enforcement so the two
    cannot drift.
    """

    directions: dict[str, str] = {}
    items: Sequence[object]
    if isinstance(facts, Mapping):
        items = list(facts.values())
    else:
        items = list(facts)
    for fact in items:
        dumped: object
        if hasattr(fact, "model_dump"):
            dumped = fact.model_dump(mode="json")
        elif isinstance(fact, Mapping):
            dumped = dict(fact)
        else:
            dumped = fact
        if not isinstance(dumped, Mapping):
            continue
        fact_id = dumped.get("fact_evidence_id")
        direction = dumped.get("direction")
        if isinstance(fact_id, str) and isinstance(direction, str):
            directions[fact_id] = direction
    return directions


def _strings(value: object) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [item.value if hasattr(item, "value") else str(item) for item in value]


def _request_hash(value: object) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if not isinstance(value, Mapping):
        value = {"value": value}
    encoded = _canonical_json(value)
    return f"sha256:{sha256(encoded).hexdigest()}"


def _canonical_json(value: Mapping[str, object]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
