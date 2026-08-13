from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence


def evidence_coverage(
    evidence_dimensions: int,
    total_dimensions: int,
) -> float:
    """Calculate only the proportion of covered evidence dimensions."""
    if total_dimensions <= 0 or evidence_dimensions <= 0:
        return 0.0
    return min(1.0, evidence_dimensions / total_dimensions)


def source_diversity(source_types: Iterable[str]) -> dict[str, object]:
    """Describe source diversity without changing evidence coverage."""
    sources = sorted({source for source in source_types if isinstance(source, str)})
    return {"count": len(sources), "sources": sources}


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


def grounding_accuracy(
    evidence: Sequence[Mapping[str, object]],
    case_input: Mapping[str, object],
) -> float:
    """Measure whether each EvidenceItem can be traced to its declared input."""
    if not evidence:
        return 1.0
    grounded = 0
    for item in evidence:
        source_type = item.get("source_type")
        source_ref = item.get("source_ref")
        if not isinstance(source_ref, str) or not source_ref.startswith(f"{source_type}:"):
            continue
        if source_type == "questionnaire":
            if isinstance(case_input.get("questionnaire_answers"), Mapping):
                grounded += 1
            continue
        if source_type not in {"narrative", "document"}:
            continue
        source_text = case_input.get(f"{source_type}_text")
        quote = item.get("quote")
        if (
            isinstance(source_text, str)
            and isinstance(quote, str)
            and bool(quote)
            and quote in source_text
        ):
            grounded += 1
    return grounded / len(evidence)


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


def _micro_f1(pairs: Sequence[tuple[set[str], set[str]]]) -> float:
    true_positive = sum(len(predicted & gold) for predicted, gold in pairs)
    predicted_count = sum(len(predicted) for predicted, _gold in pairs)
    gold_count = sum(len(gold) for _predicted, gold in pairs)
    if predicted_count == 0 and gold_count == 0:
        return 1.0
    if predicted_count == 0 or gold_count == 0:
        return 0.0
    return 2 * true_positive / (predicted_count + gold_count)


def emotion_f1(pairs: Sequence[tuple[set[str], set[str]]]) -> float:
    return _micro_f1(pairs)


def event_f1(pairs: Sequence[tuple[set[str], set[str]]]) -> float:
    return _micro_f1(pairs)


def physical_f1(pairs: Sequence[tuple[set[str], set[str]]]) -> float:
    return _micro_f1(pairs)


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
