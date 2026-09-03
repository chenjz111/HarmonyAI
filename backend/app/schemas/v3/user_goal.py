"""V3.1 optional UserGoal (疗愈诉求) contracts (Issue #99 step 4).

UserGoal is an optional post-questionnaire "healing aspiration" step, used
only by Agent3 for music design/personalization. It is never a source fact and
never enters FactEvidence / OrganEvidence.
"""

from __future__ import annotations

from .common import UserGoal, V3BaseModel


class UserGoalSubmitRequest(V3BaseModel):
    # None means the whole step was skipped.
    user_goal: UserGoal | None = None


class UserGoalReadModel(V3BaseModel):
    user_goal: UserGoal | None
