"""Provider-neutral V3.1 AI chain after ConfirmedUserState.

This module is the narrow seam between the frozen internal state object and
the existing Agent 2/3 boundaries. It does not own Session, DocumentSet,
Relevance, Assessment, or Diagnosis persistence. Those records are resolved
by their owning services and passed here as an already-authorized snapshot.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import inspect
import uuid

from backend.app.schemas.v3.common import Degradation
from backend.app.schemas.v3.diagnosis import (
    DiagnosisProviderRequest,
    DiagnosisProviderResponse,
    RagQuery,
    RagResult,
)
from backend.app.schemas.v3.flow_v31 import (
    ConfirmedUserState,
    FiveToneAnalysisReadModel,
    FiveToneAnalysisReadModelV33,
    ToneProfileV31,
)

from .agent3 import (
    GenerationSpecV31,
    build_five_tone_analysis_v31,
    build_generation_spec_v31,
    build_tone_profile_v31,
)
from .diagnosis_pipeline import (
    DiagnosisProviderExecution,
    _build_diagnosis_provider_request,
    build_diagnosis_query,
    execute_diagnosis_provider,
)
from backend.app.schemas.v3.flow_v31 import OrganDominanceDecisionV1
from backend.app.services.v3.knowledge_assets import load_organ_mapping
from backend.app.services.v3.organ_dominance_service import (
    DominanceReadinessError,
    OrganAggregationSnapshot,
    load_configured_dominance_rule,
    resolve_organ_dominance,
    verify_candidate_policy_consistency,
    verify_mapping_identity,
)


class V31PipelineBlocked(ValueError):
    """Raised before or during the V3.1 provider chain at a safe boundary."""

    def __init__(
        self,
        error_code: str,
        safe_message: str = "V3.1 AI 链路尚未就绪。",
        *,
        audit_context: "V31PipelineAuditContext | None" = None,
        retryable: bool = False,
        safe_diagnostics: Mapping[str, object] | None = None,
    ) -> None:
        self.error_code = error_code
        self.safe_message = safe_message
        self.audit_context = audit_context
        self.retryable = retryable
        self.safe_diagnostics = dict(safe_diagnostics or {})
        super().__init__(f"{error_code}: {safe_message}")


@dataclass(frozen=True)
class V31PipelineAuditContext:
    """Provider/RAG metadata available even when Agent2 cannot finish."""

    query: RagQuery
    rag_result: RagResult
    diagnosis_request: DiagnosisProviderRequest
    diagnosis_execution: DiagnosisProviderExecution
    rag_manifest: object | None
    rag_chunk_checksums: Mapping[str, str]
    mapping_version: str
    # Sprint 6 Phase 3: policy-aware query-builder identity + the approved
    # live-text hashes used for runtime integrity verification and audit.
    query_builder_version: str = "diagnosis_query_v3.1"
    rag_text_checksums: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class V31AiPipelineResult:
    confirmed_user_state: ConfirmedUserState
    query: RagQuery
    rag_result: RagResult
    diagnosis_request: DiagnosisProviderRequest
    diagnosis_execution: DiagnosisProviderExecution
    diagnosis: DiagnosisProviderResponse | None
    tone_profile: ToneProfileV31
    generation_spec: GenerationSpecV31
    read_model: FiveToneAnalysisReadModel
    rag_manifest: object | None
    rag_chunk_checksums: Mapping[str, str]
    audit_context: V31PipelineAuditContext | None = None
    dominance_decision: OrganDominanceDecisionV1 | None = None


async def execute_v31_ai_pipeline(
    *,
    confirmed_user_state: ConfirmedUserState | Mapping[str, object],
    assessment_snapshot: Mapping[str, object],
    rag_store,
    diagnosis_provider,
    tone_mapping: Mapping[str, object],
    generation_parameter_rules: Mapping[str, object] | None,
    user_goal: Mapping[str, object] | object | None = None,
    secondary_threshold: float | None = None,
    dominance_rule: Mapping[str, object] | None = None,
    organ_mapping: Mapping[str, object] | None = None,
    organ_aggregation: OrganAggregationSnapshot | None = None,
) -> V31AiPipelineResult:
    """Execute Query Builder -> Embedding/Chroma -> Qwen -> dominance -> Agent 3.

    The query and provider request are built only from the confirmed state
    projection and approved assessment fields. In particular, UserGoal is
    never copied into Agent 2; Agent 3 receives it only through its bounded
    deterministic parameter-rule selector in a later call boundary.

    Sprint 6 Phase 1B: the music-design decision is produced once by the
    authoritative dominance service (from the canonical aggregation snapshot
    evaluated by Agent 1) and Agent3 only constructs the tone profile from it.
    Provider/RAG/asset failures stay failures and never become a mode.
    """

    state = _validate_confirmed_state(confirmed_user_state, assessment_snapshot)
    if rag_store is None or diagnosis_provider is None:
        raise V31PipelineBlocked("V31_PROVIDER_CHAIN_NOT_READY")

    query = build_diagnosis_query(assessment_snapshot)
    rag_result = _query_rag(rag_store, query, assessment_snapshot)
    diagnosis_request = _build_diagnosis_provider_request(
        assessment_snapshot,
        rag_result,
        allowed_syndrome_codes=set(
            getattr(diagnosis_provider, "allowed_syndrome_codes", ())
        ),
    )
    facts = list(diagnosis_request.facts)
    execution = await execute_diagnosis_provider(
        provider=diagnosis_provider,
        request=diagnosis_request,
        facts=facts,
        rag_result=rag_result,
        medical_rule_version=(
            str(assessment_snapshot["medical_rule_version"])
            if assessment_snapshot.get("medical_rule_version") is not None
            else None
        ),
        rag_chunk_checksums=dict(getattr(rag_store, "chunk_checksums", {})),
        rag_text_checksums=dict(getattr(rag_store, "chunk_text_checksums", {})),
        confirmed_state_text=assessment_snapshot.get("confirmed_state_text"),
    )
    audit_context = V31PipelineAuditContext(
        query=query,
        rag_result=rag_result,
        diagnosis_request=diagnosis_request,
        diagnosis_execution=execution,
        rag_manifest=getattr(rag_store, "manifest", None),
        rag_chunk_checksums=dict(getattr(rag_store, "chunk_checksums", {})),
        mapping_version=_mapping_version(tone_mapping),
        query_builder_version=str(
            assessment_snapshot.get("query_builder_version")
            or getattr(
                getattr(rag_store, "query_policy", None),
                "builder_identity",
                "diagnosis_query_v3.1",
            )
        ),
        rag_text_checksums=dict(getattr(rag_store, "chunk_text_checksums", {})),
    )
    if execution.status == "abstained":
        pass
    if execution.status == "failed":
        raise V31PipelineBlocked(
            execution.reason_code or "DIAGNOSIS_FAILED",
            audit_context=audit_context,
            retryable=execution.retryable,
            safe_diagnostics=execution.safe_diagnostics,
        )
    if execution.response is None and execution.status != "abstained":
        raise V31PipelineBlocked("DIAGNOSIS_FAILED", audit_context=audit_context)

    diagnosis_id = str(assessment_snapshot.get("diagnosis_id") or f"diag_{uuid.uuid4().hex}")
    evidence_refs = [
        str(item)
        for item in (
            assessment_snapshot.get("supporting_fact_ids") or []
        )
    ] + [
        str(item)
        for item in (assessment_snapshot.get("contradicting_fact_ids") or [])
    ] + [hit.chunk_id for hit in rag_result.hits]
    if not evidence_refs:
        evidence_refs = [f"confirmed_state:{state.confirmed_user_state_id}"]
    decision = _resolve_dominance_decision(
        assessment_snapshot=assessment_snapshot,
        state=state,
        execution=execution,
        tone_mapping=tone_mapping,
        dominance_rule=dominance_rule,
        organ_mapping=organ_mapping,
        organ_aggregation=organ_aggregation,
        audit_context=audit_context,
        upstream_status=execution.status,
    )
    profile = build_tone_profile_v31(
        diagnosis_id=diagnosis_id,
        diagnosis_revision=int(assessment_snapshot.get("diagnosis_revision", 1)),
        diagnosis_status=execution.status,
        organ_weights=_mapping_value(assessment_snapshot, "organ_weights"),
        supporting_evidence_refs=evidence_refs,
        mapping=tone_mapping,
        secondary_threshold=secondary_threshold,
        dominance_decision=decision,
    )
    generation_spec = build_generation_spec_v31(
        profile=profile,
        parameter_rules=generation_parameter_rules,
        user_goal=user_goal,
        secondary_threshold=secondary_threshold,
    )
    read_model = build_five_tone_analysis_v31(
        confirmed_user_state_ref={
            "confirmed_user_state_id": state.confirmed_user_state_id,
            "revision": state.revision,
            "content_checksum": state.content_checksum,
        },
        confirmed_state=state.confirmed_state_text,
        state_tendency=str(
            assessment_snapshot.get("state_tendency") or "整体状态倾向已根据确认信息整理。"
        ),
        profile=profile,
        evidence_refs=evidence_refs,
        mapping=tone_mapping,
        generation_spec=generation_spec,
        dominance_decision=decision,
    )
    return V31AiPipelineResult(
        confirmed_user_state=state,
        query=query,
        rag_result=rag_result,
        diagnosis_request=diagnosis_request,
        diagnosis_execution=execution,
        diagnosis=execution.response,
        tone_profile=profile,
        generation_spec=generation_spec,
        read_model=read_model,
        rag_manifest=getattr(rag_store, "manifest", None),
        rag_chunk_checksums=dict(getattr(rag_store, "chunk_checksums", {})),
        audit_context=audit_context,
        dominance_decision=decision,
    )


@dataclass(frozen=True)
class V31LegalAbstainResult:
    """Authoritative result of a *legal abstain* (no provider/RAG call)."""

    dominance_decision: OrganDominanceDecisionV1
    tone_profile: ToneProfileV31
    generation_spec: GenerationSpecV31
    read_model: FiveToneAnalysisReadModel | FiveToneAnalysisReadModelV33


def build_v31_legal_abstain(
    *,
    confirmed_user_state: ConfirmedUserState | Mapping[str, object],
    assessment_snapshot: Mapping[str, object],
    tone_mapping: Mapping[str, object],
    generation_parameter_rules: Mapping[str, object] | None,
    abstain_reason: str,
    dominance_rule: Mapping[str, object] | None = None,
    organ_mapping: Mapping[str, object] | None = None,
    organ_aggregation: OrganAggregationSnapshot | None = None,
    secondary_threshold: float | None = None,
) -> V31LegalAbstainResult:
    """Assemble the frozen ``basic_wellness`` outcome for a legal abstain.

    Sprint 6 Phase 1B: an early legal abstain (element evidence insufficient)
    must produce the same authoritative decision + v3.3 read model as the
    pipeline path, without querying RAG or a provider. Technical/readiness
    reasons never reach this function as an abstain: they are validated by the
    dominance service and fail closed.
    """

    state = _validate_confirmed_state(confirmed_user_state, assessment_snapshot)
    decision = _resolve_dominance_decision(
        assessment_snapshot=assessment_snapshot,
        state=state,
        execution=None,
        tone_mapping=tone_mapping,
        dominance_rule=dominance_rule,
        organ_mapping=organ_mapping,
        organ_aggregation=organ_aggregation,
        audit_context=None,
        upstream_status="abstained",
        upstream_abstain_reason=abstain_reason,
    )
    evidence_refs = [
        str(item) for item in (assessment_snapshot.get("supporting_fact_ids") or [])
    ] + [
        str(item) for item in (assessment_snapshot.get("contradicting_fact_ids") or [])
    ]
    if not evidence_refs:
        evidence_refs = [f"confirmed_state:{state.confirmed_user_state_id}"]
    profile = build_tone_profile_v31(
        diagnosis_id=str(
            assessment_snapshot.get("diagnosis_id")
            or f"diag_abstain_{assessment_snapshot.get('assessment_id', 'assessment')}"
        ),
        diagnosis_revision=int(assessment_snapshot.get("assessment_revision", 1)),
        diagnosis_status="abstained",
        organ_weights={},
        supporting_evidence_refs=evidence_refs,
        mapping=tone_mapping,
        secondary_threshold=secondary_threshold,
        dominance_decision=decision,
    )
    generation_spec = build_generation_spec_v31(
        profile=profile,
        parameter_rules=generation_parameter_rules,
        secondary_threshold=secondary_threshold,
    )
    read_model = build_five_tone_analysis_v31(
        confirmed_user_state_ref={
            "confirmed_user_state_id": state.confirmed_user_state_id,
            "revision": state.revision,
            "content_checksum": state.content_checksum,
        },
        confirmed_state=state.confirmed_state_text,
        state_tendency=str(
            assessment_snapshot.get("state_tendency")
            or "当前证据不足以形成五音主音方向。"
        ),
        profile=profile,
        evidence_refs=evidence_refs,
        mapping=tone_mapping,
        generation_spec=generation_spec,
        dominance_decision=decision,
    )
    return V31LegalAbstainResult(
        dominance_decision=decision,
        tone_profile=profile,
        generation_spec=generation_spec,
        read_model=read_model,
    )


def _resolve_dominance_decision(
    *,
    assessment_snapshot: Mapping[str, object],
    state: ConfirmedUserState,
    execution: DiagnosisProviderExecution | None,
    tone_mapping: Mapping[str, object],
    dominance_rule: Mapping[str, object] | None,
    organ_mapping: Mapping[str, object] | None,
    organ_aggregation: OrganAggregationSnapshot | None,
    audit_context: V31PipelineAuditContext | None,
    upstream_status: str | None = None,
    upstream_abstain_reason: str | None = None,
) -> OrganDominanceDecisionV1:
    """Produce the single authoritative Phase 1B decision for this run.

    Asset problems (missing/unapproved/tampered rule, mapping identity
    mismatch) are readiness failures: they are raised as pipeline blocks and
    never resolved into ``basic_wellness`` or any other music mode.
    """

    try:
        rule = (
            dominance_rule
            if dominance_rule is not None
            else load_configured_dominance_rule()
        )
        mapping_asset = (
            organ_mapping if organ_mapping is not None else load_organ_mapping()
        )
    except (ValueError, OSError, TypeError) as error:
        raise V31PipelineBlocked(
            getattr(error, "error_code", "DOMINANCE_RULE_ASSET_INVALID"),
            getattr(error, "safe_message", "主导度规则资产无效。"),
            audit_context=audit_context,
        ) from None
    aggregation = organ_aggregation
    if aggregation is None:
        aggregation = assessment_snapshot.get("organ_aggregation")
    if not isinstance(aggregation, OrganAggregationSnapshot):
        raise V31PipelineBlocked(
            "ASSESSMENT_AGGREGATION_NOT_READY",
            "主导度判定所需的脏腑聚合快照尚未准备完成。",
            audit_context=audit_context,
        )
    try:
        assets = verify_mapping_identity(
            rule, organ_mapping=mapping_asset, five_tone_mapping=tone_mapping
        )
        # The approved organ mapping stays the candidate authority: a drift
        # against the dominance asset's documented policy is a readiness
        # failure, never a silently different candidate set.
        verify_candidate_policy_consistency(rule, organ_mapping=mapping_asset)
        return resolve_organ_dominance(
            assessment_id=str(
                assessment_snapshot.get("assessment_id")
                or assessment_snapshot.get("diagnosis_id")
                or "assessment"
            ),
            assessment_revision=int(assessment_snapshot.get("assessment_revision", 1)),
            input_revision=int(assessment_snapshot.get("input_revision", 1)),
            aggregation=aggregation,
            conflicts=assessment_snapshot.get("conflicts") or [],
            fact_claims=aggregation.fact_claims_by_fact_id,
            dominance_rule=rule,
            five_tone_mapping=tone_mapping,
            assets=assets,
            confirmed_user_state_id=state.confirmed_user_state_id,
            confirmed_user_state_revision=state.revision,
            upstream_abstain_reason=(
                upstream_abstain_reason
                if upstream_abstain_reason is not None
                else (
                    execution.reason_code
                    if execution is not None and execution.status == "abstained"
                    else None
                )
            ),
            upstream_status=(
                upstream_status
                if upstream_status is not None
                else (execution.status if execution is not None else None)
            ),
        )
    except DominanceReadinessError as error:
        raise V31PipelineBlocked(
            error.error_code,
            error.safe_message,
            audit_context=audit_context,
        ) from None


def _validate_confirmed_state(
    value: ConfirmedUserState | Mapping[str, object],
    snapshot: Mapping[str, object],
) -> ConfirmedUserState:
    if isinstance(value, Mapping):
        if value.get("authority_status") != "current":
            raise V31PipelineBlocked("CONFIRMED_USER_STATE_NOT_CURRENT")
        if value.get("confirmation_status") != "confirmed":
            raise V31PipelineBlocked("CONFIRMED_USER_STATE_NOT_CONFIRMED")
    try:
        state = ConfirmedUserState.model_validate(value)
    except (TypeError, ValueError) as error:
        raise V31PipelineBlocked("CONFIRMED_USER_STATE_INVALID") from error
    if state.authority_status != "current" or state.confirmation_status != "confirmed":
        raise V31PipelineBlocked("CONFIRMED_USER_STATE_NOT_CURRENT")
    expected_session_id = snapshot.get("session_id")
    if expected_session_id is not None and state.session_id != expected_session_id:
        raise V31PipelineBlocked("CONFIRMED_USER_STATE_NOT_OWNED")
    return state


def _query_rag(rag_store, query: RagQuery, snapshot: Mapping[str, object]) -> RagResult:
    try:
        parameters = inspect.signature(rag_store.query).parameters
        text = snapshot.get("confirmed_state_text")
        if text is not None and ("confirmed_state_text" in parameters or any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()
        )):
            result = rag_store.query(query, confirmed_state_text=text)
        else:
            result = rag_store.query(query)
    except Exception as error:
        from .rag_store import RagStoreFailure

        if not isinstance(error, RagStoreFailure):
            raise
        if error.error_code == "RAG_QUERY_MAPPING_NOT_APPROVED":
            raise V31PipelineBlocked(
                error.error_code,
                error.safe_message,
            ) from None
        return RagResult(
            retrieval_id=f"rag_degraded_{uuid.uuid4().hex}",
            status="degraded",
            knowledge_version=query.knowledge_version,
            embedding_version=str(snapshot.get("embedding_version") or "unknown"),
            retrieval_score_semantics=str(
                snapshot.get("retrieval_score_semantics") or "unavailable"
            ),
            hits=[],
            degradation=Degradation(active=True, reason_codes=[error.error_code]),
        )
    if not isinstance(result, RagResult):
        raise V31PipelineBlocked("RAG_INVALID_RESULT")
    return result


def _mapping_value(snapshot: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = snapshot.get(key)
    if not isinstance(value, Mapping):
        raise V31PipelineBlocked("ASSESSMENT_SNAPSHOT_INVALID")
    return value


def _mapping_version(mapping: Mapping[str, object]) -> str:
    schema_id = str(mapping.get("schema_id", "")).strip()
    schema_version = str(mapping.get("schema_version", "")).strip()
    return f"{schema_id}@{schema_version}" if schema_id and schema_version else "unknown"
