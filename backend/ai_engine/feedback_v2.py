from __future__ import annotations

from collections.abc import Mapping
import hashlib
from typing import Protocol

from pydantic import ValidationError

from backend.app.schemas.feedback_v2 import FeedbackV2Request


class FeedbackRepository(Protocol):
    def save_once(
        self,
        record: dict[str, object],
        preference_patch: dict[str, object],
    ) -> bool: ...


def submit_feedback_v2(
    payload: Mapping[str, object],
    repository: FeedbackRepository,
) -> dict[str, object]:
    """Persist an explicitly submitted V2 feedback record and personal patch."""
    if not isinstance(payload, Mapping):
        return _invalid("payload")

    try:
        request = FeedbackV2Request.model_validate(payload)
    except ValidationError as exc:
        location = exc.errors()[0].get("loc", ("payload",))
        return _invalid(str(location[0]) if location else "payload")

    feedback_id = _feedback_id(
        request.session_id,
        request.prescription_id,
    )
    record = request.model_dump(mode="json")
    record["feedback_id"] = feedback_id
    preference_patch = _preference_patch(request)
    response = _success_response(
        request,
        feedback_id=feedback_id,
        preference_patch=preference_patch,
    )
    try:
        inserted = repository.save_once(record, preference_patch)
    except Exception:
        return {
            "status": "failed",
            "feedback_id": feedback_id,
            "error_code": "PERSISTENCE_FAILED",
            "global_rule_update": False,
        }
    response["idempotent"] = not inserted
    return response


def _feedback_id(session_id: str, prescription_id: str) -> str:
    digest = hashlib.sha256(
        f"{session_id}:{prescription_id}".encode("utf-8")
    ).hexdigest()[:16]
    return f"fb_{digest}"


def _preference_patch(
    request: FeedbackV2Request,
) -> dict[str, object]:
    experience = request.experience
    return {
        "reduce_instruments": list(experience.disliked_instruments),
        "reduce_high_frequency": (
            "high_frequency" in experience.disliked_features
        ),
        "preserve_instruments": [],
        "favorite_tracks_add": (
            [request.music_id] if experience.favorite else []
        ),
    }


def _success_response(
    request: FeedbackV2Request,
    *,
    feedback_id: str,
    preference_patch: dict[str, object],
) -> dict[str, object]:
    subjective_change = _subjective_change(request)
    experience = request.experience
    reason_codes = []
    if experience.disliked_instruments:
        reason_codes.append("dislike_instrument")
    if "high_frequency" in experience.disliked_features:
        reason_codes.append("dislike_high_frequency")
    if experience.favorite:
        reason_codes.append("favorite_music")
    if request.post_state.change_label == "worse":
        reason_codes.append("subjective_state_worse")

    if request.post_state.change_label == "worse":
        action = "reduce_current_music"
    elif reason_codes:
        action = "adjust_personal_preference"
    else:
        action = "keep_personal_preference"

    warnings = []
    if (
        request.playback is not None
        and request.playback.listened_seconds < 30
    ):
        warnings.append("SHORT_EXPOSURE")
    return {
        "feedback_id": feedback_id,
        "agent_id": "feedback_agent",
        "status": "success",
        "idempotent": False,
        "subjective_change": subjective_change,
        "experience_summary": {
            "overall_rating": experience.overall_rating,
            "relaxation_rating": experience.relaxation_rating,
            "music_match_rating": experience.music_match_rating,
            "continue_use": experience.continue_use,
            "favorite": experience.favorite,
        },
        "decision": {
            "action": action,
            "reason_codes": reason_codes,
        },
        "personal_preference_patch": preference_patch,
        "global_rule_update": False,
        "warnings": warnings,
    }


def _subjective_change(
    request: FeedbackV2Request,
) -> dict[str, object]:
    pre_state = request.pre_state
    post_state = request.post_state
    tension_delta = post_state.tension - pre_state.tension
    body_delta = _optional_delta(
        pre_state.body_tension,
        post_state.body_tension,
    )
    fatigue_delta = _optional_delta(
        pre_state.mental_fatigue,
        post_state.mental_fatigue,
    )
    available = [
        value
        for value in (tension_delta, body_delta, fatigue_delta)
        if value is not None
    ]
    if available and all(value < 0 for value in available):
        summary = "用户主观感到紧张、身体紧绷和精神疲劳有所下降。"
    elif any(value > 0 for value in available):
        summary = "用户主观反馈显示部分状态评分有所升高。"
    else:
        summary = "用户主观反馈显示状态评分基本不变。"
    return {
        "tension_delta": tension_delta,
        "body_tension_delta": body_delta,
        "mental_fatigue_delta": fatigue_delta,
        "summary": summary,
    }


def _optional_delta(
    before: int | None,
    after: int | None,
) -> int | None:
    if before is None or after is None:
        return None
    return after - before


def _invalid(field: str) -> dict[str, object]:
    return {
        "status": "failed",
        "error_code": "INVALID_PAYLOAD",
        "field": field,
        "global_rule_update": False,
    }
