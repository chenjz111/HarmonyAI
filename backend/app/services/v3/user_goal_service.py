"""V3.1 optional UserGoal service (Issue #99 step 4).

Stores the post-questionnaire healing aspiration on the session. It is a
simple (non-revisioned) session attribute — it does not bump input_revision,
does not write a session_input_revisions snapshot, and never feeds
FactEvidence / OrganEvidence.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.schemas.v3.common import AuthPrincipal, UserGoal
from backend.app.schemas.v3.user_goal import UserGoalReadModel
from backend.app.services.v3.session_service import get_owned_session_row


def submit_user_goal(
    db: Session,
    principal: AuthPrincipal,
    session_id: str,
    user_goal: UserGoal | None,
) -> UserGoalReadModel:
    session_row = get_owned_session_row(db, principal, session_id)
    session_row.user_goal_json = (
        user_goal.model_dump(mode="json") if user_goal is not None else None
    )
    db.commit()
    return UserGoalReadModel(user_goal=user_goal)


def get_user_goal(
    db: Session,
    principal: AuthPrincipal,
    session_id: str,
) -> UserGoalReadModel:
    session_row = get_owned_session_row(db, principal, session_id)
    if session_row.user_goal_json is None:
        return UserGoalReadModel(user_goal=None)
    return UserGoalReadModel(
        user_goal=UserGoal.model_validate(session_row.user_goal_json)
    )
