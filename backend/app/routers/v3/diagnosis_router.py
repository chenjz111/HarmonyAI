"""V3 Agent 2 Diagnosis endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.routers.v3.transport import V3APIError, v3_success
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.diagnosis import DiagnosisV3, DiagnosisV31Input
from backend.app.schemas.v3.envelope import V3SuccessEnvelope
from backend.app.services.v3.auth_service import get_current_v3_principal
from backend.app.services.v3.diagnosis_service import (
    IdempotencyConflict,
    MedicalAssetUnavailable,
    OwnedResourceNotFound,
    run_diagnosis,
)


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
    except MedicalAssetUnavailable:
        raise V3APIError(
            503,
            "MEDICAL_ASSET_UNAVAILABLE",
            "辨证所需的医学知识资产尚未批准，暂不能输出证型倾向。",
            retryable=False,
        ) from None
    if replayed:
        response.status_code = 200
    return v3_success(result)
