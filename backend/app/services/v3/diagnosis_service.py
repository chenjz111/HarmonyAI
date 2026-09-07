"""Agent 2 — owner-scoped V3.1 diagnosis orchestration.

The formal V3.1 endpoint keeps the existing ownership and idempotency gates,
then projects only confirmed persistence rows into ``ConfirmedUserState`` and
the frozen ``DiagnosisProviderRequest``.  Real mode is readiness-gated through
the explicit Embedding/Chroma/Qwen dependency factory; legacy V3.0 behavior is
retained when real mode is disabled.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import datetime, timezone
from hashlib import sha256
import json
import uuid

from sqlalchemy.orm import Session

from backend.app.models import Session as SessionModel
from backend.app.models.v3.assessment import AssessmentRevisionV3, AssessmentV3
from backend.app.models.v3.assessment import (
    FactEvidence as FactEvidenceRow,
    OrganEvidence as OrganEvidenceRow,
)
from backend.app.models.v3.diagnosis import (
    AiProviderRun,
    DiagnosisCandidateEvidence,
    DiagnosisCandidate as DiagnosisCandidateRow,
    DiagnosisRun,
    KnowledgeManifest,
    RagRetrievalHit,
    RagRetrievalRun,
)
from backend.app.models.v3.understanding import (
    FactSourceRef,
    QuestionnaireSubmissionV3,
    UnderstandingRevision,
    UnderstandingRun,
)
from backend.app.schemas.v3.assessment import AssessmentRefV31
from backend.app.schemas.v3.common import (
    AuthPrincipal,
    Degradation,
    ElementCode,
    ElementProfile,
    OrganCode,
)
from backend.app.schemas.v3.diagnosis import (
    AbstainedDiagnosis,
    DiagnosisV3,
    DiagnosisV31Input,
    DiagnosisPresentation,
    ExecutionVersions,
    DiagnosisCandidate,
    KnowledgeReference,
)
from backend.app.schemas.v3.flow_v31 import ConfirmedUserState
from backend.ai_engine.v3.diagnosis_pipeline import DiagnosisPipelineFailure
from backend.ai_engine.v3.v31_pipeline import (
    V31AiPipelineResult,
    V31PipelineAuditContext,
    V31PipelineBlocked,
    execute_v31_ai_pipeline,
)
from backend.ai_engine.v3.agent3 import Agent3Blocked
from backend.app.services.v3.idempotency import (
    IdempotencyConflict,
    IdempotencyInProgress,
    reserve_v3_idempotency,
)


class OwnedResourceNotFound(RuntimeError):
    pass


class MedicalAssetUnavailable(RuntimeError):
    pass


class V31ReadinessError(RuntimeError):
    """A formal V3.1 dependency is unavailable or not approved."""

    def __init__(self, error_code: str, safe_message: str = "V3.1 AI 链路尚未就绪。"):
        self.error_code = error_code
        self.safe_message = safe_message
        super().__init__(f"{error_code}: {safe_message}")


class V31PipelineFailure(RuntimeError):
    """A formal V3.1 provider/schema/rule failure, never an abstention."""

    def __init__(
        self,
        error_code: str,
        safe_message: str = "V3.1 AI 链路执行失败。",
        *,
        audit_context: V31PipelineAuditContext | None = None,
    ):
        self.error_code = error_code
        self.safe_message = safe_message
        self.audit_context = audit_context
        super().__init__(f"{error_code}: {safe_message}")


_OPERATION = "create_v3_diagnosis"


def _request_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


_ORGAN_ELEMENT = {
    "liver": "wood",
    "heart": "fire",
    "spleen": "earth",
    "lung": "metal",
    "kidney": "water",
}


def _element_profile_from_organ(
    organ_profile_json: dict | None,
) -> ElementProfile:
    """Derive the element profile from the approved organ_element mapping.

    Insufficient organ evidence yields an insufficient element profile —
    the honest abstain input for Agent 2.
    """
    if not organ_profile_json or organ_profile_json.get("status") != "available":
        return ElementProfile(
            status="insufficient",
            weights=None,
            score_semantics="relative_element_support",
        )
    organ_weights = organ_profile_json.get("weights") or {}
    element_weights: dict[ElementCode, float] = {
        element: 0.0 for element in ElementCode
    }
    for organ_code, weight in organ_weights.items():
        element = _ORGAN_ELEMENT.get(organ_code)
        if element is not None:
            element_weights[ElementCode(element)] += float(weight)
    total = sum(element_weights.values())
    if total <= 0:
        return ElementProfile(
            status="insufficient",
            weights=None,
            score_semantics="relative_element_support",
        )
    normalized = {key: round(value / total, 4) for key, value in element_weights.items()}
    return ElementProfile(
        status="available",
        weights=normalized,
        score_semantics="relative_element_support",
    )


def _v31_real_mode() -> bool:
    from backend.app.core.agent_config import get_v31_provider_config

    return get_v31_provider_config().real_agents


def _load_confirmed_user_state(
    db: Session,
    *,
    assessment: AssessmentV3,
    assessment_revision: AssessmentRevisionV3,
    session_row: SessionModel,
) -> ConfirmedUserState:
    """Project reviewed persistence into the internal ConfirmedUserState.

    This is an adapter boundary until the reviewed #104/#105 state loader is
    available.  It reads only owner-scoped confirmed rows and does not copy
    their persistence implementation or accept state from the request body.
    """

    final_summary_ref = None
    if assessment.understanding_id is not None:
        understanding_run = (
            db.query(UnderstandingRun)
            .filter(
                UnderstandingRun.understanding_id == assessment.understanding_id,
                UnderstandingRun.current_revision == assessment.understanding_revision,
                UnderstandingRun.internal_user_pk == session_row.user_id,
                UnderstandingRun.session_row_id == session_row.id,
                UnderstandingRun.status == "confirmed",
            )
            .one_or_none()
        )
        understanding_revision = (
            db.query(UnderstandingRevision)
            .filter(
                UnderstandingRevision.understanding_id == assessment.understanding_id,
                UnderstandingRevision.revision == assessment.understanding_revision,
                UnderstandingRevision.status == "confirmed",
            )
            .one_or_none()
        )
        if understanding_run is None or understanding_revision is None:
            raise V31PipelineFailure("CONFIRMED_USER_STATE_NOT_OWNED")
        case_summary = understanding_revision.case_summary_json
        if not isinstance(case_summary, Mapping):
            raise V31PipelineFailure("CONFIRMED_USER_STATE_INVALID")
        summary_payload = dict(case_summary)
        summary_checksum = str(summary_payload.get("content_checksum") or "")
        if not summary_checksum.startswith("sha256:"):
            summary_checksum = _request_hash(
                {key: value for key, value in summary_payload.items() if key != "content_checksum"}
            )
        final_summary_ref = {
            "summary_id": str(
                summary_payload.get("case_summary_id")
                or summary_payload.get("summary_id")
                or f"summary_{assessment.understanding_id}_{assessment.understanding_revision}"
            ),
            "revision": int(summary_payload.get("revision") or assessment.understanding_revision),
            "content_checksum": summary_checksum,
            "confirmation_status": "confirmed",
        }

    questionnaire_ref = None
    if assessment.questionnaire_submission_id is not None:
        submission = (
            db.query(QuestionnaireSubmissionV3)
            .filter(
                QuestionnaireSubmissionV3.questionnaire_submission_id
                == assessment.questionnaire_submission_id,
                QuestionnaireSubmissionV3.internal_user_pk == session_row.user_id,
                QuestionnaireSubmissionV3.session_row_id == session_row.id,
            )
            .one_or_none()
        )
        if (
            submission is None
            or submission.schema_id != "questionnaire_v3"
            or submission.schema_version != "3.0.1"
            or submission.manifest_version != "medical_v3.0.1"
            or not submission.content_checksum.startswith("sha256:")
            or len(submission.answers_json or []) != 10
        ):
            raise V31PipelineFailure("CONFIRMED_USER_STATE_INVALID")
        questionnaire_ref = {
            "questionnaire_result_id": submission.questionnaire_submission_id,
            "revision": 1,
            "content_checksum": submission.content_checksum,
            "completion_status": "complete",
        }

    if final_summary_ref is not None and questionnaire_ref is not None:
        source_mode = "document_plus_questionnaire"
    elif final_summary_ref is not None:
        source_mode = "document_only"
    elif questionnaire_ref is not None:
        source_mode = "questionnaire_only"
    else:
        raise V31PipelineFailure("CONFIRMED_USER_STATE_INVALID")

    projection: list[dict[str, object]] = []
    evidence_rows = (
        db.query(FactEvidenceRow)
        .filter(
            FactEvidenceRow.assessment_id == assessment.assessment_id,
            FactEvidenceRow.assessment_revision == assessment_revision.revision,
            FactEvidenceRow.confirmation_status == "confirmed",
        )
        .order_by(FactEvidenceRow.fact_evidence_id)
        .all()
    )
    for row in evidence_rows:
        source_rows = (
            db.query(FactSourceRef)
            .filter(FactSourceRef.fact_row_id == row.normalized_fact_row_id)
            .order_by(FactSourceRef.source_type, FactSourceRef.source_id)
            .all()
        )
        source_refs = [f"{item.source_type}:{item.source_id}" for item in source_rows]
        if not source_refs:
            raise V31PipelineFailure("CONFIRMED_USER_STATE_INVALID")
        projection.append(
            {
                "fact_id": row.fact_evidence_id,
                "claim_code": row.claim_code,
                "display_text": row.display_name,
                "source_refs": source_refs,
            }
        )

    input_revision = int(
        session_row.input_revision or assessment.input_revision or assessment_revision.input_revision or 1
    )
    created_at = datetime.now(timezone.utc)
    state_payload = {
        "schema_version": "confirmed_user_state_v3.1",
        "confirmed_user_state_id": f"cus_{assessment.assessment_id}_{assessment_revision.revision}",
        "session_id": session_row.session_id,
        "source_mode": source_mode,
        "final_confirmed_summary_ref": final_summary_ref,
        "questionnaire_result_ref": questionnaire_ref,
        "user_goal_ref": None,
        "confirmed_state_text": assessment_revision.state_summary,
        "normalized_projection": projection,
        "revision": assessment_revision.revision,
        "authority_status": "current",
        "confirmation_status": "confirmed",
        "confirmed_by": "user",
        "session_input_revision": input_revision,
        "created_at": created_at,
    }
    state_checksum_payload = dict(state_payload)
    state_checksum_payload["created_at"] = created_at.isoformat()
    state_payload["content_checksum"] = _request_hash(state_checksum_payload)
    try:
        return ConfirmedUserState.model_validate(state_payload)
    except (TypeError, ValueError) as error:
        raise V31PipelineFailure("CONFIRMED_USER_STATE_INVALID") from error


def _build_v31_assessment_snapshot(
    db: Session,
    *,
    request: DiagnosisV31Input,
    assessment: AssessmentV3,
    assessment_revision: AssessmentRevisionV3,
    deps,
) -> dict[str, object]:
    """Create the provider snapshot exclusively from confirmed DB rows."""

    manifest = getattr(deps.rag_store, "manifest", None)
    if manifest is None:
        raise V31ReadinessError("RAG_MANIFEST_NOT_READY")
    evidence_rows = (
        db.query(FactEvidenceRow)
        .filter(
            FactEvidenceRow.assessment_id == assessment.assessment_id,
            FactEvidenceRow.assessment_revision == assessment_revision.revision,
            FactEvidenceRow.confirmation_status == "confirmed",
        )
        .order_by(FactEvidenceRow.fact_evidence_id)
        .all()
    )
    facts = [
        {
            "fact_evidence_id": row.fact_evidence_id,
            "claim_code": row.claim_code,
            "value": row.value_json,
            "direction": row.direction,
            "time_window": row.time_window,
        }
        for row in evidence_rows
    ]
    supporting = [row.fact_evidence_id for row in evidence_rows if row.direction == "supporting"]
    contradicting = [row.fact_evidence_id for row in evidence_rows if row.direction == "contradicting"]
    organ_codes = {
        item.organ
        for item in db.query(OrganEvidenceRow)
        .join(
            FactEvidenceRow,
            OrganEvidenceRow.fact_evidence_row_id == FactEvidenceRow.fact_evidence_row_id,
        )
        .filter(
            FactEvidenceRow.assessment_id == assessment.assessment_id,
            FactEvidenceRow.assessment_revision == assessment_revision.revision,
        )
        .all()
    }
    organ_profile = assessment_revision.organ_profile_json or {}
    organ_codes.update(str(key) for key in (organ_profile.get("weights") or {}))
    try:
        from backend.app.services.v3.knowledge_assets import load_claim_dictionary

        _claim_version, claims = load_claim_dictionary()
        approved_claim_codes = sorted(claims)
    except (OSError, ValueError, TypeError, KeyError) as error:
        raise V31ReadinessError("MEDICAL_RULE_ASSET_NOT_READY") from error

    provider = deps.diagnosis_provider
    if hasattr(provider, "allowed_fact_ids"):
        provider.allowed_fact_ids = {row.fact_evidence_id for row in evidence_rows}
    if hasattr(provider, "allowed_chunk_ids"):
        provider.allowed_chunk_ids = set(
            getattr(deps.rag_store, "approved_chunk_ids", ())
        )
    return {
        "assessment_id": assessment.assessment_id,
        "assessment_revision": assessment_revision.revision,
        "diagnosis_id": request.diagnosis_id,
        "request_id": f"diag_req_{request.diagnosis_id}",
        "prompt_version": "diagnosis_prompt_v3.1",
        "medical_rule_version": deps.medical_rule_version,
        "organ_profile": organ_profile,
        "organ_weights": organ_profile.get("weights"),
        "organ_codes": sorted(organ_codes),
        "approved_organ_codes": [item.value for item in OrganCode],
        "claim_codes": sorted({item["claim_code"] for item in facts}),
        "approved_claim_codes": approved_claim_codes,
        "supporting_fact_ids": supporting,
        "contradicting_fact_ids": contradicting,
        "facts": facts,
        "conflicts": assessment_revision.conflicts_json or [],
        "missing_information": assessment_revision.missing_information_json or [],
        "knowledge_version": manifest.knowledge_version,
        "manifest_checksum": manifest.manifest_checksum,
        "embedding_version": manifest.embedding_version,
        "retrieval_score_semantics": manifest.retrieval_score_semantics,
        "top_k": 5,
        "max_candidates": 3,
        "allowed_syndrome_codes": sorted(deps.allowed_syndrome_codes),
    }


def _run_v31_pipeline(
    db: Session,
    *,
    request: DiagnosisV31Input,
    assessment: AssessmentV3,
    assessment_revision: AssessmentRevisionV3,
    session_row: SessionModel,
) -> V31AiPipelineResult:
    try:
        from backend.app.core.agent_config import (
            V31ReadinessFailure,
            get_v31_ai_pipeline_dependencies,
        )

        deps = get_v31_ai_pipeline_dependencies()
        state = _load_confirmed_user_state(
            db,
            assessment=assessment,
            assessment_revision=assessment_revision,
            session_row=session_row,
        )
        snapshot = _build_v31_assessment_snapshot(
            db,
            request=request,
            assessment=assessment,
            assessment_revision=assessment_revision,
            deps=deps,
        )
        return asyncio.run(
            execute_v31_ai_pipeline(
                confirmed_user_state=state,
                assessment_snapshot=snapshot,
                rag_store=deps.rag_store,
                diagnosis_provider=deps.diagnosis_provider,
                tone_mapping=deps.tone_mapping,
                generation_parameter_rules=deps.generation_parameter_rules,
                user_goal=assessment.user_goal_json,
            )
        )
    except V31ReadinessFailure as error:
        raise V31ReadinessError(error.error_code, error.safe_message) from None
    except V31ReadinessError:
        raise
    except V31PipelineBlocked as error:
        raise V31PipelineFailure(
            error.error_code,
            error.safe_message,
            audit_context=error.audit_context,
        ) from None
    except (DiagnosisPipelineFailure, Agent3Blocked) as error:
        error_code = getattr(error, "error_code", "V31_PIPELINE_FAILED")
        safe_message = getattr(error, "safe_message", "V3.1 AI 链路执行失败。")
        raise V31PipelineFailure(error_code, safe_message) from None


def _diagnosis_from_v31_pipeline(
    pipeline: V31AiPipelineResult,
    *,
    diagnosis_id: str,
    assessment_ref: AssessmentRefV31,
    element_profile: ElementProfile,
) -> DiagnosisV3:
    response = pipeline.diagnosis
    if response is None or response.status not in {"success", "degraded"}:
        raise V31PipelineFailure("DIAGNOSIS_RESPONSE_INVALID")
    candidates = [
        DiagnosisCandidate(
            candidate_id=f"{diagnosis_id}_c{index}",
            **candidate.model_dump(mode="json"),
        )
        for index, candidate in enumerate(response.candidate_tendencies, start=1)
    ]
    if not candidates:
        raise V31PipelineFailure("DIAGNOSIS_RESPONSE_INVALID")
    rag_refs = [
        KnowledgeReference(title=hit.source_title, summary=hit.display_summary)
        for hit in pipeline.rag_result.hits
    ]
    root = {
        "schema_version": "diagnosis_v3.0",
        "agent_id": "diagnosis_agent",
        "diagnosis_id": diagnosis_id,
        "assessment_ref": {
            "assessment_id": assessment_ref.assessment_id,
            "revision": assessment_ref.revision,
        },
        "rag_result_ref": pipeline.rag_result.retrieval_id,
        "execution_versions": ExecutionVersions(
            prompt_version=pipeline.diagnosis_request.prompt_version,
            response_schema_version=pipeline.diagnosis_request.response_schema_version,
            knowledge_version=pipeline.rag_result.knowledge_version,
            mapping_version=pipeline.tone_profile.mapping_version,
        ),
        "degradation": Degradation(
            active=response.status == "degraded",
            reason_codes=["DIAGNOSIS_DEGRADED"] if response.status == "degraded" else [],
        ),
        "presentation": DiagnosisPresentation(
            title="辨证分析",
            primary_tendency=candidates[0].display_name,
            basis_summaries=[item.reasoning_summary for item in candidates],
            knowledge_references=rag_refs,
            disclaimer="本结果不构成医学诊断或治疗建议。",
        ),
        "status": response.status,
        "abstained": False,
        "abstain_reason": None,
        "candidate_tendencies": [item.model_dump(mode="json") for item in candidates],
        "primary_tendency_id": candidates[0].candidate_id,
        "element_profile": element_profile,
    }
    try:
        return DiagnosisV3.model_validate(root)
    except (TypeError, ValueError) as error:
        raise V31PipelineFailure("DIAGNOSIS_RESPONSE_INVALID") from error


def _persist_diagnosis(
    db: Session,
    *,
    principal: AuthPrincipal,
    session_row: SessionModel,
    assessment_ref: AssessmentRefV31,
    result: DiagnosisV3,
    record,
    evidence_rows: list[FactEvidenceRow] | None = None,
    pipeline: V31AiPipelineResult | None = None,
) -> None:
    root = result.root
    run = db.get(DiagnosisRun, root.diagnosis_id)
    if run is None:
        run = DiagnosisRun(
            diagnosis_id=root.diagnosis_id,
            internal_user_pk=principal.internal_user_pk,
            session_row_id=session_row.id,
            assessment_id=assessment_ref.assessment_id,
            assessment_revision=assessment_ref.revision,
            provider_run_id=None,
            rag_run_id=None,
        )
        db.add(run)
    run.status = root.status
    run.abstained = 1 if root.abstained else 0
    run.abstain_reason = root.abstain_reason
    run.primary_tendency_id = root.primary_tendency_id
    run.element_profile_json = root.element_profile.model_dump(mode="json")
    run.degradation_json = root.degradation.model_dump(mode="json")
    run.presentation_json = root.presentation.model_dump(mode="json")
    db.flush()
    if pipeline is not None:
        run.rag_run_id, run.provider_run_id = _persist_pipeline_audit(
            db,
            diagnosis_id=root.diagnosis_id,
            pipeline=pipeline,
        )
        db.flush()
    fact_by_id = {row.fact_evidence_id: row for row in (evidence_rows or [])}
    for rank, candidate in enumerate(root.candidate_tendencies, start=1):
        db.add(
            DiagnosisCandidateRow(
                candidate_id=candidate.candidate_id,
                diagnosis_id=root.diagnosis_id,
                syndrome_code=candidate.syndrome_code,
                display_name=candidate.display_name,
                relative_support=candidate.relative_support,
                reasoning_summary=candidate.reasoning_summary,
                rank=rank,
            )
        )
        for direction, fact_ids in (
            ("supporting", candidate.supporting_fact_ids),
            ("contradicting", candidate.contradicting_fact_ids),
        ):
            for fact_id in fact_ids:
                fact_row = fact_by_id.get(fact_id)
                if fact_row is not None:
                    db.add(
                        DiagnosisCandidateEvidence(
                            candidate_id=candidate.candidate_id,
                            fact_evidence_row_id=fact_row.fact_evidence_row_id,
                            direction=direction,
                        )
                    )
    record.resource_type = "diagnosis"
    record.resource_id = root.diagnosis_id
    record.status = "succeeded"
    record.response_code = 201
    record.response_json = result.model_dump_json()
    db.commit()


def _persist_pipeline_audit(
    db: Session,
    *,
    diagnosis_id: str,
    pipeline: V31AiPipelineResult | V31PipelineAuditContext,
) -> tuple[str, str]:
    """Persist safe RAG/provider audit rows and return their linked IDs.

    The audit chain keeps versions, hashes, public summaries and stable chunk
    references. It never stores credentials, full prompts, user source text,
    or complete embedding vectors.
    """

    if isinstance(pipeline, V31PipelineAuditContext):
        audit = pipeline
    elif pipeline.audit_context is not None:
        audit = pipeline.audit_context
    else:
        audit = V31PipelineAuditContext(
            query=pipeline.query,
            rag_result=pipeline.rag_result,
            diagnosis_request=pipeline.diagnosis_request,
            diagnosis_execution=pipeline.diagnosis_execution,
            rag_manifest=pipeline.rag_manifest,
            rag_chunk_checksums=pipeline.rag_chunk_checksums,
            mapping_version=pipeline.tone_profile.mapping_version,
        )

    manifest = audit.rag_manifest
    if manifest is None:
        raise V31ReadinessError("RAG_MANIFEST_NOT_READY")
    manifest_checksum = str(getattr(manifest, "manifest_checksum", ""))
    manifest_id = f"km_{sha256(manifest_checksum.encode('utf-8')).hexdigest()[:48]}"
    manifest_row = (
        db.query(KnowledgeManifest)
        .filter(KnowledgeManifest.manifest_checksum == manifest_checksum)
        .one_or_none()
    )
    if manifest_row is None:
        manifest_row = KnowledgeManifest(
            knowledge_manifest_id=manifest_id,
            knowledge_version=str(manifest.knowledge_version),
            embedding_provider=str(manifest.embedding_provider),
            embedding_model=str(manifest.embedding_model),
            embedding_version=str(manifest.embedding_version),
            distance_metric=str(manifest.distance_metric),
            score_semantics=str(manifest.retrieval_score_semantics),
            minimum_score=float(manifest.minimum_score),
            chunk_count=int(manifest.chunk_count),
            manifest_checksum=manifest_checksum,
            review_status="approved",
            medical_review_version=(
                audit.diagnosis_execution.medical_rule_version or "unknown"
            ),
        )
        db.add(manifest_row)
        db.flush()
    elif manifest_row.knowledge_manifest_id != manifest_id:
        raise V31ReadinessError("RAG_MANIFEST_ID_MISMATCH")

    rag_run_id = audit.rag_result.retrieval_id
    db.add(
        RagRetrievalRun(
            rag_run_id=rag_run_id,
            diagnosis_id=diagnosis_id,
            query_hash=_request_hash(audit.query.model_dump(mode="json")),
            query_builder_version="diagnosis_query_v3.1",
            knowledge_manifest_id=manifest_row.knowledge_manifest_id,
            knowledge_version=audit.rag_result.knowledge_version,
            manifest_checksum=manifest_checksum,
            embedding_version=audit.rag_result.embedding_version,
            distance_metric=str(manifest.distance_metric),
            score_semantics=audit.rag_result.retrieval_score_semantics,
            status=audit.rag_result.status,
            top_k=audit.query.top_k,
            minimum_score=float(manifest.minimum_score),
            degradation_json=audit.rag_result.degradation.model_dump(mode="json"),
        )
    )
    chunk_checksums = audit.rag_chunk_checksums
    for hit in audit.rag_result.hits:
        chunk_checksum = chunk_checksums.get(hit.chunk_id) or _request_hash(
            {"chunk_id": hit.chunk_id, "text": hit.text}
        )
        db.add(
            RagRetrievalHit(
                rag_run_id=rag_run_id,
                chunk_id=hit.chunk_id,
                source_id=hit.source_id,
                source_title=hit.source_title,
                section=hit.section,
                retrieval_score=float(hit.retrieval_score),
                display_summary=hit.display_summary,
                text_ciphertext=_request_hash({"text": hit.text}),
                review_status=hit.review_status,
                knowledge_version=audit.rag_result.knowledge_version,
                chunk_content_checksum=chunk_checksum,
            )
        )

    execution = audit.diagnosis_execution
    db.add(
        AiProviderRun(
            provider_run_id=execution.provider_run_id,
            purpose="diagnosis",
            resource_id=diagnosis_id,
            provider=execution.provider_name,
            model=execution.provider_model,
            prompt_version=audit.diagnosis_request.prompt_version,
            response_schema_version=audit.diagnosis_request.response_schema_version,
            status=execution.status,
            error_code=execution.reason_code,
            attempts=max(1, execution.attempts),
            latency_ms=max(0, execution.latency_ms),
            input_tokens=None,
            output_tokens=None,
            request_hash=execution.request_hash,
            response_hash=execution.response_hash,
            knowledge_version=audit.rag_result.knowledge_version,
            mapping_version=audit.mapping_version,
        )
    )
    return rag_run_id, execution.provider_run_id


def _persist_failed_pipeline_audit(
    db: Session,
    *,
    principal: AuthPrincipal,
    session_row: SessionModel,
    assessment_ref: AssessmentRefV31,
    diagnosis_id: str,
    element_profile: ElementProfile,
    audit: V31PipelineAuditContext,
) -> None:
    """Commit a failed/abstained Agent2 attempt without a public result."""

    execution = audit.diagnosis_execution
    abstained = execution.status == "abstained"
    status = "abstained" if abstained else "failed"
    reason_code = execution.reason_code if abstained else None
    run = DiagnosisRun(
        diagnosis_id=diagnosis_id,
        internal_user_pk=principal.internal_user_pk,
        session_row_id=session_row.id,
        assessment_id=assessment_ref.assessment_id,
        assessment_revision=assessment_ref.revision,
        status=status,
        abstained=1 if abstained else 0,
        abstain_reason=reason_code,
        primary_tendency_id=None,
        element_profile_json=element_profile.model_dump(mode="json"),
        degradation_json=Degradation(
            active=True,
            reason_codes=[execution.reason_code] if execution.reason_code else [],
        ).model_dump(mode="json"),
        presentation_json={
            "title": "辨证分析",
            "primary_tendency": None,
            "basis_summaries": ["当前请求未生成可展示的辨证结果。"],
            "knowledge_references": [],
            "disclaimer": "本结果不构成医学诊断或治疗建议。",
        },
        provider_run_id=None,
        rag_run_id=None,
    )
    db.add(run)
    db.flush()
    run.rag_run_id, run.provider_run_id = _persist_pipeline_audit(
        db,
        diagnosis_id=diagnosis_id,
        pipeline=audit,
    )
    db.commit()


def run_diagnosis(
    db: Session,
    principal: AuthPrincipal,
    request: DiagnosisV31Input,
    *,
    idempotency_key: str,
) -> tuple[DiagnosisV3, bool]:
    request_hash = _request_hash(request.model_dump(mode="json"))
    record, replayed = reserve_v3_idempotency(
        db,
        internal_user_pk=principal.internal_user_pk,
        operation=_OPERATION,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )
    if replayed:
        return DiagnosisV3.model_validate_json(record.response_json), True

    ref: AssessmentRefV31 = request.assessment_ref
    owned_input = (
        db.query(AssessmentV3, AssessmentRevisionV3, SessionModel)
        .join(SessionModel, AssessmentV3.session_row_id == SessionModel.id)
        .join(
            AssessmentRevisionV3,
            (AssessmentRevisionV3.assessment_id == AssessmentV3.assessment_id)
            & (AssessmentRevisionV3.revision == ref.revision),
        )
        .filter(
            AssessmentV3.assessment_id == ref.assessment_id,
            AssessmentV3.internal_user_pk == principal.internal_user_pk,
            SessionModel.user_id == principal.internal_user_pk,
            SessionModel.session_id == request.session_id,
            SessionModel.input_revision == ref.input_revision,
            AssessmentV3.current_revision == ref.revision,
            AssessmentV3.input_revision == ref.input_revision,
            AssessmentRevisionV3.input_revision == ref.input_revision,
            AssessmentV3.status == "confirmed",
            AssessmentRevisionV3.status == "confirmed",
            AssessmentRevisionV3.confirmation_status == "confirmed",
            AssessmentV3.flow_contract_version == "v3-owner-flow-1",
            AssessmentV3.safety_policy == "deferred_v3",
            AssessmentV3.safety_status.is_(None),
            AssessmentV3.safety_evaluation_status == "not_run",
        )
        .one_or_none()
    )
    if owned_input is None:
        raise OwnedResourceNotFound
    _assessment, assessment_revision, session_row = owned_input

    element_profile = _element_profile_from_organ(
        assessment_revision.organ_profile_json
    )
    diagnosis_id = f"diag_{uuid.uuid4().hex}"
    rag_degraded = Degradation(
        active=True,
        reason_codes=["RAG_INGESTION_NOT_APPROVED"],
    )

    if element_profile.status == "insufficient":
        # Honest abstain: element evidence is insufficient.
        result = DiagnosisV3(
            root=AbstainedDiagnosis(
                schema_version="diagnosis_v3.0",
                agent_id="diagnosis_agent",
                diagnosis_id=diagnosis_id,
                assessment_ref={
                    "assessment_id": ref.assessment_id,
                    "revision": ref.revision,
                },
                rag_result_ref=None,
                execution_versions=ExecutionVersions(
                    prompt_version="diagnosis_v3.0",
                    response_schema_version="diagnosis_provider_response_v3.0",
                    knowledge_version="medical_v3.0",
                    mapping_version="organ_mapping_v3.0",
                ),
                degradation=rag_degraded,
                presentation=DiagnosisPresentation(
                    title="辨证分析",
                    primary_tendency=None,
                    basis_summaries=[
                        "当前证据不足以形成证型倾向。",
                        "RAG 知识索引尚未获得医学批准，未检索到引用。",
                    ],
                    knowledge_references=[],
                    disclaimer="本结果不构成医学诊断或治疗建议。",
                ),
                status="abstained",
                abstained=True,
                abstain_reason="ELEMENT_EVIDENCE_INSUFFICIENT",
                candidate_tendencies=[],
                primary_tendency_id=None,
                element_profile=element_profile,
            )
        )
        status = "abstained"
    elif _v31_real_mode():
        try:
            pipeline = _run_v31_pipeline(
                db,
                request=request,
                assessment=_assessment,
                assessment_revision=assessment_revision,
                session_row=session_row,
            )
        except V31PipelineFailure as error:
            if error.audit_context is not None:
                _persist_failed_pipeline_audit(
                    db,
                    principal=principal,
                    session_row=session_row,
                    assessment_ref=ref,
                    diagnosis_id=diagnosis_id,
                    element_profile=element_profile,
                    audit=error.audit_context,
                )
            raise
        result = _diagnosis_from_v31_pipeline(
            pipeline,
            diagnosis_id=diagnosis_id,
            assessment_ref=ref,
            element_profile=element_profile,
        )
        evidence_rows = (
            db.query(FactEvidenceRow)
            .filter(
                FactEvidenceRow.assessment_id == ref.assessment_id,
                FactEvidenceRow.assessment_revision == ref.revision,
                FactEvidenceRow.confirmation_status == "confirmed",
            )
            .all()
        )
        _persist_diagnosis(
            db,
            principal=principal,
            session_row=session_row,
            assessment_ref=ref,
            result=result,
            record=record,
            evidence_rows=evidence_rows,
            pipeline=pipeline,
        )
        return result, False
    else:
        # Element evidence is available but no approved syndrome whitelist /
        # production RAG exists: fabricating syndromes is forbidden.
        raise MedicalAssetUnavailable

    db.add(
        DiagnosisRun(
            diagnosis_id=diagnosis_id,
            internal_user_pk=principal.internal_user_pk,
            session_row_id=session_row.id,
            assessment_id=ref.assessment_id,
            assessment_revision=ref.revision,
            status=status,
            abstained=1 if status == "abstained" else 0,
            abstain_reason="ELEMENT_EVIDENCE_INSUFFICIENT"
            if status == "abstained"
            else None,
            primary_tendency_id=None,
            element_profile_json=element_profile.model_dump(mode="json"),
            degradation_json=rag_degraded.model_dump(mode="json"),
            presentation_json=result.root.presentation.model_dump(mode="json"),
            provider_run_id=None,
            rag_run_id=None,
        )
    )
    record.resource_type = "diagnosis"
    record.resource_id = diagnosis_id
    record.status = "succeeded"
    record.response_code = 201
    record.response_json = result.model_dump_json()
    db.commit()
    return result, False
