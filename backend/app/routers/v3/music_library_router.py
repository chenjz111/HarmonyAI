"""Sprint 7 W2 private music-library endpoints (Issue #151).

Routes (identical to the intent published in
``docs/sprint7/TEAM_BASELINE_DEVELOPMENT.md`` so the frozen frontend adapter does
not need new fields):

| Method | Path | Meaning |
|---|---|---|
| GET | ``/me/music-assets`` | owner history, signed-cursor paginated |
| GET | ``/me/music-favorites`` | favorites that are *also* authorized library assets |
| GET | ``/music/assets/{music_id}`` | detail with real availability and persisted explanation |
| PATCH | ``/music/assets/{music_id}/title`` | private title, compare-and-swap |
| POST | ``/music/assets/{music_id}/playback-events`` | one real ``play_started`` event |

Favorites *writes* stay on the existing ``PUT/DELETE /api/v3/favorites`` routes in
``feedback_router`` (one favorites authority, no second store).

Integration (Issue #150) owns ``main.py`` registration and the shared model
exports, so this module is not wired into the app yet; it is exercisable on its own
(see ``tests/api/v3/test_s7_music_library_api.py``).

Read routes never write.  Write routes each commit exactly once, after the
library epoch and the sidecar/event row move together in the same transaction.
"""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.routers.v3.transport import V3APIError, v3_success
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.envelope import V3SuccessEnvelope
from backend.app.schemas.v3.music_library import (
    LibraryAudioV1,
    MusicDetailV1,
    MusicLibraryPageV1,
    PlaybackEventRequestV1,
    PlaybackEventResultV1,
    TitleUpdateRequestV1,
    TitleUpdateResultV1,
)
from backend.app.services.v3.auth_service import get_current_v3_principal
from backend.app.services.v3.music_library_access import (
    FeedbackContextUnavailable,
    LibraryAccessDenied,
    library_availability,
    require_library_access,
)
from backend.app.services.v3.music_library_service import (
    LIST_KEY_FAVORITES,
    LIST_KEY_HISTORY,
    LibraryCursorConfigError,
    LibraryCursorError,
    LibraryPageLimitError,
    PlaybackEventConflict,
    TitleVersionConflict,
    owner_music_item,
    page_owner_music,
    record_playback_event,
    replayed_playback_event,
    update_private_title,
)
from backend.app.services.v3.music_source_service import (
    context_choices,
    history_explanation,
    owned_context_projection,
    select_context,
)


router = APIRouter()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _not_found() -> V3APIError:
    """Used for "absent" and "not yours" alike, so other owners leak nothing."""

    return V3APIError(404, "RESOURCE_NOT_FOUND", "未找到对应资源。")


def _not_available() -> V3APIError:
    return V3APIError(404, "RESOURCE_NOT_AVAILABLE", "音频资源暂不可用。")


def _translate_read_error(error: Exception) -> V3APIError:
    if isinstance(error, LibraryPageLimitError):
        return V3APIError(
            400,
            "INVALID_LIMIT",
            "limit 必须是 1 到 50 之间的整数。",
        )
    if isinstance(error, LibraryCursorConfigError):
        return V3APIError(
            503,
            "LIBRARY_CURSOR_UNAVAILABLE",
            "分页游标签名尚未配置，暂不提供列表分页。",
            retryable=True,
        )
    if isinstance(error, LibraryCursorError):
        if error.stale:
            return V3APIError(
                409,
                "LIBRARY_CURSOR_STALE",
                "列表已更新，请从第一页重新获取。",
                retryable=True,
                next_actions=["refetch_first_page"],
            )
        return V3APIError(400, "INVALID_CURSOR", "分页游标无效。")
    if isinstance(error, LibraryAccessDenied):
        return _not_found()
    raise error


@router.get(
    "/me/music-assets",
    response_model=V3SuccessEnvelope[MusicLibraryPageV1],
)
def list_my_music_assets(
    limit: Annotated[int | None, Query()] = None,
    cursor: Annotated[str | None, Query()] = None,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[MusicLibraryPageV1]:
    try:
        page = page_owner_music(
            db,
            internal_user_pk=principal.internal_user_pk,
            limit=limit,
            cursor=cursor,
            list_key=LIST_KEY_HISTORY,
            now=_utc_now(),
        )
    except (
        LibraryPageLimitError,
        LibraryCursorConfigError,
        LibraryCursorError,
    ) as error:
        raise _translate_read_error(error) from None
    return v3_success(
        MusicLibraryPageV1(
            items=[item.card for item in page.items],
            next_cursor=page.next_cursor,
            has_more=page.has_more,
        )
    )


@router.get(
    "/me/music-favorites",
    response_model=V3SuccessEnvelope[MusicLibraryPageV1],
)
def list_my_music_favorites(
    limit: Annotated[int | None, Query()] = None,
    cursor: Annotated[str | None, Query()] = None,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[MusicLibraryPageV1]:
    """Favorites that are also authorized library assets.

    A favorite row alone grants nothing, so an asset that is favorited but has no
    provable membership is not listed here.
    """

    try:
        page = page_owner_music(
            db,
            internal_user_pk=principal.internal_user_pk,
            limit=limit,
            cursor=cursor,
            list_key=LIST_KEY_FAVORITES,
            favorites_only=True,
            now=_utc_now(),
        )
    except (
        LibraryPageLimitError,
        LibraryCursorConfigError,
        LibraryCursorError,
    ) as error:
        raise _translate_read_error(error) from None
    return v3_success(
        MusicLibraryPageV1(
            items=[item.card for item in page.items],
            next_cursor=page.next_cursor,
            has_more=page.has_more,
        )
    )


@router.get(
    "/music/assets/{music_id}",
    response_model=V3SuccessEnvelope[MusicDetailV1],
)
def get_music_asset_detail(
    music_id: str,
    context_id: Annotated[str | None, Query()] = None,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[MusicDetailV1]:
    """Detail read.  Never writes, and never silently picks a source context."""

    try:
        access = require_library_access(
            db, internal_user_pk=principal.internal_user_pk, music_id=music_id
        )
        item = owner_music_item(
            db,
            internal_user_pk=principal.internal_user_pk,
            music_id=music_id,
            now=_utc_now(),
        )
        if item is None:  # pragma: no cover - access proof implies membership
            raise LibraryAccessDenied
        contexts = owned_context_projection(
            db, internal_user_pk=principal.internal_user_pk, music_id=music_id
        )
        selected = select_context(contexts, context_id)
    except (LibraryAccessDenied, FeedbackContextUnavailable) as error:
        if isinstance(error, FeedbackContextUnavailable):
            raise V3APIError(
                422,
                "CONTEXT_NOT_AVAILABLE",
                "所选来源不属于本次音乐，或不可用于该操作。",
            ) from None
        raise _translate_read_error(error) from None

    card = item.card
    return v3_success(
        MusicDetailV1(
            card=card,
            audio=LibraryAudioV1(
                availability=library_availability(access.asset, now=_utc_now()),
                # Measured duration only; the legacy generation target is never
                # exposed as if it were the real audio length.
                duration_seconds=card.duration_seconds,
                format=access.asset.format,
            ),
            source_contexts=context_choices(contexts),
            selected_context_id=selected.context_id if selected else None,
            history_explanation=history_explanation(selected) if selected else None,
        )
    )


@router.patch(
    "/music/assets/{music_id}/title",
    response_model=V3SuccessEnvelope[TitleUpdateResultV1],
)
def update_music_asset_title(
    music_id: str,
    body: TitleUpdateRequestV1,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[TitleUpdateResultV1]:
    """Owner-private title alias.  ``user_title=null`` clears it.

    The stored ``music_assets.title`` and its checksum are never modified.
    """

    try:
        access = require_library_access(
            db, internal_user_pk=principal.internal_user_pk, music_id=music_id
        )
    except LibraryAccessDenied as error:
        raise _translate_read_error(error) from None

    try:
        state = update_private_title(
            db,
            internal_user_pk=principal.internal_user_pk,
            asset=access.asset,
            user_title=body.user_title,
            expected_version=body.expected_version,
        )
    except TitleVersionConflict:
        db.rollback()
        raise V3APIError(
            409,
            "TITLE_VERSION_CONFLICT",
            "标题已被更新，请刷新后重试。",
            retryable=True,
            next_actions=["refetch_detail"],
        ) from None
    db.commit()
    return v3_success(
        TitleUpdateResultV1(
            music_id=state.music_id,
            user_title=state.user_title,
            display_title=state.display_title,
            metadata_version=state.metadata_version,
        )
    )


@router.post(
    "/music/assets/{music_id}/playback-events",
    response_model=V3SuccessEnvelope[PlaybackEventResultV1],
    status_code=201,
)
def create_music_playback_event(
    music_id: str,
    body: PlaybackEventRequestV1,
    response: Response,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[PlaybackEventResultV1]:
    """Record one real playback start.

    Only ``play_started`` is accepted; page views, prefetch and seek are not plays
    and have no route here.  Replaying the same ``event_id`` for the same asset is
    idempotent (200 + ``replayed=true``); reusing it for another asset is a
    conflict.
    """

    try:
        access = require_library_access(
            db, internal_user_pk=principal.internal_user_pk, music_id=music_id
        )
    except LibraryAccessDenied as error:
        raise _translate_read_error(error) from None

    if library_availability(access.asset, now=_utc_now()) != "ready":
        # A play implies the audio really played, so an unavailable/unreadable
        # asset cannot be recorded as played.
        raise _not_available()

    try:
        recorded = record_playback_event(
            db,
            internal_user_pk=principal.internal_user_pk,
            asset=access.asset,
            context_ids=access.context_ids,
            event_id=body.event_id,
            event_type=body.event_type,
            source_context_id=body.source_context_id,
        )
    except FeedbackContextUnavailable:
        db.rollback()
        raise V3APIError(
            422,
            "CONTEXT_NOT_AVAILABLE",
            "所选来源不属于本次音乐，或不可用于该操作。",
        ) from None
    except PlaybackEventConflict:
        db.rollback()
        raise V3APIError(
            409,
            "PLAYBACK_EVENT_CONFLICT",
            "该播放事件标识已属于其他音乐。",
        ) from None
    except IntegrityError:
        db.rollback()
        # A concurrent request may have stored the very same owner-scoped event
        # id while this one was in flight.  That is an idempotent replay of this
        # asset (Owner ruling: replay must not bump the library epoch again), not
        # a conflict; only a genuinely unusable situation becomes an error.
        try:
            replayed = replayed_playback_event(
                db,
                internal_user_pk=principal.internal_user_pk,
                music_id=music_id,
                event_id=body.event_id,
            )
        except PlaybackEventConflict:
            raise V3APIError(
                409,
                "PLAYBACK_EVENT_CONFLICT",
                "该播放事件标识已属于其他音乐。",
            ) from None
        if replayed is None:
            raise V3APIError(
                409,
                "PLAYBACK_EVENT_CONFLICT",
                "播放记录写入冲突，请重试。",
                retryable=True,
            ) from None
        response.status_code = 200
        return v3_success(
            PlaybackEventResultV1(
                event_id=replayed.event_id,
                music_id=replayed.music_id,
                event_type=replayed.event_type,
                occurred_at=replayed.occurred_at,
                last_played_at=replayed.last_played_at,
                replayed=replayed.replayed,
            )
        )
    db.commit()
    if recorded.replayed:
        response.status_code = 200
    return v3_success(
        PlaybackEventResultV1(
            event_id=recorded.event_id,
            music_id=recorded.music_id,
            event_type=recorded.event_type,
            occurred_at=recorded.occurred_at,
            last_played_at=recorded.last_played_at,
            replayed=recorded.replayed,
        )
    )
