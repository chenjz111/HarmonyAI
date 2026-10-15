"""Owner-scoped foundations for the Sprint 7 music library.

W1 exposed no route and performed no writes: it built the history read model from
existing ownership and terminal generation-task relationships while retaining
every legal task context for later source/feedback selection.

W2 (Issue #151) adds the signed-cursor paged reads on top of that projection and
starts consuming the private-title sidecar and real playback events.  It still
never writes: the write paths live in the router/services that own them.
"""

import base64
import binascii
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import stat

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.models.v3.feedback import Favorite
from backend.app.models.v3.music import GenerationTask, MusicAsset
from backend.app.models.v3.music_library import MusicLibraryState, MusicPlaybackEvent
from backend.app.schemas.v3.music_library import MusicCardV1, MusicSourceSummaryV1


_TERMINAL_LIBRARY_STATUSES = ("succeeded", "matched_fallback")
_INSTRUMENT_CODES = {
    "笛": ("dizi", "笛"),
    "古琴": ("guqin", "古琴"),
    "筝": ("guzheng", "古筝"),
    "古筝": ("guzheng", "古筝"),
    "笙": ("sheng", "笙"),
    "箫": ("xiao", "箫"),
    "琵琶": ("pipa", "琵琶"),
}


@dataclass(frozen=True)
class OwnerMusicHistoryItem:
    card: MusicCardV1
    context_ids: tuple[str, ...]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _primary_instrument(asset: MusicAsset) -> tuple[str, str, str | None]:
    instruments = asset.instruments_json
    if not isinstance(instruments, list) or len(instruments) != 1:
        return "unknown", "unknown", None
    instrument = instruments[0]
    if not isinstance(instrument, str):
        return "unknown", "unknown", None
    mapped = _INSTRUMENT_CODES.get(instrument)
    if mapped is None:
        return "unknown", "unknown", None
    code, label = mapped
    return code, "legacy_single", label


def _default_title(asset: MusicAsset, created_at: datetime) -> tuple[str, str, str]:
    code, origin, instrument_label = _primary_instrument(asset)
    day = _utc(created_at)
    date_label = f"{day.year}年{day.month}月{day.day}日"
    suffix = asset.music_asset_id[-6:]
    if instrument_label is None:
        return f"{date_label}的音乐 · {suffix}", code, origin
    return f"{instrument_label} · {date_label} · {suffix}", code, origin


def _availability(asset: MusicAsset, *, now: datetime) -> str:
    if asset.playable_status in {"deleted", "quarantined"}:
        return asset.playable_status
    expires_at = asset.retention_expires_at
    if expires_at is not None and _utc(expires_at) <= now:
        return "expired"
    if asset.playable_status != "ready":
        return asset.playable_status
    return "ready" if resolve_library_audio_path(asset) is not None else "missing"


def resolve_library_audio_path(asset: MusicAsset) -> Path | None:
    """Return only a canonical, controlled, actually readable local file.

    Callers must establish membership before invoking this storage-only helper.
    Shared by availability and Stream: never fall back to the unchecked locator.
    """
    # The legacy stream resolver supports local paths only. Constrain its
    # input before it touches storage; unknown/remote locators fail closed.
    key = asset.storage_key
    if not isinstance(key, str) or not key.strip() or "\x00" in key:
        return None
    try:
        from backend.app.services.v3.generation_service import _resolve_asset_path

        raw_root = Path(os.environ.get("HARMONY_MEDIA_ROOT", "media"))
        raw_path = Path(key)
        # Do not probe UNC/network shares, device paths, drive-relative paths,
        # URLs or NTFS alternate data streams.
        if str(raw_root).startswith(("\\\\", "//")) or str(raw_path).startswith(("\\\\", "//")):
            return None
        if ".." in raw_path.parts or (raw_path.drive and not raw_path.is_absolute()):
            return None
        if any(":" in part for part in raw_path.parts[1 if raw_path.anchor else 0:]):
            return None
        root = raw_root.resolve(strict=True)
        candidate = (raw_path if raw_path.is_absolute() else root / raw_path).resolve(strict=True)
        if not candidate.is_relative_to(root):
            return None
        path = _resolve_asset_path(str(candidate))
        if path is None:
            return None
        with path.open("rb") as audio:
            if not stat.S_ISREG(os.fstat(audio.fileno()).st_mode):
                return None
            audio.read(1)
        return path
    except (OSError, ValueError, RuntimeError):
        return None


def list_owner_music_history(
    db: Session,
    *,
    internal_user_pk: int,
    now: datetime | None = None,
) -> list[OwnerMusicHistoryItem]:
    """Return deduplicated authorized assets without inferring a person/context.

    Direct asset ownership or a terminal task owned by the principal grants
    library membership.  A NULL asset owner, favorite, or non-terminal task is
    never sufficient.  Context IDs remain separate from the public card so a
    later caller can require an explicit choice instead of selecting first or
    latest.
    """

    now_utc = _utc(now or datetime.now(timezone.utc))
    return _collect_owner_music(db, internal_user_pk=internal_user_pk, now=now_utc)


def owner_music_item(
    db: Session,
    *,
    internal_user_pk: int,
    music_id: str,
    now: datetime | None = None,
) -> OwnerMusicHistoryItem | None:
    """The caller's own card for one asset, from the same projection as the list.

    Detail must not reimplement eligibility, so it reuses the collection and
    selects by id; ``None`` means the asset is not in this owner's library.
    """

    now_utc = _utc(now or datetime.now(timezone.utc))
    for item in _collect_owner_music(
        db, internal_user_pk=internal_user_pk, now=now_utc
    ):
        if item.card.music_id == music_id:
            return item
    return None


def _collect_owner_music(
    db: Session,
    *,
    internal_user_pk: int,
    now: datetime,
) -> list[OwnerMusicHistoryItem]:
    """Shared projection behind both the unpaginated list and the paged reads."""

    tasks = (
        db.query(GenerationTask)
        .filter(
            GenerationTask.internal_user_pk == internal_user_pk,
            GenerationTask.status.in_(_TERMINAL_LIBRARY_STATUSES),
            GenerationTask.music_asset_id.isnot(None),
        )
        .all()
    )
    tasks_by_asset: dict[str, list[GenerationTask]] = {}
    for task in tasks:
        tasks_by_asset.setdefault(task.music_asset_id, []).append(task)

    directly_owned_ids = {
        row[0]
        for row in db.query(MusicAsset.music_asset_id)
        .filter(MusicAsset.owner_internal_user_pk == internal_user_pk)
        .all()
    }
    authorized_ids = directly_owned_ids | set(tasks_by_asset)
    if not authorized_ids:
        return []

    assets = (
        db.query(MusicAsset)
        .filter(MusicAsset.music_asset_id.in_(authorized_ids))
        .all()
    )
    favorite_ids = {
        row[0]
        for row in db.query(Favorite.music_asset_id)
        .filter(
            Favorite.internal_user_pk == internal_user_pk,
            Favorite.music_asset_id.in_(authorized_ids),
        )
        .all()
    }
    # Private title sidecar (owner + asset).  Absent rows keep the W1 default
    # title at metadata version 0; the asset title itself is never rewritten.
    sidecars = {
        row.music_asset_id: row
        for row in db.query(MusicLibraryState)
        .filter(
            MusicLibraryState.owner_internal_user_pk == internal_user_pk,
            MusicLibraryState.music_asset_id.in_(authorized_ids),
        )
        .all()
    }
    # Real playback only: last_played_at is the newest owned play_started event.
    last_played: dict[str, datetime] = {}
    for asset_id, occurred_at in (
        db.query(
            MusicPlaybackEvent.music_asset_id,
            func.max(MusicPlaybackEvent.occurred_at),
        )
        .filter(
            MusicPlaybackEvent.internal_user_pk == internal_user_pk,
            MusicPlaybackEvent.music_asset_id.in_(authorized_ids),
        )
        .group_by(MusicPlaybackEvent.music_asset_id)
        .all()
    ):
        if occurred_at is not None:
            last_played[asset_id] = _utc(occurred_at)

    items: list[OwnerMusicHistoryItem] = []
    for asset in assets:
        contexts = tasks_by_asset.get(asset.music_asset_id, [])
        context_ids = tuple(sorted(task.task_id for task in contexts))
        task_times = [task.completed_at for task in contexts if task.completed_at]
        playable_created_at = min(task_times) if task_times else asset.created_at
        playable_created_at = _utc(playable_created_at)
        default_title, instrument_code, instrument_origin = _default_title(
            asset, _utc(asset.created_at)
        )
        source_availability = "unknown" if context_ids else "unavailable"
        sidecar = sidecars.get(asset.music_asset_id)
        user_title = sidecar.user_title if sidecar is not None else None
        metadata_version = int(sidecar.metadata_version) if sidecar is not None else 0
        last_played_at = last_played.get(asset.music_asset_id)
        card = MusicCardV1(
            music_id=asset.music_asset_id,
            source_type=asset.source_type,
            default_title=default_title,
            user_title=user_title,
            display_title=user_title or default_title,
            metadata_version=metadata_version,
            playable_created_at=playable_created_at,
            last_played_at=last_played_at,
            # Sort/activity rule fixed by the W2 boundary: real playback wins,
            # otherwise the legal playable creation time.
            activity_at=last_played_at or playable_created_at,
            # Existing duration_seconds may be a generation target.  W1 has no
            # persisted measurement provenance, so the library read model must
            # expose unknown rather than copy or invent a number.
            duration_seconds=None,
            availability=_availability(asset, now=now),
            is_favorite=asset.music_asset_id in favorite_ids,
            primary_instrument_code=instrument_code,
            primary_instrument_origin=instrument_origin,
            source_summary=MusicSourceSummaryV1(
                kind="unknown" if context_ids else "none",
                availability=source_availability,
                context_count=len(context_ids),
            ),
        )
        items.append(OwnerMusicHistoryItem(card=card, context_ids=context_ids))

    items.sort(
        key=lambda item: (item.card.activity_at, item.card.music_id), reverse=True
    )
    return items


# ---------------------------------------------------------------------------
# Sprint 7 W2: signed-cursor pagination (Issue #151)
#
# Boundary rules implemented here (docs/sprint7/S7_W2_IMPLEMENTATION_BOUNDARY.md):
#   - the cursor cryptographically binds owner, list, cursor version, the library
#     epoch and the sort boundary, so it cannot be moved to another owner/list;
#   - a real asset addition bumps ``library_epoch`` and every previously issued
#     cursor becomes stale instead of silently skipping or duplicating a card;
#   - there is no unsigned fallback: without signing configuration the paged read
#     fails closed rather than degrading to a guessable cursor;
#   - ordering is the fixed ``(activity_at, music_id)`` descending tuple, so the
#     page boundary is total and stable.
# ---------------------------------------------------------------------------

CURSOR_VERSION = 1
LIBRARY_PAGE_DEFAULT_LIMIT = 20
LIBRARY_PAGE_MAX_LIMIT = 50
CURSOR_SECRET_ENV = "HARMONY_LIBRARY_CURSOR_SECRET"
CURSOR_SECRET_MIN_BYTES = 16

LIST_KEY_HISTORY = "history"
LIST_KEY_FAVORITES = "favorites"


class LibraryCursorError(RuntimeError):
    """Cursor missing, malformed, tampered, bound elsewhere, or stale."""

    def __init__(self, message: str, *, stale: bool = False) -> None:
        super().__init__(message)
        self.stale = stale


class LibraryCursorConfigError(RuntimeError):
    """Cursor signing configuration is absent or too weak (fail closed)."""


class LibraryPageLimitError(RuntimeError):
    """The requested page size is outside the supported range."""


@dataclass(frozen=True)
class OwnerMusicPage:
    items: list[OwnerMusicHistoryItem]
    next_cursor: str | None
    has_more: bool
    library_epoch: int


def _cursor_secret(explicit: bytes | str | None = None) -> bytes:
    if explicit is None:
        raw = os.environ.get(CURSOR_SECRET_ENV, "")
    elif isinstance(explicit, bytes):
        raw = explicit.decode("utf-8", errors="strict")
    else:
        raw = explicit
    secret = raw.strip().encode("utf-8") if isinstance(raw, str) else raw
    if len(secret) < CURSOR_SECRET_MIN_BYTES:
        raise LibraryCursorConfigError(
            f"{CURSOR_SECRET_ENV} must be configured with at least "
            f"{CURSOR_SECRET_MIN_BYTES} bytes; unsigned cursors are not offered"
        )
    return secret


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _sign(payload: bytes, secret: bytes) -> str:
    return _b64encode(hmac.new(secret, payload, hashlib.sha256).digest())


def validate_library_limit(limit: int | None) -> int:
    if limit is None:
        return LIBRARY_PAGE_DEFAULT_LIMIT
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise LibraryPageLimitError
    if limit < 1 or limit > LIBRARY_PAGE_MAX_LIMIT:
        raise LibraryPageLimitError
    return limit


def encode_library_cursor(
    *,
    internal_user_pk: int,
    list_key: str,
    epoch: int,
    activity_at: datetime,
    music_id: str,
    secret: bytes | str | None = None,
) -> str:
    payload = json.dumps(
        {
            "v": CURSOR_VERSION,
            "o": int(internal_user_pk),
            "l": list_key,
            "e": int(epoch),
            "a": _utc(activity_at).isoformat(),
            "m": music_id,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"{_b64encode(payload)}.{_sign(payload, _cursor_secret(secret))}"


def decode_library_cursor(
    cursor: str,
    *,
    internal_user_pk: int,
    list_key: str,
    epoch: int,
    secret: bytes | str | None = None,
) -> tuple[datetime, str]:
    """Return the sort boundary, or raise ``LibraryCursorError``."""

    if not isinstance(cursor, str) or not cursor.strip():
        raise LibraryCursorError("cursor is required")
    parts = cursor.strip().split(".")
    if len(parts) != 2:
        raise LibraryCursorError("cursor is malformed")
    encoded_payload, signature = parts
    try:
        payload = _b64decode(encoded_payload)
        provided = _b64decode(signature)
    except (ValueError, binascii.Error):
        raise LibraryCursorError("cursor is malformed") from None
    expected = hmac.new(_cursor_secret(secret), payload, hashlib.sha256).digest()
    if not hmac.compare_digest(provided, expected):
        raise LibraryCursorError("cursor signature is invalid")
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise LibraryCursorError("cursor is malformed") from None
    if not isinstance(decoded, dict) or decoded.get("v") != CURSOR_VERSION:
        raise LibraryCursorError("cursor version is unsupported")
    if decoded.get("o") != int(internal_user_pk) or decoded.get("l") != list_key:
        # A cursor from another owner or another list is not a valid boundary.
        raise LibraryCursorError("cursor does not belong to this request")
    if decoded.get("e") != int(epoch):
        raise LibraryCursorError("cursor is stale", stale=True)
    raw_activity = decoded.get("a")
    music_id = decoded.get("m")
    if not isinstance(raw_activity, str) or not isinstance(music_id, str) or not music_id:
        raise LibraryCursorError("cursor is malformed")
    try:
        activity_at = datetime.fromisoformat(raw_activity)
    except ValueError:
        raise LibraryCursorError("cursor is malformed") from None
    if activity_at.tzinfo is None:
        raise LibraryCursorError("cursor is malformed")
    return _utc(activity_at), music_id


def page_owner_music(
    db: Session,
    *,
    internal_user_pk: int,
    limit: int | None = None,
    cursor: str | None = None,
    list_key: str = LIST_KEY_HISTORY,
    favorites_only: bool = False,
    now: datetime | None = None,
    library_epoch: int | None = None,
    cursor_secret: bytes | str | None = None,
) -> OwnerMusicPage:
    """One page of the owner's library plus the next signed cursor.

    Reads never write: the epoch is read from owner state (missing state reads as
    0) and no playback or owner-state row is created here.
    """

    from backend.app.services.v3.owner_music_state_service import library_epoch_for

    page_size = validate_library_limit(limit)
    # Validate the signing configuration up front: pagination must fail closed
    # on the first page too, instead of succeeding and failing on the next one.
    secret = _cursor_secret(cursor_secret)
    epoch = (
        library_epoch
        if library_epoch is not None
        else library_epoch_for(db, internal_user_pk=internal_user_pk)
    )
    now_utc = _utc(now or datetime.now(timezone.utc))
    items = _collect_owner_music(db, internal_user_pk=internal_user_pk, now=now_utc)
    if favorites_only:
        items = [item for item in items if item.card.is_favorite]

    if cursor:
        boundary_activity, boundary_music_id = decode_library_cursor(
            cursor,
            internal_user_pk=internal_user_pk,
            list_key=list_key,
            epoch=epoch,
            secret=secret,
        )
        items = [
            item
            for item in items
            if (item.card.activity_at, item.card.music_id)
            < (boundary_activity, boundary_music_id)
        ]

    page = items[:page_size]
    has_more = len(items) > page_size
    next_cursor = None
    if has_more and page:
        last = page[-1].card
        next_cursor = encode_library_cursor(
            internal_user_pk=internal_user_pk,
            list_key=list_key,
            epoch=epoch,
            activity_at=last.activity_at,
            music_id=last.music_id,
            secret=secret,
        )
    return OwnerMusicPage(
        items=page, next_cursor=next_cursor, has_more=has_more, library_epoch=epoch
    )


# ---------------------------------------------------------------------------
# Sprint 7 W2: private title sidecar and real playback events (Issue #151)
#
# Both writes are owner+asset scoped, commit once at the end of the request, and
# never touch ``music_assets.title`` or its checksum.
# ---------------------------------------------------------------------------


class TitleVersionConflict(RuntimeError):
    """``expected_version`` does not match the owner's current metadata version."""


class PlaybackEventConflict(RuntimeError):
    """The same ``event_id`` was already used for a different asset."""


class LibraryAssetNotPlayable(RuntimeError):
    """A play can only be recorded for an asset that is really playable now."""


@dataclass(frozen=True)
class PrivateTitleState:
    music_id: str
    user_title: str | None
    display_title: str
    metadata_version: int


def _title_state(asset: MusicAsset, sidecar: MusicLibraryState | None) -> PrivateTitleState:
    default_title, _code, _origin = _default_title(asset, _utc(asset.created_at))
    user_title = sidecar.user_title if sidecar is not None else None
    version = int(sidecar.metadata_version) if sidecar is not None else 0
    return PrivateTitleState(
        music_id=asset.music_asset_id,
        user_title=user_title,
        display_title=user_title or default_title,
        metadata_version=version,
    )


def read_private_title(
    db: Session,
    *,
    internal_user_pk: int,
    asset: MusicAsset,
) -> PrivateTitleState:
    sidecar = (
        db.query(MusicLibraryState)
        .filter(
            MusicLibraryState.owner_internal_user_pk == internal_user_pk,
            MusicLibraryState.music_asset_id == asset.music_asset_id,
        )
        .one_or_none()
    )
    return _title_state(asset, sidecar)


def update_private_title(
    db: Session,
    *,
    internal_user_pk: int,
    asset: MusicAsset,
    user_title: str | None,
    expected_version: int,
) -> PrivateTitleState:
    """Compare-and-swap the owner's private title.

    ``user_title=None`` clears the alias.  The version check is an atomic
    conditional ``UPDATE`` (not read-then-write), so two concurrent writers with
    the same ``expected_version`` cannot both win.  Returns the new state; the
    caller owns the commit.
    """

    from sqlalchemy import update
    from sqlalchemy.exc import IntegrityError
    from backend.app.services.v3.owner_music_state_service import advance_library_epoch

    current = read_private_title(db, internal_user_pk=internal_user_pk, asset=asset)
    if current.metadata_version != expected_version:
        raise TitleVersionConflict

    if current.metadata_version == 0:
        # First write for this (owner, asset): create the sidecar at version 1.
        row = MusicLibraryState(
            owner_internal_user_pk=internal_user_pk,
            music_asset_id=asset.music_asset_id,
            user_title=user_title,
            metadata_version=1,
        )
        db.add(row)
        try:
            db.flush()
        except IntegrityError:
            # Another writer created it first; the caller's expected version is
            # no longer current, so this is a conflict rather than a retry.
            db.rollback()
            raise TitleVersionConflict from None
        advance_library_epoch(db, internal_user_pk=internal_user_pk)
        return PrivateTitleState(
            music_id=asset.music_asset_id,
            user_title=user_title,
            display_title=user_title
            or _default_title(asset, _utc(asset.created_at))[0],
            metadata_version=1,
        )

    result = db.execute(
        update(MusicLibraryState)
        .where(
            MusicLibraryState.owner_internal_user_pk == internal_user_pk,
            MusicLibraryState.music_asset_id == asset.music_asset_id,
            MusicLibraryState.metadata_version == expected_version,
        )
        .values(user_title=user_title, metadata_version=expected_version + 1)
    )
    if result.rowcount != 1:
        raise TitleVersionConflict
    advance_library_epoch(db, internal_user_pk=internal_user_pk)
    default_title, _code, _origin = _default_title(asset, _utc(asset.created_at))
    return PrivateTitleState(
        music_id=asset.music_asset_id,
        user_title=user_title,
        display_title=user_title or default_title,
        metadata_version=expected_version + 1,
    )


@dataclass(frozen=True)
class RecordedPlaybackEvent:
    event_id: str
    music_id: str
    event_type: str
    occurred_at: datetime
    last_played_at: datetime
    replayed: bool


def _latest_playback(
    db: Session, *, internal_user_pk: int, music_id: str
) -> datetime | None:
    value = (
        db.query(func.max(MusicPlaybackEvent.occurred_at))
        .filter(
            MusicPlaybackEvent.internal_user_pk == internal_user_pk,
            MusicPlaybackEvent.music_asset_id == music_id,
        )
        .scalar()
    )
    return None if value is None else _utc(value)


def replayed_playback_event(
    db: Session,
    *,
    internal_user_pk: int,
    music_id: str,
    event_id: str,
) -> RecordedPlaybackEvent | None:
    """Resolve an already-stored event after a concurrent insert conflict.

    Used when ``record_playback_event`` lost a race: two requests with the same
    owner-scoped ``event_id`` may both pass the pre-check, and only one insert can
    win.  The loser must become an idempotent replay of the winner rather than an
    error, and must not bump the library epoch a second time.

    Returns ``None`` when no such event exists (the conflict was elsewhere, e.g.
    the owner-state row), and raises ``PlaybackEventConflict`` when the stored
    event belongs to a different asset.
    """

    row = (
        db.query(MusicPlaybackEvent)
        .filter(
            MusicPlaybackEvent.internal_user_pk == internal_user_pk,
            MusicPlaybackEvent.event_id == event_id,
        )
        .one_or_none()
    )
    if row is None:
        return None
    if row.music_asset_id != music_id:
        raise PlaybackEventConflict("event_id already belongs to another asset")
    occurred_at = _utc(row.occurred_at)
    latest = _latest_playback(db, internal_user_pk=internal_user_pk, music_id=music_id)
    return RecordedPlaybackEvent(
        event_id=event_id,
        music_id=music_id,
        event_type=row.event_type,
        occurred_at=occurred_at,
        last_played_at=latest or occurred_at,
        replayed=True,
    )


def record_playback_event(
    db: Session,
    *,
    internal_user_pk: int,
    asset: MusicAsset,
    context_ids: tuple[str, ...],
    event_id: str,
    event_type: str,
    source_context_id: str | None,
    now: datetime | None = None,
) -> RecordedPlaybackEvent:
    """Record one real ``play_started`` event, idempotently per owner.

    - ``event_id`` is an owner-scoped idempotency key: a replay with the same
      asset returns the stored event (``replayed=True``) instead of inserting a
      second row, while the same id for a *different* asset is a conflict;
    - ``occurred_at`` is always server time, never client-supplied;
    - the playback ``last_played_at`` is the maximum over the owner's events, so
      concurrent inserts converge instead of overwriting each other;
    - a new event changes the ``activity_at`` sort key, so it bumps the owner's
      library epoch in the same transaction: an in-flight cursor must not be able
      to skip a card that a play just moved to the top of the list.
    """

    from backend.app.services.v3.music_library_access import (
        FeedbackContextUnavailable,
    )
    from backend.app.services.v3.owner_music_state_service import advance_library_epoch

    if event_type != "play_started":
        raise ValueError("only play_started is a real playback event")
    if source_context_id is not None and source_context_id not in context_ids:
        # A play may only be attributed to an explicitly owned, legal context.
        raise FeedbackContextUnavailable

    existing = (
        db.query(MusicPlaybackEvent)
        .filter(
            MusicPlaybackEvent.internal_user_pk == internal_user_pk,
            MusicPlaybackEvent.event_id == event_id,
        )
        .one_or_none()
    )
    if existing is not None:
        if existing.music_asset_id != asset.music_asset_id:
            raise PlaybackEventConflict("event_id already belongs to another asset")
        occurred_at = _utc(existing.occurred_at)
        latest = _latest_playback(
            db, internal_user_pk=internal_user_pk, music_id=asset.music_asset_id
        )
        return RecordedPlaybackEvent(
            event_id=event_id,
            music_id=asset.music_asset_id,
            event_type=existing.event_type,
            occurred_at=occurred_at,
            last_played_at=latest or occurred_at,
            replayed=True,
        )

    occurred_at = _utc(now or datetime.now(timezone.utc))
    db.add(
        MusicPlaybackEvent(
            internal_user_pk=internal_user_pk,
            event_id=event_id,
            music_asset_id=asset.music_asset_id,
            event_type=event_type,
            source_context_id=source_context_id,
            occurred_at=occurred_at,
        )
    )
    db.flush()
    advance_library_epoch(db, internal_user_pk=internal_user_pk)
    latest = _latest_playback(
        db, internal_user_pk=internal_user_pk, music_id=asset.music_asset_id
    )
    return RecordedPlaybackEvent(
        event_id=event_id,
        music_id=asset.music_asset_id,
        event_type=event_type,
        occurred_at=occurred_at,
        last_played_at=latest or occurred_at,
        replayed=False,
    )
