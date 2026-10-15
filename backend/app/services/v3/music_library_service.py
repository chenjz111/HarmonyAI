"""Owner-scoped foundations for the Sprint 7 music library.

W1 exposes no route and performs no writes.  It builds the history read model
from existing ownership and terminal generation-task relationships while
retaining every legal task context for later source/feedback selection.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import stat

from sqlalchemy.orm import Session

from backend.app.models.v3.feedback import Favorite
from backend.app.models.v3.music import GenerationTask, MusicAsset
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
    # The legacy stream resolver supports local paths only. Constrain its
    # input before it touches storage; unknown/remote locators fail closed.
    key = asset.storage_key
    if not isinstance(key, str) or not key.strip() or "\x00" in key:
        return "missing"
    try:
        from backend.app.services.v3.generation_service import _resolve_asset_path

        raw_root = Path(os.environ.get("HARMONY_MEDIA_ROOT", "media"))
        raw_path = Path(key)
        # Do not probe UNC/network shares, device paths, drive-relative paths,
        # URLs or NTFS alternate data streams.
        if str(raw_root).startswith(("\\\\", "//")) or str(raw_path).startswith(("\\\\", "//")):
            return "missing"
        if ".." in raw_path.parts or (raw_path.drive and not raw_path.is_absolute()):
            return "missing"
        if any(":" in part for part in raw_path.parts[1 if raw_path.anchor else 0:]):
            return "missing"
        root = raw_root.resolve(strict=True)
        candidate = (raw_path if raw_path.is_absolute() else root / raw_path).resolve(strict=True)
        if not candidate.is_relative_to(root):
            return "missing"
        path = _resolve_asset_path(str(candidate))
        if path is None:
            return "missing"
        with path.open("rb") as audio:
            if not stat.S_ISREG(os.fstat(audio.fileno()).st_mode):
                return "missing"
            audio.read(1)
        return "ready"
    except (OSError, ValueError, RuntimeError):
        return "missing"


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
        card = MusicCardV1(
            music_id=asset.music_asset_id,
            source_type=asset.source_type,
            default_title=default_title,
            user_title=None,
            display_title=default_title,
            metadata_version=0,
            playable_created_at=playable_created_at,
            last_played_at=None,
            activity_at=playable_created_at,
            # Existing duration_seconds may be a generation target.  W1 has no
            # persisted measurement provenance, so the library read model must
            # expose unknown rather than copy or invent a number.
            duration_seconds=None,
            availability=_availability(asset, now=now_utc),
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
