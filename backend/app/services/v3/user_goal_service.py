"""V3.1 optional UserGoal service (Issue #99 step 4).

Stores the post-questionnaire healing aspiration on the session. It is a
simple (non-revisioned) session attribute — it does not bump input_revision,
does not write a session_input_revisions snapshot, and never feeds
FactEvidence / OrganEvidence.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.models.v3.understanding import QuestionnaireSubmissionV3
from backend.app.schemas.v3.common import AuthPrincipal, UserGoal
from backend.app.schemas.v3.user_goal import UserGoalReadModel
from backend.app.services.v3.activity_service import (
    _QUESTIONNAIRE_COMPLETE,
    _QUESTIONNAIRE_QUESTION_IDS,
)
from backend.app.services.v3.session_service import get_owned_session_row


class InvalidUserGoal(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _validate_active_questionnaire(db: Session, session_row) -> None:
    """A non-null UserGoal requires a complete, active Q1-Q10 submission."""
    submission_id = session_row.active_questionnaire_submission_id
    if submission_id is None:
        raise InvalidUserGoal(
            "QUESTIONNAIRE_REQUIRED", "请先完成10道状态问卷，再填写疗愈诉求。"
        )
    submission = (
        db.query(QuestionnaireSubmissionV3)
        .filter(
            QuestionnaireSubmissionV3.questionnaire_submission_id == submission_id,
            QuestionnaireSubmissionV3.internal_user_pk == session_row.user_id,
            QuestionnaireSubmissionV3.session_row_id == session_row.id,
        )
        .one_or_none()
    )
    if submission is None:
        raise InvalidUserGoal(
            "QUESTIONNAIRE_NOT_OWNED", "问卷提交不属于当前会话。"
        )
    answers = submission.answers_json or []
    if len(answers) != _QUESTIONNAIRE_COMPLETE:
        raise InvalidUserGoal(
            "QUESTIONNAIRE_INCOMPLETE", "需要完整提交10道状态问卷。"
        )
    answer_ids = {
        item.get("question_id") for item in answers if isinstance(item, dict)
    }
    if answer_ids != _QUESTIONNAIRE_QUESTION_IDS:
        raise InvalidUserGoal(
            "QUESTIONNAIRE_INCOMPLETE", "需要完整提交10道状态问卷（唯一题号）。"
        )


def submit_user_goal(
    db: Session,
    principal: AuthPrincipal,
    session_id: str,
    user_goal: UserGoal | None,
) -> UserGoalReadModel:
    session_row = get_owned_session_row(db, principal, session_id)
    if user_goal is not None:
        _validate_active_questionnaire(db, session_row)
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
