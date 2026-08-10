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
    unsupported_conclusion_rate,
)


def run_evaluation(
    *,
    cases_path: str | Path,
    safety_cases_path: str | Path | None,
    output_path: str | Path | None = None,
) -> dict[str, object]:
    cases = _read_jsonl(Path(cases_path))
    safety_cases = _read_jsonl(Path(safety_cases_path)) if safety_cases_path else []
    report = _build_report(cases, safety_cases)
    if output_path is not None:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    return report


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
        gold = _mapping(case.get("gold"))
        schema_passes += int(predicted.get("status") in {
            "success",
            "degraded",
            "needs_follow_up",
            "blocked_safety",
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
        provider_error = case.get("provider_error")
        if isinstance(provider_error, dict):
            provider_errors.append(provider_error)

    safety_predicted = [
        _mapping(case.get("predicted")).get("status") == "blocked_safety"
        for case in safety_cases
    ]
    safety_gold = [
        _mapping(case.get("gold")).get("safety_blocked") is True
        for case in safety_cases
    ]
    evidence_counts = [
        len(
            {
                item.get("label")
                for item in _mapping(case.get("predicted")).get("evidence_items", [])
                if isinstance(item, dict)
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
        max(1, sum(max(1, len(_mapping(case.get("gold")).get("labels", []))) for case in cases)),
        source_types,
    )
    metrics = {
        "schema_pass_rate": schema_passes / len(cases) if cases else 1.0,
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
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    run_evaluation(
        cases_path=args.cases,
        safety_cases_path=args.safety_cases,
        output_path=args.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
