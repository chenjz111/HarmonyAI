"""V3 Understanding endpoints (Owner Flow Amendment 001 §3.2/§4.2)."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from backend.ai_engine.v3.understanding_provider import ProviderFailureV3
from backend.app.core.database import get_db
from backend.app.routers.v3.transport import V3APIError, v3_success
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.envelope import V3SuccessEnvelope
from backend.app.schemas.v3.understanding import (
    UnderstandingV31ConfirmationRequest,
    UnderstandingV31ConfirmationResult,
    UnderstandingV31Request,
    UnderstandingV31Response,
)
from backend.app.services.v3.activity_service import (
    FlowContractUnsupported,
    OwnedResourceNotFound,
)
from backend.app.services.v3.auth_service import get_current_v3_principal
from backend.app.services.v3.understanding_service import (
    ChangeNotAllowed,
    InputRevisionConflict,
    InvalidSourceType,
    MedicalAssetUnavailable,
    NoFactsExtracted,
    RevisionConflict,
    SourceNoValidText,
    SourceNotActive,
    SourceNotOwned,
    SourceNotReady,
    SourceOcrFailed,
    UnderstandingNotFound,
    VoiceTranscriptNotEnabled,
    confirm_understanding_v3_1,
    get_understanding_read_model,
    run_understanding_v31,
)


router = APIRouter()


def _resolve_provider_chain():
    """Production Understanding provider chain.

    Requires an approved claim dictionary / Qwen configuration (Issue #77).
    Until the medical assets are approved this returns ``None`` and the run /
    full-text reprocess endpoints answer MEDICAL_ASSET_UNAVAILABLE instead of
    pretending to understand sources.
    """
    return None


def _provider_error(error: ProviderFailureV3) -> V3APIError:
    if error.error_code == "MEDICAL_ASSET_UNAVAILABLE":
        return V3APIError(
            503,
            "MEDICAL_ASSET_UNAVAILABLE",
            "审核知识版本暂不可用，AI 理解服务未执行。",
            retryable=False,
        )
    return V3APIError(
        503,
        "PROVIDER_UNAVAILABLE",
        error.safe_message,
        retryable=error.retryable,
    )


@router.post(
    "/understandings",
    response_model=V3SuccessEnvelope[UnderstandingV31Response],
    status_code=201,
)
def create_understanding(
    body: Annotated[dict[str, object], Body()],
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[UnderstandingV31Response]:
    schema_version = body.get("schema_version")
    if schema_version != "understanding_v3.1":
        # Legacy v3.0 is preserved for old clients but never auto-migrated;
        # new Owner Flow requests must use the v3.1 discriminator.
        raise V3APIError(
            422,
            "INVALID_SCHEMA_VERSION",
            "新流程仅支持 understanding_v3.1 判别版本。",
        )
    try:
        request = UnderstandingV31Request.model_validate(body)
    except Exception:
        raise V3APIError(
            422,
            "INVALID_UNDERSTANDING_REQUEST",
            "理解请求不符合 understanding_v3.1 契约。",
        ) from None
    try:
        result = run_understanding_v31(
            db,
            principal,
            request,
            _resolve_provider_chain(),
        )
    except OwnedResourceNotFound:
        raise V3APIError(404, "RESOURCE_NOT_FOUND", "未找到对应资源。") from None
    except FlowContractUnsupported:
        raise V3APIError(
            409,
            "FLOW_CONTRACT_UNSUPPORTED",
            "该会话未绑定当前流程契约。",
        ) from None
    except InputRevisionConflict:
        raise V3APIError(
            409,
            "INPUT_REVISION_CONFLICT",
            "输入版本已变化，请刷新后重试。",
        ) from None
    except InvalidSourceType:
        raise V3APIError(
            422,
            "INVALID_SOURCE_TYPE",
            "理解请求仅接受 document、narrative 来源。",
        ) from None
    except SourceNotReady:
        raise V3APIError(
            422,
            "SOURCE_NOT_READY",
            "资料尚未完成处理，请稍后重试。",
        ) from None
    except SourceNotActive:
        raise V3APIError(
            409,
            "SOURCE_NOT_ACTIVE",
            "资料已弃用或被替换，请重新上传。",
        ) from None
    except SourceNotOwned:
        raise V3APIError(
            404,
            "RESOURCE_NOT_FOUND",
            "未找到对应资料。",
        ) from None
    except SourceOcrFailed:
        raise V3APIError(
            422,
            "SOURCE_OCR_FAILED",
            "资料 OCR 结果无效或已降级，请重新上传或改用描述与问卷。",
        ) from None
    except SourceNoValidText:
        raise V3APIError(
            422,
            "SOURCE_NO_VALID_TEXT",
            "资料未能识别出有效文字，请重新上传或改用问卷流程。",
        ) from None
    except VoiceTranscriptNotEnabled:
        raise V3APIError(
            422,
            "VOICE_TRANSCRIPT_NOT_ENABLED",
            "语音转写暂未启用，请使用文字描述或问卷。",
        ) from None
    except NoFactsExtracted:
        raise V3APIError(
            422,
            "NO_FACTS_EXTRACTED",
            "暂时无法从资料生成有效摘要，请重试、重新上传或改用描述与问卷。",
            retryable=True,
            next_actions=["retry", "reupload", "switch_to_narrative_and_questionnaire"],
        ) from None
    except MedicalAssetUnavailable:
        raise V3APIError(
            503,
            "MEDICAL_ASSET_UNAVAILABLE",
            "审核知识版本暂不可用，AI 理解服务未执行。",
            retryable=False,
        ) from None
    except ProviderFailureV3 as error:
        raise _provider_error(error) from None
    return v3_success(result)


@router.get(
    "/understandings/{understanding_id}",
    response_model=V3SuccessEnvelope[UnderstandingV31Response],
)
def get_understanding(
    understanding_id: str,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[UnderstandingV31Response]:
    try:
        return v3_success(
            get_understanding_read_model(db, principal, understanding_id)
        )
    except UnderstandingNotFound:
        raise V3APIError(404, "RESOURCE_NOT_FOUND", "未找到对应资源。") from None


@router.post(
    "/understandings/{understanding_id}/confirmations",
    response_model=V3SuccessEnvelope[UnderstandingV31ConfirmationResult],
)
def confirm_understanding(
    understanding_id: str,
    body: Annotated[dict[str, object], Body()],
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[UnderstandingV31ConfirmationResult]:
    schema_version = body.get("schema_version")
    if schema_version != "understanding_v3.1":
        raise V3APIError(
            422,
            "INVALID_SCHEMA_VERSION",
            "仅支持 understanding_v3.1 判别版本。",
        )
    try:
        request = UnderstandingV31ConfirmationRequest.model_validate(body)
    except Exception:
        raise V3APIError(
            422,
            "INVALID_CONFIRMATION",
            "确认请求不符合 understanding_v3.1 契约。",
        ) from None
    try:
        result = confirm_understanding_v3_1(
            db,
            principal,
            understanding_id,
            request,
            _resolve_provider_chain(),
        )
    except UnderstandingNotFound:
        raise V3APIError(404, "RESOURCE_NOT_FOUND", "未找到对应资源。") from None
    except FlowContractUnsupported:
        raise V3APIError(
            409,
            "FLOW_CONTRACT_UNSUPPORTED",
            "该会话未绑定当前流程契约。",
        ) from None
    except RevisionConflict:
        raise V3APIError(
            409,
            "REVISION_CONFLICT",
            "理解版本已变化，请刷新后重试。",
        ) from None
    except InputRevisionConflict:
        raise V3APIError(
            409,
            "INPUT_REVISION_CONFLICT",
            "输入版本已变化，请刷新后重试。",
        ) from None
    except ChangeNotAllowed:
        raise V3APIError(
            422,
            "CHANGE_NOT_ALLOWED",
            "该字段不允许结构化修正。",
        ) from None
    except MedicalAssetUnavailable:
        raise V3APIError(
            503,
            "MEDICAL_ASSET_UNAVAILABLE",
            "审核知识版本暂不可用，无法执行全文修正。",
            retryable=False,
        ) from None
    except ProviderFailureV3 as error:
        raise _provider_error(error) from None
    return v3_success(result)
