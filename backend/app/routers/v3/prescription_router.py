"""Agent 3 (Prescription) endpoints (Issue #110 closeout)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.routers.v3.transport import V3APIError, v3_success
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.envelope import V3SuccessEnvelope
from backend.app.schemas.v3.prescription import PrescriptionV31Request, PrescriptionV3
from backend.app.services.v3.auth_service import get_current_v3_principal
from backend.app.services.v3.idempotency import (
    IdempotencyConflict,
    IdempotencyInProgress,
)
from backend.app.services.v3.prescription_service import (
    DiagnosisNotReady,
    InvalidSpec,
    OwnedResourceNotFound,
    PreferenceSnapshotConflict,
    create_prescription,
    get_prescription,
)


router = APIRouter()


@router.post(
    "/prescriptions",
    response_model=V3SuccessEnvelope[PrescriptionV3],
    status_code=201,
)
def create_prescription_endpoint(
    response: Response,
    body: PrescriptionV31Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[PrescriptionV3]:
    if idempotency_key is None or not idempotency_key.strip():
        raise V3APIError(
            400,
            "IDEMPOTENCY_KEY_REQUIRED",
            "需要提供幂等键后才能创建处方。",
        )
    try:
        result, replayed = create_prescription(
            db,
            principal,
            body,
            idempotency_key=idempotency_key.strip(),
        )
    except OwnedResourceNotFound:
        raise V3APIError(404, "RESOURCE_NOT_FOUND", "未找到对应诊断。") from None
    except DiagnosisNotReady:
        raise V3APIError(
            409, "DIAGNOSIS_NOT_READY", "诊断尚未完成，无法生成处方。"
        ) from None
    except PreferenceSnapshotConflict:
        raise V3APIError(
            409,
            "PREFERENCE_SNAPSHOT_CONFLICT",
            "偏好快照与服务端不一致，请刷新后重试。",
        ) from None
    except InvalidSpec as error:
        raise V3APIError(422, error.code, error.message) from None
    except IdempotencyConflict:
        raise V3APIError(
            422, "IDEMPOTENCY_KEY_REUSED", "相同的幂等键已被不同的请求使用。"
        ) from None
    except IdempotencyInProgress:
        raise V3APIError(
            409, "IDEMPOTENCY_IN_PROGRESS", "相同请求正在处理中，请稍后重试。"
        ) from None
    if replayed:
        response.status_code = 200
    return v3_success(result)


@router.get(
    "/prescriptions/{prescription_id}",
    response_model=V3SuccessEnvelope[PrescriptionV3],
)
def get_prescription_endpoint(
    prescription_id: str,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[PrescriptionV3]:
    try:
        return v3_success(get_prescription(db, principal, prescription_id))
    except OwnedResourceNotFound:
        raise V3APIError(404, "RESOURCE_NOT_FOUND", "未找到对应处方。") from None
