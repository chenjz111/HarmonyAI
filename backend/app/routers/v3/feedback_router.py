"""V3 Agent 5 feedback, favorites and personal data endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.routers.v3.transport import V3APIError, v3_success
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.envelope import V3SuccessEnvelope
from backend.app.schemas.v3.feedback import (
    FeedbackV3 as FeedbackV3Request,
    FeedbackV3Output,
    UserPreferenceProfile,
)
from backend.app.schemas.v3.me import (
    FavoriteList,
    FavoriteRequest,
    FavoriteState,
    FeedbackHistory,
)
from backend.app.services.v3.auth_service import get_current_v3_principal
from backend.app.services.v3.feedback_service import (
    FeedbackConflict,
    OwnedResourceNotFound,
    get_preferences,
    list_favorites,
    list_feedback_history,
    remove_favorite,
    set_favorite,
    submit_feedback,
)


router = APIRouter()


def _not_found() -> V3APIError:
    return V3APIError(404, "RESOURCE_NOT_FOUND", "未找到对应资源。")


@router.post(
    "/feedback",
    response_model=V3SuccessEnvelope[FeedbackV3Output],
    status_code=201,
)
def create_feedback(
    response: Response,
    body: FeedbackV3Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[FeedbackV3Output]:
    if idempotency_key is None or not idempotency_key.strip():
        raise V3APIError(
            400,
            "IDEMPOTENCY_KEY_REQUIRED",
            "需要提供幂等键后才能提交反馈。",
        )
    try:
        result, replayed = submit_feedback(
            db,
            principal,
            body,
            idempotency_key.strip(),
        )
    except OwnedResourceNotFound:
        raise _not_found() from None
    except FeedbackConflict:
        raise V3APIError(
            422,
            "INVALID_FEEDBACK",
            "反馈引用的音频资源类型不匹配。",
        ) from None
    if replayed:
        response.status_code = 200
    return v3_success(result)


@router.get(
    "/favorites",
    response_model=V3SuccessEnvelope[FavoriteList],
)
def get_favorites(
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[FavoriteList]:
    return v3_success(list_favorites(db, principal))


@router.put(
    "/favorites",
    response_model=V3SuccessEnvelope[FavoriteState],
)
def add_favorite(
    body: FavoriteRequest,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[FavoriteState]:
    try:
        return v3_success(set_favorite(db, principal, body.music_ref.music_id))
    except OwnedResourceNotFound:
        raise _not_found() from None


@router.delete(
    "/favorites/{music_id}",
    response_model=V3SuccessEnvelope[FavoriteState],
)
def delete_favorite(
    music_id: str,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[FavoriteState]:
    try:
        return v3_success(remove_favorite(db, principal, music_id))
    except OwnedResourceNotFound:
        raise _not_found() from None


@router.get(
    "/me/history",
    response_model=V3SuccessEnvelope[FeedbackHistory],
)
def get_my_history(
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[FeedbackHistory]:
    return v3_success(list_feedback_history(db, principal))


@router.get(
    "/me/preferences",
    response_model=V3SuccessEnvelope[UserPreferenceProfile],
)
def get_my_preferences(
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[UserPreferenceProfile]:
    try:
        return v3_success(get_preferences(db, principal))
    except OwnedResourceNotFound:
        raise _not_found() from None
