"""Schema checks for sanitized Sprint 4 prediction records."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


ALLOWED_STATUSES = frozenset(
    {"success", "degraded", "needs_follow_up", "blocked_safety", "unavailable"}
)
_SENSITIVE_KEYS = frozenset(
    {
        "narrative_text",
        "document_text",
        "ocr_text",
        "raw_text",
        "original_text",
        "user_text",
        "prompt",
        "evidence_quote",
        "quote",
    }
)


class PredictionValidationError(ValueError):
    """Raised when a model prediction cannot cross the evaluation boundary."""


def _require_list(prediction: Mapping[str, Any], field: str) -> list[Any]:
    value = prediction.get(field)
    if not isinstance(value, list):
        raise PredictionValidationError(f"{field} must be a list")
    return value


def _reject_sensitive_keys(value: object, path: str = "prediction") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if key in _SENSITIVE_KEYS:
                raise PredictionValidationError(f"{path}.{key} contains user text")
            _reject_sensitive_keys(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_sensitive_keys(nested, f"{path}[{index}]")


def validate_prediction(prediction: Mapping[str, Any]) -> None:
    """Validate the public, non-narrative prediction shape."""

    if not isinstance(prediction, Mapping):
        raise PredictionValidationError("prediction must be an object")
    status = prediction.get("status")
    if not isinstance(status, str):
        raise PredictionValidationError("status is required")
    if status not in ALLOWED_STATUSES:
        raise PredictionValidationError(f"invalid status: {status}")
    evidence_items = _require_list(prediction, "evidence_items")
    candidates = _require_list(prediction, "candidate_tendencies")
    safety_flags = _require_list(prediction, "safety_flags")
    if not isinstance(prediction.get("abstained"), bool):
        raise PredictionValidationError("abstained must be a boolean")

    for index, item in enumerate(evidence_items):
        if not isinstance(item, Mapping):
            raise PredictionValidationError(f"evidence_items[{index}] must be an object")
        if "source_ref" in item and not isinstance(item["source_ref"], str):
            raise PredictionValidationError(f"evidence_items[{index}].source_ref must be a string")
        if "source_type" in item and not isinstance(item["source_type"], str):
            raise PredictionValidationError(f"evidence_items[{index}].source_type must be a string")

    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, Mapping):
            raise PredictionValidationError(
                f"candidate_tendencies[{index}] must be an object"
            )
        ids = candidate.get("supporting_evidence_ids")
        if ids is not None and (
            not isinstance(ids, list) or not all(isinstance(item, str) for item in ids)
        ):
            raise PredictionValidationError(
                f"candidate_tendencies[{index}].supporting_evidence_ids must be string list"
            )

    if not all(isinstance(flag, str) for flag in safety_flags):
        raise PredictionValidationError("safety_flags must contain strings")
    for field in ("reason_code", "error_code"):
        if field in prediction and (
            not isinstance(prediction[field], str) or not prediction[field]
        ):
            raise PredictionValidationError(f"{field} must be a non-empty string")
    _reject_sensitive_keys(prediction)


def sanitize_prediction(prediction: Mapping[str, Any]) -> dict[str, Any]:
    """Drop known raw-text fields before a prediction is persisted."""

    def sanitize(value: object) -> object:
        if isinstance(value, Mapping):
            return {
                key: sanitize(nested)
                for key, nested in value.items()
                if key not in _SENSITIVE_KEYS
            }
        if isinstance(value, list):
            return [sanitize(nested) for nested in value]
        return value

    result = sanitize(prediction)
    if not isinstance(result, dict):
        raise PredictionValidationError("prediction must be an object")
    return result
