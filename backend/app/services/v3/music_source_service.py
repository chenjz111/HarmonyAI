"""Persisted source/context projection for an owner's private music library.

A library card may exist without any context, but anything that claims *where a
piece of music came from* — the detail explanation, the feedback context, a
playback ``source_context_id`` — must be an explicit choice among the caller's own
persisted generation contexts.

Hard rules (Issue #151 / docs/sprint7/TEAM_BASELINE_DEVELOPMENT.md):

- contexts come only from the caller's own terminal generation tasks bound to the
  asset; another owner's tasks are never projected and never used as proof;
- with several contexts nothing is auto-selected (not the earliest, not the
  latest, not "the one that happens to be live"), so source-dependent actions stay
  closed until the owner picks one;
- the explanation is built from **persisted rows only**.  The current session is
  never read here, so an old asset cannot borrow today's state as its origin;
- no prose is invented: every field is a stored fact, and unverifiable ones stay
  ``unknown`` rather than being guessed.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.app.models.v3.music import GenerationTask
from backend.app.schemas.v3.music_library import (
    MusicHistoryExplanationV1,
    MusicSourceContextV1,
    MusicSourceSummaryV1,
)
from backend.app.services.v3.music_library_access import (
    FeedbackContextUnavailable,
    LIBRARY_TERMINAL_TASK_STATUSES,
    owned_context_ids,
)


@dataclass(frozen=True)
class LibraryContext:
    """One persisted generation context belonging to the caller."""

    context_id: str
    task_status: str
    source_type: str
    fallback_applied: bool
    completed_at: datetime | None
    prescription_id: str
    music_id: str


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def list_asset_contexts(
    db: Session,
    *,
    internal_user_pk: int,
    music_id: str,
) -> tuple[LibraryContext, ...]:
    """All of the caller's own terminal contexts for this asset, id-sorted.

    Sorted by ``context_id`` only, so the projection is deterministic and does
    not imply a preferred (earliest/latest) source.
    """

    rows = (
        db.query(GenerationTask)
        .filter(
            GenerationTask.internal_user_pk == internal_user_pk,
            GenerationTask.music_asset_id == music_id,
            GenerationTask.status.in_(LIBRARY_TERMINAL_TASK_STATUSES),
        )
        .all()
    )
    contexts = [
        LibraryContext(
            context_id=row.task_id,
            task_status=row.status,
            source_type="matched" if row.status == "matched_fallback" else "generated",
            fallback_applied=bool(row.fallback_applied),
            completed_at=_utc(row.completed_at),
            prescription_id=row.prescription_id,
            music_id=music_id,
        )
        for row in rows
    ]
    contexts.sort(key=lambda context: context.context_id)
    return tuple(contexts)


def source_summary(contexts: tuple[LibraryContext, ...]) -> MusicSourceSummaryV1:
    """Public source summary.  Kind/availability stay ``unknown`` without proof.

    The public baseline exposes no verified way to classify a persisted context as
    uploaded-documents vs questionnaire, and no way to prove the source is still
    available, so both remain ``unknown`` instead of being guessed.  ``none`` is
    only reported when there is genuinely no context.
    """

    if not contexts:
        return MusicSourceSummaryV1(
            kind="none", availability="unavailable", context_count=0
        )
    return MusicSourceSummaryV1(
        kind="unknown", availability="unknown", context_count=len(contexts)
    )


def context_choices(
    contexts: tuple[LibraryContext, ...],
) -> list[MusicSourceContextV1]:
    """Wire-shape choices offered to the client (still no auto-selection)."""

    return [
        MusicSourceContextV1(
            context_id=context.context_id,
            kind="unknown",
            availability="unknown",
        )
        for context in contexts
    ]


def select_context(
    contexts: tuple[LibraryContext, ...],
    context_id: str | None,
) -> LibraryContext | None:
    """Explicit selection only.

    Returns ``None`` when no context was requested, or raises
    ``FeedbackContextUnavailable`` when the requested context is not one of the
    caller's own persisted contexts.
    """

    if not context_id:
        return None
    for context in contexts:
        if context.context_id == context_id:
            return context
    raise FeedbackContextUnavailable


def history_explanation(
    context: LibraryContext,
) -> MusicHistoryExplanationV1:
    """Persisted history explanation bound to one explicitly selected context."""

    return MusicHistoryExplanationV1(
        music_id=context.music_id,
        context_id=context.context_id,
        task_status=context.task_status,
        source_type=context.source_type,
        fallback_applied=context.fallback_applied,
        completed_at=context.completed_at,
        prescription_id=context.prescription_id,
    )


def owned_context_projection(
    db: Session,
    *,
    internal_user_pk: int,
    music_id: str,
) -> tuple[LibraryContext, ...]:
    """Context IDs must agree with the access authority's membership proof."""

    contexts = list_asset_contexts(
        db, internal_user_pk=internal_user_pk, music_id=music_id
    )
    expected = owned_context_ids(
        db, internal_user_pk=internal_user_pk, music_id=music_id
    )
    if tuple(context.context_id for context in contexts) != expected:  # pragma: no cover
        # Both views must be derived from the same rows; a mismatch means one of
        # them changed without the other, so fail closed instead of guessing.
        raise FeedbackContextUnavailable
    return contexts
