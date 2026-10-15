"""V3 Agent 2 Diagnosis endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models import Session as SessionModel
from backend.app.models.v3.diagnosis import DiagnosisRun
from backend.app.routers.v3.transport import V3APIError, v3_success
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.diagnosis import DiagnosisV3, DiagnosisV31Input
from backend.app.schemas.v3.envelope import V3SuccessEnvelope
from backend.app.schemas.v3.flow_v31 import FiveToneAnalysisReadModel, FiveToneAnalysisReadModelV33
from backend.app.services.v3.auth_service import get_current_v3_principal
from backend.app.services.v3.diagnosis_service import (
    IdempotencyConflict,
    IdempotencyFailureReplay,
    IdempotencyInProgress,
    MedicalAssetUnavailable,
    OwnedResourceNotFound,
    V31PipelineFailure,
    V31ReadinessError,
    run_diagnosis,
)
from backend.app.services.v3.internal_agent3_service import Agent3NotReady, load_current_five_tone_read_model


router = APIRouter()


@router.post(
    "/diagnoses",
    response_model=V3SuccessEnvelope[DiagnosisV3],
    status_code=201,
)
def create_run(
    response: Response,
    body: DiagnosisV31Input,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[DiagnosisV3]:
    if idempotency_key is None or not idempotency_key.strip():
        raise V3APIError(
            400,
            "IDEMPOTENCY_KEY_REQUIRED",
            "需要提供幂等键后才能创建辨证。",
        )
    try:
        result, replayed = run_diagnosis(
            db,
            principal,
            body,
            idempotency_key=idempotency_key.strip(),
        )
    except OwnedResourceNotFound:
        raise V3APIError(404, "RESOURCE_NOT_FOUND", "未找到对应资源。") from None
    except IdempotencyConflict:
        raise V3APIError(
            422,
            "IDEMPOTENCY_KEY_REUSED",
            "相同的幂等键已被不同的请求使用。",
        ) from None
    except IdempotencyInProgress:
        raise V3APIError(
            409,
            "IDEMPOTENCY_IN_PROGRESS",
            "相同幂等键的请求仍在处理中，请稍后重试。",
            retryable=True,
        ) from None
    except IdempotencyFailureReplay as error:
        raise V3APIError(
            error.status_code,
            error.code,
            error.message,
            retryable=error.retryable,
            next_actions=error.next_actions,
            request_id=error.request_id,
        ) from None
    except MedicalAssetUnavailable as error:
        raise V3APIError(
            503,
            "MEDICAL_ASSET_UNAVAILABLE",
            "辨证所需的医学知识资产尚未批准，暂不能输出证型倾向。",
            retryable=False,
            request_id=getattr(error, "request_id", None),
        ) from None
    except V31ReadinessError as error:
        raise V3APIError(
            503,
            error.error_code,
            error.safe_message,
            retryable=False,
            request_id=error.request_id,
        ) from None
    except V31PipelineFailure as error:
        raise V3APIError(
            502,
            error.error_code,
            error.safe_message,
            retryable=error.retryable,
            request_id=error.request_id,
        ) from None
    if replayed:
        response.status_code = 200
    return v3_success(result)


@router.get(
    "/diagnoses/{diagnosis_id}/five-tone-analysis",
    response_model=V3SuccessEnvelope[FiveToneAnalysisReadModel | FiveToneAnalysisReadModelV33],
)
def get_five_tone_analysis(
    diagnosis_id: str,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[FiveToneAnalysisReadModel | FiveToneAnalysisReadModelV33]:
    """Read the checksum-verified persisted Agent 3 model for Player.

    This route is deliberately read-only: it only loads the existing diagnosis
    row and its current assessment/session snapshot. It never creates or
    recomputes diagnosis, prescription, RAG, or provider work.
    """

    diagnosis = (
        db.query(DiagnosisRun)
        .filter(
            DiagnosisRun.diagnosis_id == diagnosis_id,
            DiagnosisRun.internal_user_pk == principal.internal_user_pk,
        )
        .one_or_none()
    )
    if diagnosis is None:
        raise V3APIError(404, "RESOURCE_NOT_FOUND", "未找到对应诊断。")
    session_row = db.get(SessionModel, diagnosis.session_row_id)
    if session_row is None or session_row.user_id != principal.internal_user_pk:
        raise V3APIError(404, "RESOURCE_NOT_FOUND", "未找到对应诊断。")
    try:
        read_model = load_current_five_tone_read_model(db, diagnosis, session_row)
    except Agent3NotReady as error:
        raise V3APIError(409, error.code, error.message) from None
    return v3_success(read_model)
