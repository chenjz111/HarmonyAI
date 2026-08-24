"""V3 understanding ingestion, read model and confirmation endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.routers.v3.transport import V3APIError, v3_success
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.envelope import V3SuccessEnvelope
from backend.app.schemas.v3.understanding import (
    UnderstandingConfirmationRequest,
    UnderstandingRevisionResult,
    UnderstandingV3Request,
    UnderstandingV3Response,
)
from backend.app.services.v3.auth_service import get_current_v3_principal
from backend.app.services.v3.understanding_service import (
    IdempotencyConflict,
    InvalidChange,
    OwnedResourceNotFound,
    RevisionConflict,
    confirm_understanding,
    create_understanding,
    get_understanding,
)


router = APIRouter()


def _not_found() -> V3APIError:
    return V3APIError(404, "RESOURCE_NOT_FOUND", "未找到对应资源。")


@router.post(
    "/understandings",
    response_model=V3SuccessEnvelope[UnderstandingV3Response],
    status_code=201,
)
def create_run(
    response: Response,
    body: UnderstandingV3Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[UnderstandingV3Response]:
    if idempotency_key is None or not idempotency_key.strip():
        raise V3APIError(
            400,
            "IDEMPOTENCY_KEY_REQUIRED",
            "需要提供幂等键后才能创建理解。",
        )
    try:
        result, replayed = create_understanding(
            db,
            principal,
            body,
            idempotency_key.strip(),
        )
    except OwnedResourceNotFound:
        raise _not_found() from None
    except IdempotencyConflict:
        raise V3APIError(
            422,
            "IDEMPOTENCY_KEY_REUSED",
            "相同的幂等键已被不同的请求使用。",
        ) from None
    if replayed:
        response.status_code = 200
    return v3_success(result)


@router.get(
    "/understandings/{understanding_id}",
    response_model=V3SuccessEnvelope[UnderstandingV3Response],
)
def read_run(
    understanding_id: str,
    revision: int | None = None,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[UnderstandingV3Response]:
    try:
        return v3_success(
            get_understanding(db, principal, understanding_id, revision=revision)
        )
    except OwnedResourceNotFound:
        raise _not_found() from None


@router.post(
    "/understandings/{understanding_id}/confirmations",
    response_model=V3SuccessEnvelope[UnderstandingRevisionResult],
    status_code=201,
)
def confirm_run(
    response: Response,
    understanding_id: str,
    body: UnderstandingConfirmationRequest,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[UnderstandingRevisionResult]:
    if idempotency_key is None or not idempotency_key.strip():
        raise V3APIError(
            400,
            "IDEMPOTENCY_KEY_REQUIRED",
            "需要提供幂等键后才能确认理解。",
        )
    try:
        result, replayed = confirm_understanding(
            db,
            principal,
            understanding_id,
            body,
            idempotency_key.strip(),
        )
    except OwnedResourceNotFound:
        raise _not_found() from None
    except RevisionConflict:
        raise V3APIError(
            409,
            "REVISION_CONFLICT",
            "理解状态已更新，请基于最新版本重试。",
        ) from None
    except IdempotencyConflict:
        raise V3APIError(
            422,
            "IDEMPOTENCY_KEY_REUSED",
            "相同的幂等键已被不同的请求使用。",
        ) from None
    except InvalidChange as error:
        raise V3APIError(422, error.code, error.message) from None
    if replayed:
        response.status_code = 200
    return v3_success(result)
