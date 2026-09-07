"""Provider-neutral V3.1 AI chain after ConfirmedUserState.

This module is the narrow seam between the frozen internal state object and
the existing Agent 2/3 boundaries. It does not own Session, DocumentSet,
Relevance, Assessment, or Diagnosis persistence. Those records are resolved
by their owning services and passed here as an already-authorized snapshot.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
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


class V31PipelineBlocked(ValueError):
    """Raised before or during the V3.1 provider chain at a safe boundary."""

    def __init__(self, error_code: str, safe_message: str = "V3.1 AI 链路尚未就绪。") -> None:
        self.error_code = error_code
        self.safe_message = safe_message
        super().__init__(f"{error_code}: {safe_message}")


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
) -> V31AiPipelineResult:
    """Execute Query Builder -> Embedding/Chroma -> Qwen -> Agent 3.

    The query and provider request are built only from the confirmed state
    projection and approved assessment fields. In particular, UserGoal is
    never copied into Agent 2; Agent 3 receives it only through its bounded
    deterministic parameter-rule selector in a later call boundary.
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
    )
    if execution.status == "abstained":
        raise V31PipelineBlocked("DIAGNOSIS_ABSTAINED")
    if execution.status == "failed":
        raise V31PipelineBlocked(execution.reason_code or "DIAGNOSIS_FAILED")
    if execution.response is None:
        raise V31PipelineBlocked("DIAGNOSIS_FAILED")

    diagnosis_id = str(assessment_snapshot.get("diagnosis_id") or f"diag_{uuid.uuid4().hex}")
    evidence_refs = [
        str(item)
        for item in (
            assessment_snapshot.get("supporting_fact_ids") or []
        )
    ] + [hit.chunk_id for hit in rag_result.hits]
    profile = build_tone_profile_v31(
        diagnosis_id=diagnosis_id,
        diagnosis_revision=int(assessment_snapshot.get("diagnosis_revision", 1)),
        diagnosis_status=execution.status,
        organ_weights=_mapping_value(assessment_snapshot, "organ_weights"),
        supporting_evidence_refs=evidence_refs,
        mapping=tone_mapping,
        secondary_threshold=secondary_threshold,
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
    )


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
        result = rag_store.query(query)
    except Exception as error:
        from .rag_store import RagStoreFailure

        if not isinstance(error, RagStoreFailure):
            raise
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
