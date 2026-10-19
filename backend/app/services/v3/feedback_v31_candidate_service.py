"""PF-1B isolated 0013 service slice; not registered in application routing.

The caller owns the write transaction. No implicit commit, policy decision,
receipt, production migration, or preference learning occurs here.
"""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.services.v3.owner_music_state_service import (
    advance_feedback_epoch,
    feedback_evidence_epoch_for,
)
from backend.drafts.s7_feedback_consent.contracts import lock_expected_epoch
from backend.drafts.s7_feedback_consent.models import FeedbackCandidate


class FeedbackNotFound(LookupError):
    """No feedback belonging to this principal can be disclosed."""


def list_owned_feedback(db: Session, principal: AuthPrincipal) -> list[FeedbackCandidate]:
    """Read-only owner listing; tombstones never appear."""
    return list(db.scalars(
        select(FeedbackCandidate).where(
            FeedbackCandidate.internal_user_pk == principal.internal_user_pk,
            FeedbackCandidate.deleted_at.is_(None),
        ).order_by(FeedbackCandidate.created_at.desc(), FeedbackCandidate.feedback_id.desc())
    ))


def tombstone_owned_feedback(
    db: Session, *, principal: AuthPrincipal, feedback_id: str,
    expected_epoch: int, now_utc: datetime,
) -> int:
    """Soft-delete once; return current epoch; caller begins/commits transaction."""
    if now_utc.tzinfo is None or now_utc.utcoffset() != timedelta(0):
        raise ValueError("tombstone time must be timezone-aware UTC")
    row = db.scalar(select(FeedbackCandidate).where(
        FeedbackCandidate.feedback_id == feedback_id,
        FeedbackCandidate.internal_user_pk == principal.internal_user_pk,
    ))
    if row is None:
        raise FeedbackNotFound("feedback not found")
    if row.deleted_at is not None:
        return feedback_evidence_epoch_for(db, internal_user_pk=principal.internal_user_pk)
    lock_expected_epoch(db, principal=principal, expected_epoch=expected_epoch)
    row.deleted_at = now_utc
    db.flush()
    return advance_feedback_epoch(db, internal_user_pk=principal.internal_user_pk)
