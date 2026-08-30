"""V3 authenticated session endpoints."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, Response
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.routers.v3.transport import V3APIError, v3_success
from backend.app.schemas.v3.activity import (
    InputTransitionRequest,
    InputTransitionResult,
    SessionActivityState,
)
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.envelope import V3SuccessEnvelope
from backend.app.schemas.v3.session import EntryReadModel
from backend.app.services.v3.activity_service import (
    DocumentNotOwned,
    FlowContractUnsupported as ActivityFlowContractUnsupported,
    IdempotencyConflict as ActivityIdempotencyConflict,
    InputRevisionConflict,
    OwnedResourceNotFound as ActivityOwnedResourceNotFound,
    TransitionNotAllowed,
    apply_input_transition,
    get_session_activity,
)
from backend.app.services.v3.auth_service import get_current_v3_principal
from backend.app.services.v3.session_service import (
    FlowContractUnsupported,
    IdempotencyConflict,
    OwnedResourceNotFound,
    create_v3_session,
    get_owned_v3_session,
)


router = APIRouter()


def _idempotency_error() -> V3APIError:
    return V3APIError(
        409,
        "IDEMPOTENCY_KEY_REUSED",
        "该幂等键已用于不同请求。",
    )


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
    unexpected = set(incoming) - {"user_id", "flow_contract_version"}
    if unexpected:
        raise V3APIError(422, "INVALID_ENTRY_REQUEST", "入口请求包含未知字段。")
    if "flow_contract_version" in incoming and not isinstance(
        incoming["flow_contract_version"], str
    ):
        raise V3APIError(
            422, "INVALID_FLOW_CONTRACT", "flow_contract_version 必须是字符串。"
        )
    try:
        result, replayed = create_v3_session(
            db,
            principal,
            idempotency_key=normalized_key,
            payload={
                "flow_contract_version": incoming.get("flow_contract_version"),
            },
        )
    except FlowContractUnsupported:
        raise V3APIError(
            409,
            "FLOW_CONTRACT_UNSUPPORTED",
            "当前服务端不支持该流程契约版本。",
        ) from None
    except IdempotencyConflict:
        raise _idempotency_error() from None
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


@router.get(
    "/sessions/{session_id}/activity",
    response_model=V3SuccessEnvelope[SessionActivityState],
)
def get_session_activity_endpoint(
    session_id: str,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[SessionActivityState]:
    try:
        return v3_success(get_session_activity(db, principal, session_id))
    except ActivityOwnedResourceNotFound:
        raise V3APIError(404, "RESOURCE_NOT_FOUND", "未找到对应资源。") from None


@router.post(
    "/sessions/{session_id}/input-transitions",
    response_model=V3SuccessEnvelope[InputTransitionResult],
)
def create_input_transition(
    session_id: str,
    body: InputTransitionRequest,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[InputTransitionResult]:
    if idempotency_key is None or not idempotency_key.strip():
        raise V3APIError(
            400,
            "IDEMPOTENCY_KEY_REQUIRED",
            "需要提供幂等键后才能提交输入转换。",
        )
    normalized_key = idempotency_key.strip()
    if len(normalized_key) > 128:
        raise V3APIError(400, "IDEMPOTENCY_KEY_INVALID", "幂等键格式无效。")
    try:
        result, replayed = apply_input_transition(
            db,
            principal,
            session_id,
            body,
            idempotency_key=normalized_key,
        )
    except ActivityFlowContractUnsupported:
        raise V3APIError(
            409,
            "FLOW_CONTRACT_UNSUPPORTED",
            "该会话未绑定当前流程契约，不能执行输入转换。",
        ) from None
    except InputRevisionConflict:
        raise V3APIError(
            409,
            "INPUT_REVISION_CONFLICT",
            "输入版本已变化，请刷新后重试。",
        ) from None
    except TransitionNotAllowed:
        raise V3APIError(
            409,
            "TRANSITION_NOT_ALLOWED",
            "当前状态下不允许该输入转换。",
        ) from None
    except DocumentNotOwned:
        raise V3APIError(
            404,
            "RESOURCE_NOT_FOUND",
            "未找到对应资料。",
        ) from None
    except ActivityOwnedResourceNotFound:
        raise V3APIError(404, "RESOURCE_NOT_FOUND", "未找到对应资源。") from None
    except ActivityIdempotencyConflict:
        raise _idempotency_error() from None
    return v3_success(result)
