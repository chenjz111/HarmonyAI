from __future__ import annotations

from collections.abc import Mapping
import math
from typing import Protocol


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

    validated = _validate_payload(payload)
    if isinstance(validated, str):
        return _invalid(validated)
    record, preference_patch = validated

    feedback_id = record["feedback_id"]
    assert isinstance(feedback_id, str)
    try:
        inserted = repository.save_once(record, preference_patch)
    except Exception:
        return {
            "status": "failed",
            "feedback_id": feedback_id,
            "error_code": "PERSISTENCE_FAILED",
            "global_rule_update": False,
        }
    if not inserted:
        return {
            "status": "success",
            "feedback_id": feedback_id,
            "idempotent": True,
            "global_rule_update": False,
        }

    before = record["before"]
    after = record["after"]
    assert isinstance(before, Mapping) and isinstance(after, Mapping)
    return {
        "status": "success",
        "feedback_id": feedback_id,
        "idempotent": False,
        "deltas": {
            field: before[field] - after[field]
            for field in ("tension", "body_tension", "fatigue")
        },
        "comment": record["comment"],
        "personal_preference_patch": preference_patch,
        "global_rule_update": False,
    }


def _validate_payload(
    payload: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]] | str:
    identifiers: dict[str, str] = {}
    for field in ("feedback_id", "session_id", "user_id"):
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            return field
        identifiers[field] = value.strip()

    before = _measurements(payload.get("before"), "before")
    if isinstance(before, str):
        return before
    after = _measurements(payload.get("after"), "after")
    if isinstance(after, str):
        return after

    rating = _bounded_number(payload.get("rating"), 1, 5)
    if rating is None:
        return "rating"
    relaxation = _bounded_number(payload.get("relaxation"), 0, 10)
    if relaxation is None:
        return "relaxation"
    match = _bounded_number(payload.get("match"), 0, 10)
    if match is None:
        return "match"

    raw_comment = payload.get("comment", "")
    if raw_comment is None:
        comment = ""
    elif isinstance(raw_comment, str):
        comment = raw_comment.strip()
    else:
        return "comment"

    favorite = payload.get("is_favorite", False)
    continue_listening = payload.get("continue_listening", False)
    if not isinstance(favorite, bool):
        return "is_favorite"
    if not isinstance(continue_listening, bool):
        return "continue_listening"
    disliked = _disliked_features(payload.get("disliked_features", []))
    if disliked is None:
        return "disliked_features"

    track_id = payload.get("track_id")
    if favorite and (not isinstance(track_id, str) or not track_id.strip()):
        return "track_id"
    preference_patch = {
        "favorite_track_ids": [track_id.strip()] if favorite else [],
        "continue_listening": continue_listening,
        "disliked_features": disliked,
    }
    return (
        {
            **identifiers,
            "before": before,
            "after": after,
            "rating": rating,
            "relaxation": relaxation,
            "match": match,
            "comment": comment,
        },
        preference_patch,
    )


def _measurements(
    value: object,
    container: str,
) -> dict[str, int | float] | str:
    if not isinstance(value, Mapping):
        return container
    measurements: dict[str, int | float] = {}
    for field in ("tension", "body_tension", "fatigue"):
        score = _bounded_number(value.get(field), 0, 10)
        if score is None:
            return field
        measurements[field] = score
    return measurements


def _bounded_number(value: object, minimum: int, maximum: int) -> int | float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    if not math.isfinite(value):
        return None
    if value < minimum or value > maximum:
        return None
    return value


def _disliked_features(value: object) -> list[str] | None:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return None
    return [item.strip() for item in value if item.strip()]


def _invalid(field: str) -> dict[str, object]:
    return {
        "status": "failed",
        "error_code": "INVALID_PAYLOAD",
        "field": field,
        "global_rule_update": False,
    }
