"""V3.1 document-set endpoints (Issue #99 step 2)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.routers.v3.transport import V3APIError, v3_success
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.document import DocumentSetReadModel, DocumentSetReplaceRequest
from backend.app.schemas.v3.envelope import V3SuccessEnvelope
from backend.app.services.v3.auth_service import get_current_v3_principal
from backend.app.services.v3.document_set_service import (
    FlowContractMismatch,
    IdempotencyConflict,
    InputRevisionConflict,
    InvalidDocumentSet,
    OwnedResourceNotFound,
    get_active_document_set,
    replace_document_set,
)


router = APIRouter()


@router.post(
    "/sessions/{session_id}/document-sets",
    response_model=V3SuccessEnvelope[DocumentSetReadModel],
    status_code=201,
)
def replace_document_set_endpoint(
    response: Response,
    session_id: str,
    body: DocumentSetReplaceRequest,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[DocumentSetReadModel]:
    if idempotency_key is None or not idempotency_key.strip():
        raise V3APIError(
            400,
            "IDEMPOTENCY_KEY_REQUIRED",
            "需要提供幂等键后才能替换资料。",
        )
    try:
        result, replayed = replace_document_set(
            db,
            principal,
            session_id,
            body.document_ids,
            body.expected_input_revision,
            idempotency_key.strip(),
        )
    except OwnedResourceNotFound:
        raise V3APIError(404, "RESOURCE_NOT_FOUND", "未找到对应资源。") from None
    except FlowContractMismatch:
        raise V3APIError(
            409, "FLOW_CONTRACT_MISMATCH", "该会话不支持多资料。"
        ) from None
    except InputRevisionConflict:
        raise V3APIError(
            409, "INPUT_REVISION_CONFLICT", "输入状态已更新，请基于最新版本重试。"
        ) from None
    except IdempotencyConflict:
        raise V3APIError(
            422, "IDEMPOTENCY_KEY_REUSED", "相同的幂等键已被不同的请求使用。"
        ) from None
    except InvalidDocumentSet as error:
        raise V3APIError(422, error.code, error.message) from None
    if replayed:
        response.status_code = 200
    return v3_success(DocumentSetReadModel.model_validate(result))


@router.get(
    "/sessions/{session_id}/document-sets/active",
    response_model=V3SuccessEnvelope[DocumentSetReadModel],
)
def get_active_document_set_endpoint(
    session_id: str,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[DocumentSetReadModel]:
    try:
        result = get_active_document_set(db, principal, session_id)
    except OwnedResourceNotFound:
        raise V3APIError(404, "RESOURCE_NOT_FOUND", "未找到活动资料集。") from None
    return v3_success(DocumentSetReadModel.model_validate(result))
