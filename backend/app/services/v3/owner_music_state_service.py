"""Backend-owned owner music state: epochs, locking and shared transaction hooks.

``owner_music_state`` is the single owner-state row for the music library.  The
Sprint 7 boundary makes Backend the owner of this row and forbids Preference from
building a second one, so this module is the only place that mutates the epochs.

Transaction rules (docs/sprint7/S7_W2_IMPLEMENTATION_BOUNDARY.md):

- every function here participates in the **caller's** transaction and never
  calls ``commit()`` or ``rollback()``;
- reads never create the row (a GET must not write owner state);
- the row is created lazily by the first explicit write.

Concurrency: the epoch bump is an atomic ``UPDATE ... SET epoch = epoch + 1`` so a
lost update cannot happen even where ``SELECT ... FOR UPDATE`` is a no-op (SQLite
ignores row locks).  ``lock_owner_music_state`` still issues the row lock for
dialects that honour it.

The state row is created with a plain ``flush`` rather than a savepoint so that a
caller's ``rollback()`` always undoes it together with the rest of the
transaction.  Two callers creating the row at the same time therefore surface a
normal ``IntegrityError``; the caller owns the transaction and may treat it as a
retryable conflict, which is honest and keeps the row unique.
"""

from sqlalchemy import update
from sqlalchemy.orm import Session

from backend.app.models.v3.music_library import OwnerMusicState


def _load(db: Session, internal_user_pk: int) -> OwnerMusicState | None:
    return (
        db.query(OwnerMusicState)
        .filter(OwnerMusicState.owner_internal_user_pk == internal_user_pk)
        .one_or_none()
    )


def _create_row(db: Session, internal_user_pk: int) -> OwnerMusicState:
    """Insert the state row on the caller's transaction.

    Raises ``IntegrityError`` if another transaction created the row first; the
    caller decides whether that is a retry or a conflict.
    """

    row = OwnerMusicState(
        owner_internal_user_pk=internal_user_pk,
        library_epoch=0,
        feedback_evidence_epoch=0,
    )
    db.add(row)
    db.flush()
    return row


def lock_owner_music_state(db: Session, *, internal_user_pk: int) -> OwnerMusicState:
    """Return the locked owner state row, creating it on first explicit write.

    The row lock is held until the caller commits or rolls back.  This function
    does not commit: Preference and Backend must be able to share one transaction.
    """

    row = (
        db.query(OwnerMusicState)
        .filter(OwnerMusicState.owner_internal_user_pk == internal_user_pk)
        .with_for_update()
        .one_or_none()
    )
    if row is None:
        row = _create_row(db, internal_user_pk)
        row = (
            db.query(OwnerMusicState)
            .filter(OwnerMusicState.owner_internal_user_pk == internal_user_pk)
            .with_for_update()
            .one()
        )
    return row


def current_owner_music_state(
    db: Session, *, internal_user_pk: int
) -> OwnerMusicState | None:
    """Read-only lookup.  Returns ``None`` when the owner has no state yet."""

    return _load(db, internal_user_pk)


def library_epoch_for(db: Session, *, internal_user_pk: int) -> int:
    """Current pagination epoch.  Missing state reads as epoch 0 without writing."""

    row = _load(db, internal_user_pk)
    return 0 if row is None else int(row.library_epoch)


def feedback_evidence_epoch_for(db: Session, *, internal_user_pk: int) -> int:
    """Current feedback-evidence epoch.  Missing state reads as 0 without writing."""

    row = _load(db, internal_user_pk)
    return 0 if row is None else int(row.feedback_evidence_epoch)


def advance_library_epoch(db: Session, *, internal_user_pk: int) -> int:
    """Invalidate every outstanding library cursor for this owner.

    Real asset additions call this so a cursor issued before the addition cannot
    silently skip or duplicate the new asset.  Returns the new epoch.
    """

    lock_owner_music_state(db, internal_user_pk=internal_user_pk)
    db.execute(
        update(OwnerMusicState)
        .where(OwnerMusicState.owner_internal_user_pk == internal_user_pk)
        .values(library_epoch=OwnerMusicState.library_epoch + 1)
    )
    db.flush()
    row = _load(db, internal_user_pk)
    return 0 if row is None else int(row.library_epoch)


def advance_feedback_epoch(db: Session, *, internal_user_pk: int) -> int:
    """Bump the feedback-evidence epoch inside the caller's transaction.

    Preference calls this when consent/tombstone/clear changes evidence validity.
    Returns the new epoch.
    """

    lock_owner_music_state(db, internal_user_pk=internal_user_pk)
    db.execute(
        update(OwnerMusicState)
        .where(OwnerMusicState.owner_internal_user_pk == internal_user_pk)
        .values(
            feedback_evidence_epoch=OwnerMusicState.feedback_evidence_epoch + 1
        )
    )
    db.flush()
    row = _load(db, internal_user_pk)
    return 0 if row is None else int(row.feedback_evidence_epoch)
