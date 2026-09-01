"""Agent 2 — Diagnosis V3.

Pipeline: Assessment -> Query Builder -> RAG Retriever -> Qwen ->
Schema Validation -> Medical Rule Check -> Diagnosis Output.

Per the approved knowledge manifest, production RAG ingestion (embedding
index) is NOT yet approved, so the retriever returns an honest
degraded/empty result and never fake hits. Syndrome candidates may only
come from an approved syndrome whitelist; with no approved whitelist the
diagnosis abstains (insufficient element profile) or reports the medical
asset as unavailable instead of fabricating syndromes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import uuid

from sqlalchemy.orm import Session

from backend.app.models import Session as SessionModel
from backend.app.models.v3.assessment import AssessmentRevisionV3
from backend.app.models.v3.diagnosis import (
    DiagnosisCandidateEvidence,
    DiagnosisCandidate as DiagnosisCandidateRow,
    DiagnosisRun,
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
)
from backend.app.services.v3.knowledge_assets import load_organ_mapping


class OwnedResourceNotFound(RuntimeError):
    pass


class InputRevisionConflict(RuntimeError):
    pass


class MedicalAssetUnavailable(RuntimeError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


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


def run_diagnosis(
    db: Session,
    principal: AuthPrincipal,
    request: DiagnosisV31Input,
    *,
    idempotency_key: str,
) -> tuple[DiagnosisV3, bool]:
    del idempotency_key
    ref: AssessmentRefV31 = request.assessment_ref
    if ref.confirmation_status != "confirmed":
        raise OwnedResourceNotFound
    if ref.safety_policy != "deferred_v3" or ref.safety_status is not None:
        raise OwnedResourceNotFound

    session_row = (
        db.query(SessionModel)
        .filter(
            SessionModel.user_id == principal.internal_user_pk,
            SessionModel.input_revision == ref.input_revision,
        )
        .first()
    )
    if session_row is None:
        raise InputRevisionConflict

    assessment_revision = (
        db.query(AssessmentRevisionV3)
        .filter(
            AssessmentRevisionV3.assessment_id == ref.assessment_id,
            AssessmentRevisionV3.revision == ref.revision,
        )
        .one_or_none()
    )
    if assessment_revision is None:
        raise OwnedResourceNotFound

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
    db.commit()
    return result, False
