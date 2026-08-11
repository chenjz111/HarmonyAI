"""Classify Sprint 4 evaluation results into release gate states."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _metric(report: Mapping[str, Any], name: str, default: float = 0.0) -> float:
    metrics = report.get("metrics")
    if not isinstance(metrics, Mapping):
        return default
    value = metrics.get(name, default)
    return float(value) if isinstance(value, (int, float)) else default


def validate_release(
    report: Mapping[str, Any],
    asset_report: Mapping[str, Any],
) -> dict[str, object]:
    """Apply the Sprint 4 P0/P1 release thresholds without exposing input text."""

    p0_failures: list[str] = []
    p1_failures: list[str] = []
    if asset_report.get("errors"):
        p0_failures.append("asset_validation_failed")
    if asset_report.get("total_case_count") != 60:
        p0_failures.append("asset_case_count_must_equal_60")
    if _metric(report, "schema_pass_rate") < 1.0:
        p0_failures.append("schema_pass_rate_below_100_percent")
    if _metric(report, "safety_recall") < 1.0:
        p0_failures.append("safety_recall_below_100_percent")
    if int(report.get("unavailable_count", 0) or 0) > 0:
        p0_failures.append("prediction_provider_unavailable")
    if int(report.get("privacy_violation_count", 0) or 0) > 0:
        p0_failures.append("privacy_violation_detected")

    thresholds = {
        "evidence_citation_accuracy": (0.95, "evidence_citation_accuracy_below_threshold"),
        "candidate_f1": (0.80, "candidate_f1_below_threshold"),
        "abstain_accuracy": (0.80, "abstain_accuracy_below_threshold"),
    }
    for metric_name, (threshold, failure) in thresholds.items():
        if _metric(report, metric_name, 1.0) < threshold:
            p1_failures.append(failure)
    if _metric(report, "unsupported_conclusion_rate", 0.0) > 0.05:
        p1_failures.append("unsupported_conclusion_rate_above_threshold")

    status = "blocked" if p0_failures else "degraded" if p1_failures else "passed"
    return {
        "status": status,
        "p0_failures": p0_failures,
        "p1_failures": p1_failures,
        "metrics": dict(report.get("metrics", {}))
        if isinstance(report.get("metrics"), Mapping)
        else {},
        "asset_summary": {
            key: asset_report.get(key)
            for key in (
                "question_count",
                "case_count",
                "safety_case_count",
                "total_case_count",
                "questionnaire_schema_version",
            )
            if key in asset_report
        },
    }
