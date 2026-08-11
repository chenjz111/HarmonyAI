from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .metrics import (
    abstain_accuracy,
    citation_accuracy,
    evidence_coverage,
    f1_score,
    provider_error_explainability,
    safety_recall,
    source_diversity,
    unsupported_conclusion_rate,
)
from .sprint4.prediction_schema import PredictionValidationError, validate_prediction


class EvaluationInputError(ValueError):
    """Raised when an evaluation set is not fully covered by predictions."""


def run_evaluation(
    *,
    cases_path: str | Path,
    safety_cases_path: str | Path | None,
    output_path: str | Path | None = None,
    predictions_path: str | Path | None = None,
) -> dict[str, object]:
    cases = _read_jsonl(Path(cases_path))
    safety_cases = _read_jsonl(Path(safety_cases_path)) if safety_cases_path else []
    if predictions_path is not None:
        _attach_predictions(cases, safety_cases, _read_jsonl(Path(predictions_path)))
    else:
        _validate_embedded_predictions(cases, safety_cases)
    report = _build_report(cases, safety_cases)
    if output_path is not None:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    return report


def _validate_embedded_predictions(
    cases: list[dict[str, Any]],
    safety_cases: list[dict[str, Any]],
) -> None:
    for case in [*cases, *safety_cases]:
        if not isinstance(case.get("predicted"), dict):
            raise EvaluationInputError(
                f"case {case.get('case_id', '<unknown>')} is missing predicted"
            )
        try:
            validate_prediction(case["predicted"])
        except PredictionValidationError as exc:
            raise EvaluationInputError(
                f"invalid predicted for case {case.get('case_id', '<unknown>')}: {exc}"
            ) from exc


def _attach_predictions(
    cases: list[dict[str, Any]],
    safety_cases: list[dict[str, Any]],
    prediction_rows: list[dict[str, Any]],
) -> None:
    expected_cases = [*cases, *safety_cases]
    expected_ids = {
        case.get("case_id")
        for case in expected_cases
        if isinstance(case.get("case_id"), str)
    }
    predictions: dict[str, dict[str, Any]] = {}
    for row in prediction_rows:
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or case_id in predictions:
            raise EvaluationInputError("predictions contain an invalid or duplicate case_id")
        predicted = row.get("predicted")
        try:
            validate_prediction(predicted)
        except PredictionValidationError as exc:
            raise EvaluationInputError(f"invalid predicted for case {case_id}: {exc}") from exc
        predictions[case_id] = dict(predicted)

    missing = expected_ids - predictions.keys()
    extra = predictions.keys() - expected_ids
    if missing:
        raise EvaluationInputError(f"predictions missing case coverage: {len(missing)}")
    if extra:
        raise EvaluationInputError(f"predictions contain unknown case coverage: {len(extra)}")
    for case in expected_cases:
        case["predicted"] = predictions[case["case_id"]]


def _build_report(
    cases: list[dict[str, Any]],
    safety_cases: list[dict[str, Any]],
) -> dict[str, object]:
    citations: list[float] = []
    unsupported_claims: list[dict[str, object]] = []
    predicted_abstain: list[bool] = []
    gold_abstain: list[bool] = []
    predicted_labels: set[str] = set()
    gold_labels: set[str] = set()
    provider_errors: list[dict[str, object]] = []
    schema_passes = 0

    for case in cases:
        predicted = _mapping(case.get("predicted"))
        gold = _gold_mapping(case)
        schema_passes += int(predicted.get("status") in {
            "success",
            "degraded",
            "needs_follow_up",
            "blocked_safety",
            "unavailable",
        })
        refs = {
            ref for ref in gold.get("source_refs", []) if isinstance(ref, str)
        }
        evidence = predicted.get("evidence_items", [])
        citations.append(
            citation_accuracy(
                [item for item in evidence if isinstance(item, dict)],
                refs,
            )
        )
        candidates = predicted.get("candidate_tendencies", [])
        unsupported_claims.extend(
            {
                "evidence_ids": candidate.get("supporting_evidence_ids", [])
            }
            for candidate in candidates
            if isinstance(candidate, dict)
        )
        predicted_abstain.append(predicted.get("abstained") is True)
        gold_abstain.append(gold.get("abstained") is True)
        predicted_labels.update(
            candidate.get("id")
            for candidate in candidates
            if isinstance(candidate, dict) and isinstance(candidate.get("id"), str)
        )
        gold_labels.update(
            label for label in gold.get("labels", []) if isinstance(label, str)
        )
        provider_error = predicted.get("provider_error")
        if isinstance(provider_error, dict):
            provider_errors.append(provider_error)

    safety_predicted = [
        _mapping(case.get("predicted")).get("status") == "blocked_safety"
        for case in safety_cases
    ]
    schema_passes += sum(
        int(_mapping(case.get("predicted")).get("status") in {
            "success",
            "degraded",
            "needs_follow_up",
            "blocked_safety",
            "unavailable",
        })
        for case in safety_cases
    )
    safety_gold = [
        _gold_mapping(case).get("safety_blocked") is True
        for case in safety_cases
    ]
    evidence_counts = [
        len(
            {
                item.get("label")
                for item in _mapping(case.get("predicted")).get("evidence_items", [])
                if isinstance(item, dict) and isinstance(item.get("label"), str)
            }
        )
        for case in cases
    ]
    source_types = {
        item.get("source_type")
        for case in cases
        for item in _mapping(case.get("predicted")).get("evidence_items", [])
        if isinstance(item, dict) and isinstance(item.get("source_type"), str)
    }
    coverage = evidence_coverage(
        sum(evidence_counts),
        max(1, sum(max(1, len(_gold_mapping(case).get("labels", []))) for case in cases)),
    )
    status_counts: dict[str, int] = {}
    for case in [*cases, *safety_cases]:
        status = _mapping(case.get("predicted")).get("status")
        if isinstance(status, str):
            status_counts[status] = status_counts.get(status, 0) + 1
    metrics = {
        "schema_pass_rate": schema_passes / (len(cases) + len(safety_cases))
        if cases or safety_cases
        else 1.0,
        "evidence_citation_accuracy": sum(citations) / len(citations) if citations else 1.0,
        "unsupported_conclusion_rate": unsupported_conclusion_rate(unsupported_claims),
        "evidence_coverage_score": coverage,
        "candidate_f1": f1_score(predicted_labels, gold_labels),
        "abstain_accuracy": abstain_accuracy(predicted_abstain, gold_abstain),
        "safety_recall": safety_recall(safety_predicted, safety_gold),
        "provider_error_explainability": provider_error_explainability(provider_errors),
    }
    return {
        "case_count": len(cases),
        "safety_case_count": len(safety_cases),
        "metrics": metrics,
        "source_diversity": source_diversity(source_types),
        "prediction_status_counts": status_counts,
        "unavailable_count": status_counts.get("unavailable", 0),
    }


def _gold_mapping(case: dict[str, Any]) -> dict[str, Any]:
    explicit_gold = case.get("gold")
    if isinstance(explicit_gold, dict):
        return explicit_gold
    expected = _mapping(case.get("expected"))
    labels: list[str] = []
    for group in ("emotion_states", "sleep", "energy", "appetite"):
        values = expected.get(group, [])
        if isinstance(values, list):
            labels.extend(
                item["label"]
                for item in values
                if isinstance(item, dict) and isinstance(item.get("label"), str)
            )
    return {
        "labels": labels,
        "source_refs": set(),
        "abstained": expected.get("expected_abstain") is True,
        "safety_blocked": expected.get("safety_expected") == "block",
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        records.append(value)
    return records


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the offline Sprint 4 evaluation")
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--safety-cases", required=False, type=Path)
    parser.add_argument("--predictions", required=False, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    run_evaluation(
        cases_path=args.cases,
        safety_cases_path=args.safety_cases,
        predictions_path=args.predictions,
        output_path=args.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
