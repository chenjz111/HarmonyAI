"""V3 Agent 4 music generation endpoints."""

import os
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.ai_engine.v3.generation_provider_adapter import build_music_provider_bundle
from backend.ai_engine.v3.music_provider import (
    MusicGenerationProvider,
    MusicProviderFailureV3,
)
from backend.app.core.database import get_db
from backend.app.routers.v3.transport import V3APIError, v3_success
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.envelope import V3SuccessEnvelope
from backend.app.schemas.v3.music import MusicGenerationV3Request, MusicTask
from backend.app.services.v3.auth_service import get_current_v3_principal
from backend.app.services.v3.generation_service import (
    AssetNotPlayable,
    GenerationCancelUnsupported,
    GenerationNotAllowed,
    IdempotencyConflict,
    OwnedResourceNotFound,
    cancel_generation_task,
    create_generation_task,
    get_generation_task,
    get_playable_asset_stream_path,
)


router = APIRouter()


def get_music_provider() -> MusicGenerationProvider:
    return build_music_provider_bundle(os.environ).provider


def _not_found() -> V3APIError:
    return V3APIError(404, "RESOURCE_NOT_FOUND", "未找到对应资源。")


@router.post(
    "/music/generations",
    response_model=V3SuccessEnvelope[MusicTask],
    status_code=201,
)
def create_generation(
    response: Response,
    body: MusicGenerationV3Request,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    provider: MusicGenerationProvider = Depends(get_music_provider),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[MusicTask]:
    try:
        result, replayed = create_generation_task(db, principal, body, provider)
    except OwnedResourceNotFound:
        raise _not_found() from None
    except GenerationNotAllowed:
        raise V3APIError(
            409,
            "GENERATION_NOT_ALLOWED",
            "当前处方状态不允许生成音乐。",
        ) from None
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
    "/music/generations/{task_id}",
    response_model=V3SuccessEnvelope[MusicTask],
)
def get_generation(
    task_id: str,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    provider: MusicGenerationProvider = Depends(get_music_provider),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[MusicTask]:
    try:
        return v3_success(get_generation_task(db, principal, task_id, provider))
    except OwnedResourceNotFound:
        raise _not_found() from None


@router.post(
    "/music/generations/{task_id}/cancel",
    response_model=V3SuccessEnvelope[MusicTask],
)
def cancel_generation(
    task_id: str,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    provider: MusicGenerationProvider = Depends(get_music_provider),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[MusicTask]:
    try:
        return v3_success(cancel_generation_task(db, principal, task_id, provider))
    except OwnedResourceNotFound:
        raise _not_found() from None
    except GenerationCancelUnsupported:
        raise V3APIError(
            409,
            "GENERATION_CANCEL_UNSUPPORTED",
            "当前生成服务不支持取消任务。",
        ) from None
    except MusicProviderFailureV3 as error:
        raise V3APIError(
            502,
            error.error_code,
            error.safe_message,
            retryable=error.retryable,
        ) from None


@router.get(
    "/music/assets/{music_id}/stream",
    response_class=FileResponse,
)
def stream_asset(
    music_id: str,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> FileResponse:
    try:
        asset, path = get_playable_asset_stream_path(db, principal, music_id)
    except OwnedResourceNotFound:
        raise _not_found() from None
    except AssetNotPlayable:
        raise V3APIError(
            404,
            "RESOURCE_NOT_AVAILABLE",
            "音频资源暂不可用。",
        ) from None
    media_type = {
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "m4a": "audio/mp4",
    }.get(asset.format, "application/octet-stream")
    return FileResponse(path, media_type=media_type)
