"""Internal owner reads; never serialize ORM rows directly to HTTP."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.models.v3.feedback import FeedbackV3 as FeedbackRow
from .feedback_v31_service import FeedbackNotFound


def visible_feedback_query(principal: AuthPrincipal, *, music_id: str | None = None):
    statement = select(FeedbackRow).where(
        FeedbackRow.internal_user_pk == principal.internal_user_pk,
        FeedbackRow.deleted_at.is_(None),
    )
    if music_id is not None:
        statement = statement.where(FeedbackRow.music_asset_id == music_id)
    return statement.execution_options(populate_existing=True)


def get_owned_feedback(db: Session, *, principal: AuthPrincipal, feedback_id: str) -> FeedbackRow:
    row = db.scalar(visible_feedback_query(principal).where(FeedbackRow.feedback_id == feedback_id))
    if row is None:
        raise FeedbackNotFound("feedback not found")
    return row


def read_owned_feedback_page(
    db: Session, *, principal: AuthPrincipal, music_id: str | None = None, limit: int = 20,
) -> tuple[list[FeedbackRow], int]:
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer between 1 and 100")
    visible = visible_feedback_query(principal, music_id=music_id)
    total = db.scalar(select(func.count()).select_from(visible.subquery()))
    rows = list(db.scalars(visible.order_by(
        FeedbackRow.created_at.desc(), FeedbackRow.feedback_id.desc()).limit(limit)))
    return rows, int(total)
