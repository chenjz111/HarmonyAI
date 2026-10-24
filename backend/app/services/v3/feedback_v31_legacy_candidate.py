"""Explicit, sequential legacy compatibility harness for installed R1 SQLite.

No production router calls this module. Legacy submit retains internal commits;
this facade alone is not safe for enabling deletion alongside concurrent POSTs.
"""
from sqlalchemy import select

from backend.app.schemas.v3.me import FeedbackHistory
from backend.app.schemas.v3.feedback import FeedbackV3
from backend.drafts.s7_feedback_consent import migration
from backend.drafts.s7_feedback_consent.contracts import FeedbackGone, FeedbackContentUnverified
from backend.drafts.s7_feedback_consent.models import FeedbackCandidate
from . import feedback_service
from .feedback_v31_candidate_queries import visible_feedback_query


class CandidateSchemaUnavailable(RuntimeError):
    """An explicitly installed, intact R1 candidate is required."""


def _require_candidate(db):
    connection = db.connection()
    if connection.dialect.name != "sqlite":
        raise CandidateSchemaUnavailable("candidate compatibility requires verified SQLite")
    cursor = connection.connection.driver_connection.cursor()
    try:
        if not migration._existing(cursor):
            raise CandidateSchemaUnavailable("candidate schema is not installed")
    except migration.CandidateRejected:
        raise CandidateSchemaUnavailable("candidate schema verification failed") from None
    finally:
        cursor.close()


def list_legacy_history_candidate(db, principal) -> FeedbackHistory:
    _require_candidate(db)
    visible = set(db.scalars(visible_feedback_query(principal).with_only_columns(FeedbackCandidate.feedback_id)))
    history = feedback_service.list_feedback_history(db, principal)
    items = [item for item in history.items if item.feedback_id in visible]
    return FeedbackHistory(items=items, total=len(items))


def submit_legacy_feedback_candidate(db, principal, request, idempotency_key):
    if type(request) is not FeedbackV3:
        raise TypeError("validated exact V3.0 request required")
    _require_candidate(db)
    if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key.strip()) <= 128:
        raise ValueError("invalid idempotency key")
    key = idempotency_key.strip()
    table = FeedbackCandidate.__table__
    existing = db.execute(select(table.c.deleted_at, table.c.request_fingerprint).where(
        table.c.internal_user_pk == principal.internal_user_pk, table.c.idempotency_key == key,
    )).mappings().one_or_none()
    if existing is not None:
        if existing["deleted_at"] is not None:
            raise FeedbackGone("tombstone precedes legacy replay")
        if existing["request_fingerprint"] is not None:
            raise FeedbackContentUnverified("V3.1 feedback requires exact V3.1 replay")
    return feedback_service.submit_feedback(db, principal, request, key)
