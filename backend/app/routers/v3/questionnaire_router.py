"""V3.1 questionnaire submission endpoint (Issue #99)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.routers.v3.transport import V3APIError, v3_success
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.envelope import V3SuccessEnvelope
from backend.app.schemas.v3.questionnaire import (
    QuestionnaireSubmissionRequest,
    QuestionnaireSubmissionResponse,
)
from backend.app.services.v3.auth_service import get_current_v3_principal
from backend.app.services.v3.questionnaire_service import (
    FlowContractMismatch,
    IdempotencyConflict,
    InputRevisionConflict,
    InvalidQuestionnaire,
    OwnedResourceNotFound,
    submit_questionnaire,
)


router = APIRouter()


@router.post(
    "/sessions/{session_id}/questionnaire",
    response_model=V3SuccessEnvelope[QuestionnaireSubmissionResponse],
    status_code=201,
)
def submit_questionnaire_endpoint(
    response: Response,
    session_id: str,
    body: QuestionnaireSubmissionRequest,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[QuestionnaireSubmissionResponse]:
    if idempotency_key is None or not idempotency_key.strip():
        raise V3APIError(
            400,
            "IDEMPOTENCY_KEY_REQUIRED",
            "需要提供幂等键后才能提交问卷。",
        )
    try:
        result, replayed = submit_questionnaire(
            db,
            principal,
            session_id,
            body,
            idempotency_key.strip(),
        )
    except OwnedResourceNotFound:
        raise V3APIError(404, "RESOURCE_NOT_FOUND", "未找到对应资源。") from None
    except FlowContractMismatch:
        raise V3APIError(
            409,
            "FLOW_CONTRACT_MISMATCH",
            "该会话不支持问卷提交。",
        ) from None
    except InputRevisionConflict:
        raise V3APIError(
            409,
            "INPUT_REVISION_CONFLICT",
            "输入状态已更新，请基于最新版本重试。",
        ) from None
    except IdempotencyConflict:
        raise V3APIError(
            422,
            "IDEMPOTENCY_KEY_REUSED",
            "相同的幂等键已被不同的请求使用。",
        ) from None
    except InvalidQuestionnaire as error:
        raise V3APIError(422, error.code, error.message) from None
    if replayed:
        response.status_code = 200
    return v3_success(result)
