from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence


def evidence_coverage(
    evidence_dimensions: int,
    total_dimensions: int,
    source_types: Iterable[str],
) -> float:
    """Calculate the Sprint 4 evidence coverage score."""
    if total_dimensions <= 0 or evidence_dimensions <= 0:
        return 0.0
    dimension_ratio = min(1.0, evidence_dimensions / total_dimensions)
    source_factor = min(1.0, len(set(source_types)) / 3)
    return dimension_ratio * source_factor


def citation_accuracy(
    predictions: Sequence[Mapping[str, object]],
    gold_source_refs: set[str],
) -> float:
    if not predictions:
        return 1.0
    correct = sum(
        1
        for item in predictions
        if isinstance(item.get("source_ref"), str)
        and item["source_ref"] in gold_source_refs
    )
    return correct / len(predictions)


def unsupported_conclusion_rate(
    conclusions: Sequence[Mapping[str, object]],
) -> float:
    if not conclusions:
        return 0.0
    unsupported = sum(
        1
        for conclusion in conclusions
        if not isinstance(conclusion.get("evidence_ids"), list)
        or not conclusion["evidence_ids"]
    )
    return unsupported / len(conclusions)


def f1_score(predicted: set[str], gold: set[str]) -> float:
    if not predicted and not gold:
        return 1.0
    if not predicted or not gold:
        return 0.0
    true_positive = len(predicted & gold)
    precision = true_positive / len(predicted)
    recall = true_positive / len(gold)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def safety_recall(predicted_blocked: Sequence[bool], gold_blocked: Sequence[bool]) -> float:
    if len(predicted_blocked) != len(gold_blocked):
        raise ValueError("prediction and gold lengths must match")
    positive_cases = sum(gold_blocked)
    if positive_cases == 0:
        return 1.0
    true_positive = sum(
        predicted and gold
        for predicted, gold in zip(predicted_blocked, gold_blocked)
    )
    return true_positive / positive_cases


def abstain_accuracy(predicted: Sequence[bool], gold: Sequence[bool]) -> float:
    if len(predicted) != len(gold):
        raise ValueError("prediction and gold lengths must match")
    if not gold:
        return 1.0
    return sum(actual == expected for actual, expected in zip(predicted, gold)) / len(gold)


def provider_error_explainability(results: Sequence[Mapping[str, object]]) -> float:
    if not results:
        return 1.0
    explained = sum(
        1
        for result in results
        if isinstance(result.get("reason_code"), str)
        and isinstance(result.get("user_message"), str)
        and bool(result["user_message"])
    )
    return explained / len(results)
