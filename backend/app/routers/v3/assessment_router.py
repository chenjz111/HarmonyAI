"""V3 Agent 1 Assessment endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.routers.v3.transport import V3APIError, v3_success
from backend.app.schemas.v3.assessment import AssessmentV31Request, AssessmentV31Response
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.envelope import V3SuccessEnvelope
from backend.app.services.v3.assessment_service import (
    AssessmentInputNotReady,
    InputRevisionConflict,
    OwnedResourceNotFound,
    create_assessment,
)
from backend.app.services.v3.auth_service import get_current_v3_principal


router = APIRouter()


@router.post(
    "/assessments",
    response_model=V3SuccessEnvelope[AssessmentV31Response],
    status_code=201,
)
def create_run(
    response: Response,
    body: AssessmentV31Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[AssessmentV31Response]:
    if idempotency_key is None or not idempotency_key.strip():
        raise V3APIError(
            400,
            "IDEMPOTENCY_KEY_REQUIRED",
            "需要提供幂等键后才能创建评估。",
        )
    try:
        result, replayed = create_assessment(
            db,
            principal,
            body,
            idempotency_key=idempotency_key.strip(),
        )
    except OwnedResourceNotFound:
        raise V3APIError(404, "RESOURCE_NOT_FOUND", "未找到对应资源。") from None
    except InputRevisionConflict:
        raise V3APIError(
            409,
            "INPUT_REVISION_CONFLICT",
            "输入版本已变化，请刷新后重试。",
        ) from None
    except AssessmentInputNotReady:
        raise V3APIError(
            409,
            "ASSESSMENT_INPUT_NOT_READY",
            "评估输入尚未就绪：请先确认资料摘要或提交完整问卷。",
        ) from None
    if replayed:
        response.status_code = 200
    return v3_success(result)
