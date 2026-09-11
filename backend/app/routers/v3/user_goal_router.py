"""V3.1 optional UserGoal endpoints (Issue #99 step 4)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.routers.v3.transport import V3APIError, v3_success
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.envelope import V3SuccessEnvelope
from backend.app.schemas.v3.user_goal import UserGoalReadModel, UserGoalSubmitRequest
from backend.app.services.v3.auth_service import get_current_v3_principal
from backend.app.services.v3.session_service import OwnedResourceNotFound
from backend.app.services.v3.user_goal_service import (
    InvalidUserGoal,
    get_user_goal,
    submit_user_goal,
)


router = APIRouter()


@router.put(
    "/sessions/{session_id}/user-goal",
    response_model=V3SuccessEnvelope[UserGoalReadModel],
)
def submit_user_goal_endpoint(
    session_id: str,
    body: UserGoalSubmitRequest,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[UserGoalReadModel]:
    try:
        return v3_success(
            submit_user_goal(db, principal, session_id, body.user_goal)
        )
    except OwnedResourceNotFound:
        raise V3APIError(404, "RESOURCE_NOT_FOUND", "未找到对应资源。") from None
    except InvalidUserGoal as error:
        raise V3APIError(422, error.code, error.message) from None


@router.get(
    "/sessions/{session_id}/user-goal",
    response_model=V3SuccessEnvelope[UserGoalReadModel],
)
def get_user_goal_endpoint(
    session_id: str,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[UserGoalReadModel]:
    try:
        return v3_success(get_user_goal(db, principal, session_id))
    except OwnedResourceNotFound:
        raise V3APIError(404, "RESOURCE_NOT_FOUND", "未找到对应资源。") from None
