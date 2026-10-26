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

The non-MySQL ``lock_owner_music_state`` path creates with a plain ``flush``;
concurrent first creation can surface ``IntegrityError`` to its caller. The new
feedback CAS uses a conditional UPDATE and a narrow first-write upsert instead.
MySQL first acquires the unique-key write lock through a no-op upsert, avoiding
the absent-row gap-lock deadlock. No epoch is reset or advanced by that upsert.
Both paths retain caller-owned transaction completion: a rollback undoes state
creation together with business changes. The CAS does not add an idempotency
receipt or replace the future Feedback service's transaction coordinator.
"""

from sqlalchemy import inspect, update
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from backend.app.models.v3.music_library import OwnerMusicState


class FeedbackEpochConflict(RuntimeError):
    """The database no longer has the caller's expected feedback epoch."""


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

    if db.get_bind().dialect.name == 'mysql':
        # SELECT FOR UPDATE on an absent key takes a gap lock. Two first
        # writers can both hold it and then deadlock inserting the same owner.
        # Acquire the unique-key write lock first; an existing state is a
        # strict no-op, with no epoch reset/advance and no independent commit.
        statement=mysql_insert(OwnerMusicState).values(
            owner_internal_user_pk=internal_user_pk,library_epoch=0,feedback_evidence_epoch=0)
        db.execute(statement.on_duplicate_key_update(
            owner_internal_user_pk=statement.inserted.owner_internal_user_pk))
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


def compare_and_advance_feedback_epoch(
    db: Session, *, internal_user_pk: int, expected_epoch: int
) -> int:
    """Atomically advance an explicit feedback write, never a GET or replay.

    The caller owns BEGIN/COMMIT/rollback, business writes and idempotency. A
    successful return is NOT a commit receipt. Reusing the old expected epoch
    conflicts rather than bumping twice. Deadlock/SQLITE_BUSY/DB faults propagate;
    this helper neither retries an operation nor continues a failed transaction.

    SQLite serializes these writes; MySQL uses InnoDB conditional-update/unique
    key locking (real MySQL concurrency remains a separate validation Gate).
    No SELECT-before-unconditional-UPDATE, INSERT IGNORE, or hidden savepoint.
    """

    if type(internal_user_pk) is not int or internal_user_pk <= 0:
        raise ValueError('positive internal owner PK required')
    if type(expected_epoch) is not int or not 0 <= expected_epoch < 9223372036854775807:
        raise ValueError('incrementable nonnegative BIGINT epoch required')
    dialect = db.get_bind().dialect.name
    if dialect not in ('sqlite', 'mysql'):
        raise ValueError('feedback epoch CAS supports SQLite and MySQL only')
    key = db.identity_key(class_=OwnerMusicState, ident=(internal_user_pk,))
    cached = db.identity_map.get(key)
    if (any(isinstance(row, OwnerMusicState) and row.owner_internal_user_pk == internal_user_pk
            for row in db.new)
            or (cached is not None and (
                cached in db.deleted
                or inspect(cached).attrs.owner_internal_user_pk.history.has_changes()
                or inspect(cached).attrs.feedback_evidence_epoch.history.has_changes()))):
        raise ValueError('pending owner state conflicts with feedback CAS')
    table = OwnerMusicState.__table__
    statement = (
        table.update()
        .where(table.c.owner_internal_user_pk == internal_user_pk,
               table.c.feedback_evidence_epoch == expected_epoch)
        .values(feedback_evidence_epoch=table.c.feedback_evidence_epoch + 1)
    )
    with db.no_autoflush:
        changed = db.execute(statement).rowcount
        if changed == 0 and expected_epoch == 0:
            # Only an explicit first write may create state. Narrow conflict
            # handling preserves FK/CHECK errors and unrelated database faults.
            values = dict(owner_internal_user_pk=internal_user_pk,
                          library_epoch=0, feedback_evidence_epoch=0)
            if dialect == 'sqlite':
                creation = sqlite_insert(table).values(**values).on_conflict_do_nothing(
                    index_elements=[table.c.owner_internal_user_pk])
            else:
                creation = mysql_insert(table).values(**values).on_duplicate_key_update(
                    owner_internal_user_pk=internal_user_pk)
            db.execute(creation)
            changed = db.execute(statement).rowcount
    if changed != 1:
        raise FeedbackEpochConflict('feedback evidence epoch changed')
    if cached is not None:
        # Core SQL bypasses ORM synchronization: expire only this field, without
        # erasing pending library/cutoff work or trusting the old cached value.
        db.expire(cached, ['feedback_evidence_epoch'])
    return expected_epoch + 1
