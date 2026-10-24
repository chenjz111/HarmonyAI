"""V3.1 optional UserGoal (疗愈诉求) contracts (Issue #99 step 4).

UserGoal is an optional post-questionnaire "healing aspiration" step, used
only by Agent3 for music design/personalization. It is never a source fact and
never enters FactEvidence / OrganEvidence. Uses the frozen UserGoalV31 shape
(custom-text-only is a valid submission; a skipped/empty step is None).
"""

from __future__ import annotations

from .common import V3BaseModel
from .flow_v31 import UserGoalSubmissionV31, UserGoalV31


class UserGoalSubmitRequest(V3BaseModel):
    # None means the whole step was skipped; empty dict maps to None.
    user_goal: UserGoalSubmissionV31 = None


class UserGoalReadModel(V3BaseModel):
    user_goal: UserGoalV31 | None
