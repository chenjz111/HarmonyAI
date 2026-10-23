"""Signatures only: Backend implements, Preference consumes; no business writes."""
from typing import Protocol

from sqlalchemy.orm import Session

from backend.app.models.v3.music import GenerationTask, MusicAsset
from .models import OwnerMusicState


class SharedOwnerAccess(Protocol):
    """Caller owns transaction. No method commits; read does not create state.

    Authentication precedes all calls: owner is a server-derived users.id.
    Implementations must not treat these signatures as an authorization bypass.
    """

    def get_owner_state(self, db: Session, *, internal_user_pk: int) -> OwnerMusicState | None:
        """Pure read; absent means epochs 0/cutoff null, not INSERT."""
        ...

    def lock_owner_state(self, db: Session, *, internal_user_pk: int) -> OwnerMusicState:
        """Write transaction only: lock or race-safe initialize unique owner row."""
        ...

    def require_music_access(self, db: Session, *, internal_user_pk: int, music_id: str) -> MusicAsset:
        """Require owned asset or authorized terminal task; favorite/NULL not enough."""
        ...

    def require_music_context(self, db: Session, *, internal_user_pk: int, music_id: str, task_id: str) -> GenerationTask:
        """Require same owner+asset and succeeded/matched_fallback; never guess."""
        ...

    def advance_library_epoch(self, db: Session, *, internal_user_pk: int, expected_epoch: int) -> int:
        """Atomic CAS increment within same write transaction; conflict rejects."""
        ...

    def advance_feedback_epoch(self, db: Session, *, internal_user_pk: int, expected_epoch: int) -> int:
        """Delete/clear invalidation CAS in same transaction; no learning."""
        ...
