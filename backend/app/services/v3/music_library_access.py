"""Single authorization + availability authority for the owner music library.

Everything that reveals a private music asset — history list, favorites list,
detail, private title, playback events and (once the stream Gate closes) the
audio stream — must ask *this* module first, so list/detail/stream cannot drift
into three different eligibility rules.

Authorization (docs/sprint7/S7_W2_IMPLEMENTATION_BOUNDARY.md):

- membership is a direct ``music_assets.owner_internal_user_pk`` match **or** a
  terminal (``succeeded`` / ``matched_fallback``) generation task owned by the
  caller that is bound to that asset;
- a NULL asset owner, a ``favorites`` row, or a failed/cancelled task grants
  nothing on its own;
- another owner's tasks/storage/context never prove that a resource exists for
  the caller, so "not authorized" and "does not exist" are reported identically
  (``LibraryAccessDenied``) and must not be distinguished by callers.

Availability reuses the W1 file check, which is the only place that touches the
controlled media root; unknown or remote locators fail closed.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.session import Session as ConversationSession
from backend.app.models.v3.music import GenerationTask, MusicAsset
from backend.app.models.v3.music_library import MusicPlaybackEvent
from backend.app.schemas.v3.common import AuthPrincipal


LIBRARY_TERMINAL_TASK_STATUSES = ("succeeded", "matched_fallback")

ACCESS_SOURCE_DIRECT_OWNER = "direct_owner"
ACCESS_SOURCE_OWNER_TASK = "owner_task"


class LibraryAccessDenied(RuntimeError):
    """The caller has no provable membership for this asset.

    Callers must translate this to the same not-found response used for a
    genuinely absent asset so that no other owner's resource is revealed.
    """


class FeedbackContextUnavailable(RuntimeError):
    """The requested feedback context is not an owned, legal, played context."""


class PlaybackProofUnavailable(RuntimeError):
    """Uniform failure: the specified owned event/task/session is not provable."""


@dataclass(frozen=True)
class PlaybackProof:
    """Internal persisted association, not a client credential or listening measurement."""

    playback_event_row_id: int
    playback_event_id: str
    internal_user_pk: int
    music_asset_id: str
    source_context_id: str
    session_row_id: int
    occurred_at: datetime


@dataclass(frozen=True)
class LibraryAssetAccess:
    """Proof of membership plus the caller's own persisted task contexts."""

    asset: MusicAsset
    access_sources: tuple[str, ...]
    context_ids: tuple[str, ...]

    @property
    def has_context(self) -> bool:
        return bool(self.context_ids)


def library_availability(asset: MusicAsset, *, now: datetime) -> str:
    """The single availability rule for list, detail and stream.

    Delegates to the W1 file check so retention/status/file readability cannot be
    implemented twice.  Imported lazily to keep this module importable without
    pulling the media helpers into unrelated call sites.
    """

    from backend.app.services.v3.music_library_service import _availability

    return _availability(asset, now=now)


def owned_context_ids(db: Session, *, internal_user_pk: int, music_id: str) -> tuple[str, ...]:
    """Context IDs of the caller's own terminal tasks bound to this asset.

    Never includes another owner's tasks, and never invents a context from a
    live session.
    """

    rows = (
        db.query(GenerationTask.task_id)
        .filter(
            GenerationTask.internal_user_pk == internal_user_pk,
            GenerationTask.music_asset_id == music_id,
            GenerationTask.status.in_(LIBRARY_TERMINAL_TASK_STATUSES),
        )
        .all()
    )
    return tuple(sorted(row[0] for row in rows))


def authorize_library_asset(
    db: Session,
    *,
    internal_user_pk: int,
    music_id: str,
) -> LibraryAssetAccess:
    """Return membership proof or raise ``LibraryAccessDenied``."""

    asset = (
        db.query(MusicAsset)
        .filter(MusicAsset.music_asset_id == music_id)
        .one_or_none()
    )
    if asset is None:
        raise LibraryAccessDenied

    context_ids = owned_context_ids(
        db, internal_user_pk=internal_user_pk, music_id=music_id
    )
    direct_owner = asset.owner_internal_user_pk == internal_user_pk
    sources: list[str] = []
    if direct_owner:
        sources.append(ACCESS_SOURCE_DIRECT_OWNER)
    if context_ids:
        sources.append(ACCESS_SOURCE_OWNER_TASK)
    if not sources:
        # NULL owner, a favorite row, or a failed/cancelled task are not enough.
        raise LibraryAccessDenied

    return LibraryAssetAccess(
        asset=asset,
        access_sources=tuple(sources),
        context_ids=context_ids,
    )


def require_library_access(
    db: Session,
    *,
    internal_user_pk: int,
    music_id: str,
) -> LibraryAssetAccess:
    """Membership gate shared by every library-facing read.

    Availability is requested separately through ``library_availability`` so the
    same membership proof can be reused by a read that does not need a file check.
    """

    return authorize_library_asset(db, internal_user_pk=internal_user_pk, music_id=music_id)


def resolve_feedback_context(
    db: Session,
    *,
    internal_user_pk: int,
    music_id: str,
    context_id: str | None,
) -> str:
    """Resolve an explicit, owned, legal feedback context.

    Requires all three of: provable membership, an **explicit** context that is
    one of the caller's own terminal tasks for this asset, and at least one real
    owned playback event for the asset.  Nothing is inferred from the current
    session, the newest task, or another owner's rows.
    """

    access = authorize_library_asset(
        db, internal_user_pk=internal_user_pk, music_id=music_id
    )
    if not context_id or context_id not in access.context_ids:
        raise FeedbackContextUnavailable
    played = (
        db.query(MusicPlaybackEvent.playback_event_row_id)
        .filter(
            MusicPlaybackEvent.internal_user_pk == internal_user_pk,
            MusicPlaybackEvent.music_asset_id == music_id,
            MusicPlaybackEvent.event_type == "play_started",
        )
        .first()
    )
    if played is None:
        raise FeedbackContextUnavailable
    return context_id


def resolve_feedback_playback_proof(
    db: Session,
    *,
    principal: AuthPrincipal,
    music_id: str,
    source_context_id: str,
    playback_event_id: str,
    session_id: str,
) -> PlaybackProof:
    """Resolve the SPECIFIED persisted play, task and session for this principal.

    Read-only even with autoflush enabled. No owner-state creation, transaction
    completion, current-session inference or availability/file access. A later
    Feedback write must preserve this association in its caller transaction and
    the forthcoming 0013 constraints; this value is not a durable grant.
    """

    if any(not isinstance(value, str) or not value or len(value) > 64
           for value in (music_id, source_context_id, playback_event_id, session_id)):
        raise PlaybackProofUnavailable
    owner = principal.internal_user_pk
    with db.no_autoflush:
        try:
            require_library_access(db, internal_user_pk=owner, music_id=music_id)
        except LibraryAccessDenied:
            raise PlaybackProofUnavailable from None
        # Scalar columns deliberately read database authority rather than stale
        # mapped task/event/session attributes in the caller's identity map.
        row = db.execute(
            select(
                MusicPlaybackEvent.playback_event_row_id,
                MusicPlaybackEvent.event_id,
                MusicPlaybackEvent.internal_user_pk,
                MusicPlaybackEvent.music_asset_id,
                MusicPlaybackEvent.source_context_id,
                ConversationSession.id,
                MusicPlaybackEvent.occurred_at,
            )
            .join(GenerationTask, MusicPlaybackEvent.source_context_id == GenerationTask.task_id)
            .join(ConversationSession, GenerationTask.session_row_id == ConversationSession.id)
            .where(
                MusicPlaybackEvent.internal_user_pk == owner,
                MusicPlaybackEvent.event_id == playback_event_id,
                MusicPlaybackEvent.music_asset_id == music_id,
                MusicPlaybackEvent.source_context_id == source_context_id,
                MusicPlaybackEvent.event_type == 'play_started',
                GenerationTask.internal_user_pk == owner,
                GenerationTask.music_asset_id == music_id,
                GenerationTask.status.in_(LIBRARY_TERMINAL_TASK_STATUSES),
                ConversationSession.user_id == owner,
                ConversationSession.session_id == session_id,
            )
        ).one_or_none()
    if row is None:
        raise PlaybackProofUnavailable
    return PlaybackProof(*row)
