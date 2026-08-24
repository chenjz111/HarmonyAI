"""V3 authenticated session endpoints."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, Response
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.routers.v3.transport import V3APIError, v3_success
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.envelope import V3SuccessEnvelope
from backend.app.schemas.v3.session import EntryReadModel
from backend.app.services.v3.auth_service import get_current_v3_principal
from backend.app.services.v3.session_service import (
    IdempotencyConflict,
    OwnedResourceNotFound,
    create_v3_session,
    get_owned_v3_session,
)


router = APIRouter()


@router.post(
    "/sessions",
    response_model=V3SuccessEnvelope[EntryReadModel],
    status_code=201,
)
def create_session(
    response: Response,
    body: Annotated[dict[str, object] | None, Body()] = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[EntryReadModel]:
    if idempotency_key is None or not idempotency_key.strip():
        raise V3APIError(
            400,
            "IDEMPOTENCY_KEY_REQUIRED",
            "需要提供幂等键后才能创建会话。",
        )
    normalized_key = idempotency_key.strip()
    if len(normalized_key) > 128:
        raise V3APIError(400, "IDEMPOTENCY_KEY_INVALID", "幂等键格式无效。")
    incoming = body or {}
    unexpected = set(incoming) - {"user_id"}
    if unexpected:
        raise V3APIError(422, "INVALID_ENTRY_REQUEST", "入口请求包含未知字段。")
    try:
        result, replayed = create_v3_session(
            db,
            principal,
            idempotency_key=normalized_key,
            payload={},
        )
    except IdempotencyConflict:
        raise V3APIError(
            409,
            "IDEMPOTENCY_KEY_REUSED",
            "该幂等键已用于不同请求。",
        ) from None
    if replayed:
        response.status_code = 200
    return v3_success(result)


@router.get(
    "/sessions/{session_id}",
    response_model=V3SuccessEnvelope[EntryReadModel],
)
def get_session(
    session_id: str,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[EntryReadModel]:
    try:
        return v3_success(get_owned_v3_session(db, principal, session_id))
    except OwnedResourceNotFound:
        raise V3APIError(404, "RESOURCE_NOT_FOUND", "未找到对应资源。") from None