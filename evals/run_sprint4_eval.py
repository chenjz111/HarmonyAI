from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


from backend.ai_engine.questionnaire_v2 import (
    QuestionnaireValidationError,
    score_questionnaire_v21,
)
from backend.ai_engine.providers import async_qwen_provider_from_env
from backend.ai_engine.real_workflow import run_real_workflow_v21

from evals.metrics import (
    abstain_accuracy,
    emotion_f1,
    event_f1,
    grounding_accuracy,
    physical_f1,
    safety_recall,
    source_diversity,
    unsupported_conclusion_rate,
)


Pipeline = Callable[..., dict[str, object]]
_AUTO_PROVIDER = object()
_ASSESSMENT_STATUSES = {
    "success",
    "degraded",
    "needs_follow_up",
    "blocked_safety",
}
_EMOTION_LABELS = frozenset({
    "tension_worry",
    "calm_wellbeing",
    "emotional_recovery",
    "overthinking",
    "irritability_anger",
    "low_mood",
    "interest_loss",
    "fear_unease",
})
# NOTE: worry_control is intentionally excluded — scored=false, weight=0 per frozen contract.
# It is a qualitative dimension (Q04), not an emotion label for evaluation purposes.
_P0_THRESHOLDS = {
    "emotion_f1": (">=", 0.80),
    "event_f1": (">=", 0.75),
    "physical_f1": (">=", 0.80),
    "evidence_citation_accuracy": (">=", 0.95),
    "unsupported_conclusion_rate": ("<=", 0.05),
    "safety_recall": (">=", 1.0),
    "schema_pass_rate": (">=", 1.0),
}


def load_cases(
    cases_path: str | Path,
    safety_cases_path: str | Path | None,
) -> list[dict[str, Any]]:
    cases = _read_jsonl(Path(cases_path))
    safety_cases = _read_jsonl(Path(safety_cases_path)) if safety_cases_path else []
    records = [*cases, *safety_cases]
    identifiers: set[str] = set()
    for index, case in enumerate(records, start=1):
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError(f"case {index} must have a non-empty case_id")
        if case_id in identifiers:
            raise ValueError(f"duplicate case_id: {case_id}")
        if not isinstance(case.get("input"), Mapping):
            raise ValueError(f"{case_id} must contain input")
        if not isinstance(case.get("expected"), Mapping):
            raise ValueError(f"{case_id} must contain expected")
        identifiers.add(case_id)
        try:
            score_questionnaire_v21(_questionnaire_envelope(case["input"]))
        except QuestionnaireValidationError as exc:
            raise ValueError(
                f"{case_id} has invalid questionnaire_v2.1 data: {exc}"
            ) from exc
    return records


def run_evaluation(
    *,
    cases_path: str | Path,
    safety_cases_path: str | Path | None,
    output_path: str | Path | None = None,
    provider: object | None = _AUTO_PROVIDER,
    pipeline: Pipeline = run_real_workflow_v21,
    case_id: str | None = None,
    case_ids: Sequence[str] | None = None,
) -> dict[str, object]:
    cases = load_cases(cases_path, safety_cases_path)
    if case_id is not None and case_ids is not None:
        raise ValueError("case_id and case_ids are mutually exclusive")
    if case_ids is not None:
        by_id = {str(case["case_id"]): case for case in cases}
        requested = tuple(dict.fromkeys(value.strip() for value in case_ids if value.strip()))
        missing = [value for value in requested if value not in by_id]
        if missing:
            raise ValueError(f"unknown case_id: {missing[0]}")
        cases = [by_id[value] for value in requested]

    if case_id is not None:
        cases = [case for case in cases if case.get("case_id") == case_id]
        if not cases:
            raise ValueError(f"unknown case_id: {case_id}")

    formal_provider = (
        async_qwen_provider_from_env()
        if provider is _AUTO_PROVIDER
        else provider
    )
    results = [
        _execute_case(case, provider=formal_provider, pipeline=pipeline)
        for case in cases
    ]
    report = _build_report(cases, results, formal_provider)
    if output_path is not None:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    return report


def _execute_case(
    case: Mapping[str, Any],
    *,
    provider: object | None,
    pipeline: Pipeline,
) -> dict[str, object]:
    case_id = str(case["case_id"])
    case_type = str(case.get("type") or case.get("category") or "unknown")
    case_input = _mapping(case["input"])
    expected = _mapping(case["expected"])
    expects_safety_block = expected.get("safety_expected") == "block"

    if provider is None and _requires_qwen(case_input) and not expects_safety_block:
        return _error_result(
            case_id,
            case_type,
            expected,
            "QWEN_FORMAL_EVAL_ENV_BLOCKED",
        )

    try:
        workflow = pipeline(
            user_id=f"eval-user-{case_id}",
            session_id=f"eval-session-{case_id}",
            assessment_id=f"eval-assessment-{case_id}",
            questionnaire_answers=_questionnaire_envelope(case_input),
            assessment_confirmed=True,
            document_text=_optional_text(case_input.get("document_text")),
            narrative_text=_optional_text(case_input.get("narrative_text")),
            provider=provider,
            music_catalog=(),
        )
    except Exception:
        return _error_result(
            case_id,
            case_type,
            expected,
            "PIPELINE_ERROR",
        )

    if not _actual_schema_valid(workflow):
        return _error_result(
            case_id,
            case_type,
            expected,
            "ACTUAL_SCHEMA_INVALID",
        )

    assessment = _mapping(workflow.get("assessment"))
    if _provider_failed_for_input(assessment, case_input):
        return _error_result(
            case_id,
            case_type,
            expected,
            "PROVIDER_ERROR",
        )

    diagnosis = _mapping(workflow.get("diagnosis"))
    evidence = [
        _mapping(item)
        for item in assessment.get("evidence_items", [])
        if isinstance(item, Mapping)
    ]
    metric_evidence = _case_evidence(evidence, case_input)
    actual = _actual_fields(assessment, diagnosis, metric_evidence, workflow)
    expected_fields = _expected_fields(expected)
    failure_reasons = _compare_case(
        expected_fields,
        actual,
        expects_safety_block=expects_safety_block,
    )
    return {
        "case_id": case_id,
        "type": case_type,
        "status": "FAIL" if failure_reasons else "PASS",
        "reason_code": None,
        "failure_reasons": failure_reasons,
        "expected_summary": _safe_expected_summary(expected_fields),
        "actual_summary": _safe_actual_summary(actual),
        "_actual": actual,
        "_evidence": metric_evidence,
        "_case_input": case_input,
    }


def _build_report(
    cases: Sequence[Mapping[str, Any]],
    results: list[dict[str, object]],
    provider: object | None,
) -> dict[str, object]:
    comparable = [result for result in results if result["status"] != "ERROR"]
    normal_comparable = [
        result
        for result in comparable
        if _mapping(result.get("_actual")).get("expected_safety_block") is not True
    ]
    emotion_pairs = _field_pairs(normal_comparable, "emotion_labels")
    event_pairs = _field_pairs(normal_comparable, "life_events")
    physical_pairs = _field_pairs(normal_comparable, "physical_signals")
    grounding_scores = [
        grounding_accuracy(
            result.get("_evidence", []),  # type: ignore[arg-type]
            _mapping(result.get("_case_input")),
        )
        for result in normal_comparable
    ]
    conclusions = [
        {"evidence_ids": ids}
        for result in normal_comparable
        for ids in _mapping(result.get("_actual")).get("candidate_evidence_ids", [])
        if isinstance(ids, list)
    ]
    safety_results = [
        result
        for result in comparable
        if _mapping(result.get("_actual")).get("expected_safety_block") is True
    ]
    safety_predicted = [
        _mapping(result.get("_actual")).get("safety_blocked") is True
        for result in safety_results
    ]
    safety_gold = [True] * len(safety_results)
    predicted_abstain = [
        _mapping(result.get("_actual")).get("abstained") is True
        for result in normal_comparable
    ]
    expected_abstain = [
        _mapping(result.get("_actual")).get("expected_abstain") is True
        for result in normal_comparable
    ]
    coverage_values = [
        float(value)
        for result in normal_comparable
        if isinstance(
            value := _mapping(result.get("_actual")).get("evidence_coverage_score"),
            (int, float),
        )
    ]
    sources = {
        source
        for result in comparable
        for source in _mapping(result.get("_actual")).get("source_types", [])
        if isinstance(source, str)
    }
    schema_passes = sum(result["status"] != "ERROR" for result in results)
    metrics = {
        "emotion_f1": emotion_f1(emotion_pairs),
        "event_f1": event_f1(event_pairs),
        "physical_f1": physical_f1(physical_pairs),
        "evidence_citation_accuracy": (
            sum(grounding_scores) / len(grounding_scores)
            if grounding_scores
            else 0.0
        ),
        "unsupported_conclusion_rate": unsupported_conclusion_rate(conclusions),
        "safety_recall": safety_recall(safety_predicted, safety_gold),
        "schema_pass_rate": schema_passes / len(results) if results else 1.0,
        "abstain_accuracy": abstain_accuracy(predicted_abstain, expected_abstain),
        "evidence_coverage_score": (
            sum(coverage_values) / len(coverage_values)
            if coverage_values
            else 0.0
        ),
        "provider_failure_rate": (
            sum(result["status"] == "ERROR" for result in results) / len(results)
            if results
            else 0.0
        ),
    }
    threshold = _threshold_result(metrics)
    public_results = [
        {key: value for key, value in result.items() if not key.startswith("_")}
        for result in results
    ]
    return {
        "total_cases": len(cases),
        "loaded_count": len(cases),
        "executed_count": len(results),
        "passed_count": sum(result["status"] == "PASS" for result in results),
        "failed_count": sum(result["status"] == "FAIL" for result in results),
        "error_count": sum(result["status"] == "ERROR" for result in results),
        "safety_case_count": sum(
            _mapping(case.get("expected")).get("safety_expected") == "block"
            for case in cases
        ),
        "qwen_formal": _provider_summary(provider),
        "metrics": metrics,
        "source_diversity": source_diversity(sources),
        "threshold": threshold,
        "per_case": public_results,
    }


def _actual_fields(
    assessment: Mapping[str, object],
    diagnosis: Mapping[str, object],
    evidence: list[dict[str, object]],
    workflow: Mapping[str, object],
) -> dict[str, object]:
    active = [item for item in evidence if _is_active_evidence(item)]
    unresolved_topics = {
        str(item["topic"])
        for item in assessment.get("conflicts", [])
        if isinstance(item, Mapping)
        and isinstance(item.get("topic"), str)
        and item.get("resolution") in {"awaiting_user", "unresolved"}
    }
    emotions = {
        str(item["label"])
        for item in evidence
        if item.get("category") == "emotion"
        and _actual_emotion_present(item)
        and str(item["label"]) not in unresolved_topics
    }
    events: set[str] = set()
    physical: set[str] = set()
    for item in active:
        if item.get("category") == "life_event":
            value = item.get("value")
            label = item.get("label")
            if isinstance(value, str) and value:
                events.add(value)
            elif isinstance(label, str):
                events.add(label)
        if item.get("category") == "physical":
            value = item.get("value")
            if isinstance(value, list):
                physical.update(str(entry) for entry in value if entry != "none")
            elif isinstance(item.get("label"), str):
                physical.add(str(item["label"]))
    candidates = [
        _mapping(item)
        for item in diagnosis.get("candidate_tendencies", [])
        if isinstance(item, Mapping)
    ]
    assessment_status = str(assessment.get("status"))
    safety_blocked = (
        assessment_status == "blocked_safety"
        and workflow.get("diagnosis") is None
        and workflow.get("prescription") is None
        and workflow.get("music") is None
    )
    source_types = sorted({
        str(item["source_type"])
        for item in evidence
        if isinstance(item.get("source_type"), str)
    })
    return {
        "assessment_status": assessment_status,
        "emotion_labels": emotions,
        "life_events": events,
        "physical_signals": physical,
        "conflict_count": len(assessment.get("conflicts", [])),
        "follow_up_count": len(assessment.get("follow_up_questions", [])),
        "abstained": diagnosis.get("abstained") is True or not diagnosis,
        "safety_blocked": safety_blocked,
        "evidence_coverage_score": assessment.get("evidence_coverage_score"),
        "source_types": source_types,
        "candidate_evidence_ids": [
            list(candidate.get("supporting_evidence_ids", []))
            for candidate in candidates
        ],
    }


def _expected_fields(expected: Mapping[str, object]) -> dict[str, object]:
    emotions = {
        str(item["label"])
        for item in expected.get("emotion_states", [])
        if isinstance(item, Mapping) and _emotion_present(item)
    }
    events = {
        str(item["trigger"])
        for item in expected.get("life_events", [])
        if isinstance(item, Mapping) and isinstance(item.get("trigger"), str)
    }
    physical = {
        str(item)
        for item in expected.get("physical_signals", [])
        if isinstance(item, str) and item != "none"
    }
    follow_up = _mapping(expected.get("expected_follow_up_count"))
    return {
        "emotion_labels": emotions,
        "life_events": events,
        "physical_signals": physical,
        "conflict_count": len(expected.get("expected_conflicts", [])),
        "follow_up_min": int(follow_up.get("min", 0)),
        "follow_up_max": int(follow_up.get("max", 4)),
        "expected_abstain": expected.get("expected_abstain") is True,
        "expected_safety_block": expected.get("safety_expected") == "block",
    }


def _compare_case(
    expected: Mapping[str, object],
    actual: dict[str, object],
    *,
    expects_safety_block: bool,
) -> list[str]:
    actual["expected_abstain"] = expected["expected_abstain"]
    actual["expected_safety_block"] = expected["expected_safety_block"]
    if expects_safety_block:
        return [] if actual["safety_blocked"] is True else ["SAFETY_MISS"]
    failures = []
    for field in ("emotion_labels", "life_events", "physical_signals"):
        if actual[field] != expected[field]:
            failures.append(f"{field.upper()}_MISMATCH")
    if actual["conflict_count"] != expected["conflict_count"]:
        failures.append("CONFLICT_MISMATCH")
    follow_up_count = int(actual["follow_up_count"])
    if not int(expected["follow_up_min"]) <= follow_up_count <= int(expected["follow_up_max"]):
        failures.append("FOLLOW_UP_MISMATCH")
    if actual["abstained"] is not expected["expected_abstain"]:
        failures.append("ABSTAIN_MISMATCH")
    return failures


def _actual_schema_valid(workflow: object) -> bool:
    if not isinstance(workflow, Mapping):
        return False
    assessment = workflow.get("assessment")
    if not isinstance(assessment, Mapping):
        return False
    if assessment.get("status") not in _ASSESSMENT_STATUSES:
        return False
    evidence = assessment.get("evidence_items")
    if not isinstance(evidence, list) or any(not isinstance(item, Mapping) for item in evidence):
        return False
    diagnosis = workflow.get("diagnosis")
    if diagnosis is not None and (
        not isinstance(diagnosis, Mapping)
        or type(diagnosis.get("abstained")) is not bool
    ):
        return False
    return True


def _field_pairs(
    results: Sequence[Mapping[str, object]],
    field: str,
) -> list[tuple[set[str], set[str]]]:
    pairs = []
    for result in results:
        actual = _mapping(result.get("_actual"))
        expected = _mapping(result.get("expected_summary"))
        pairs.append((set(actual.get(field, set())), set(expected.get(field, []))))
    return pairs


def _threshold_result(metrics: Mapping[str, object]) -> dict[str, object]:
    failures = []
    for metric, (operator, target) in _P0_THRESHOLDS.items():
        value = float(metrics[metric])
        passed = value >= target if operator == ">=" else value <= target
        if not passed:
            failures.append({
                "metric": metric,
                "actual": value,
                "operator": operator,
                "target": target,
            })
    return {"status": "PASS" if not failures else "FAIL", "failures": failures}


def _questionnaire_envelope(case_input: Mapping[str, object]) -> dict[str, object]:
    raw = case_input.get("questionnaire_answers")
    if isinstance(raw, Mapping) and raw.get("schema_version") == "questionnaire_v2.1":
        return dict(raw)
    values = dict(raw) if isinstance(raw, Mapping) else _neutral_questionnaire()
    return {
        "schema_version": "questionnaire_v2.1",
        "time_window_days": 14,
        "answers": [
            {"question_id": question_id, "value": value}
            for question_id, value in values.items()
        ],
    }


def _neutral_questionnaire() -> dict[str, object]:
    """Transport scaffold for narrative-only cases; never derived from expected."""
    return {
        "q01_user_goal": "other",
        "q02_mood_weather": "clear",
        "q03_tension_worry": 2,
        "q04_worry_control": 2,
        "q05_overthinking": "waves",
        "q06_irritability_anger": 2,
        "q07_fear_unease": 2,
        "q08_low_mood": 2,
        "q09_interest_loss": 2,
        "q10_calm_wellbeing": 2,
        "q11_emotional_recovery": 2,
        "q12_sleep_disturbance": 2,
        "q13_unrefreshing_sleep": 2,
        "q14_low_energy": "half",
        "q15_appetite_change": {"direction": "none", "severity": 0},
        "q16_physical_signals": ["none"],
        "q17_duration": "recurrent_unclear",
        "q18_daily_impact": 2,
        "q19_self_harm": "never",
        "q20_emergency": ["none"],
    }


def _requires_qwen(case_input: Mapping[str, object]) -> bool:
    return bool(
        _optional_text(case_input.get("narrative_text"))
        or _optional_text(case_input.get("document_text"))
    )

def _provider_failed_for_input(
    assessment: Mapping[str, object],
    case_input: Mapping[str, object],
) -> bool:
    if assessment.get("status") == "blocked_safety":
        return False
    if not _requires_qwen(case_input):
        return False
    processing = _mapping(assessment.get("input_processing_status"))
    narrative = _mapping(processing.get("narrative"))
    if _optional_text(case_input.get("narrative_text")) and narrative and narrative.get("status") != "processed":
        return True
    degradation = _mapping(assessment.get("degradation"))
    reason_codes = degradation.get("reason_codes")
    return bool(
        degradation.get("active") is True
        and isinstance(reason_codes, list)
        and reason_codes

    )
def _case_evidence(
    evidence: Sequence[Mapping[str, object]],
    case_input: Mapping[str, object],
) -> list[dict[str, object]]:
    """Exclude only the neutral transport scaffold from formal metrics."""
    has_questionnaire = isinstance(case_input.get("questionnaire_answers"), Mapping)
    return [
        dict(item)
        for item in evidence
        if item.get("source_type") != "questionnaire" or has_questionnaire
    ]



def _emotion_present(item: Mapping[str, object]) -> bool:
    """Canonical emotion presence semantics, shared by expected and actual sides.

    Frozen Sprint 4 contract (Owner decision 2026-08-13):

    - Negative ``frequency_0_4`` emotions (``tension_worry``, ``overthinking``,
      ``irritability_anger``, ``fear_unease``, ``low_mood``, ``interest_loss``):
      ``value=0`` → ABSENT, ``value∈{1,2,3,4}`` → PRESENT.
    - ``emotional_recovery`` (single_choice, "分值越高表示恢复越困难"): ``value=0``
      → ABSENT, ``value≥1`` → PRESENT.
    - ``calm_wellbeing`` (reverse_scored=true): the *evidence* value is already
      reversed to ``4 - raw``, so evidence ``value=0`` → ABSENT ("fully calm"),
      ``value≥1`` → PRESENT.
    - ``worry_control`` is scored=false/weight=0 and excluded from
      ``_EMOTION_LABELS``.

    Presence and severity/frequency are distinct concepts: ``value=1/2`` means the
    symptom occurred less often but still occurred, so it is PRESENT — it must not
    be dropped merely because ``value < 3``. Severity/frequency is preserved in
    ``value`` and is never raised here.
    """
    label = item.get("label")
    if not isinstance(label, str) or label not in _EMOTION_LABELS:
        return False
    if item.get("negated") is True or item.get("polarity") == "absent":
        return False
    value = item.get("value")
    # A missing ``value`` (bare ``{"label": ...}``) means "listed as present".
    # An explicit zero/empty/neutral marker means ABSENT.
    if value == 0 or value in ("", "none"):
        return False
    if isinstance(value, list) and (not value or value == ["none"]):
        return False
    return True


def _actual_emotion_present(item: Mapping[str, object]) -> bool:
    """Actual-side emotion presence, with questionnaire salience.

    The expected ``emotion_states`` are *narrative/document-derived* — the
    annotation guide requires ``evidence_quote`` and "只标明确出现的情绪状态"
    (only clearly-appearing emotions). A questionnaire ``frequency_0_4`` value of
    1 ("偶尔", 1-3 days) or 2 ("有时", 4-7 days) is a *mild/background* self-report
    and does not, on its own, constitute a clearly-appearing emotion; the frozen
    annotation threshold for the emotion profile is value ≥ 3 ("经常/几乎每天").
    Those value-1/2 questionnaire emotions remain full-fidelity evidence in
    ``evidence_items`` — they are only excluded from the *label set* that
    ``emotion_f1`` compares against the narrative-derived gold labels.

    Narrative/document emotions are extracted by Qwen and are salient by
    construction, so they are present whenever ``_emotion_present`` holds.
    """
    if not _emotion_present(item):
        return False
    if item.get("source_type") == "questionnaire":
        value = item.get("value")
        return isinstance(value, int) and not isinstance(value, bool) and value >= 3
    return True


def _is_active_evidence(item: Mapping[str, object]) -> bool:
    if item.get("negated") is True or item.get("polarity") == "absent":
        return False
    value = item.get("value")
    if value in (None, 0, "", "none"):
        return False
    if isinstance(value, list) and (not value or value == ["none"]):
        return False
    return True


def _safe_expected_summary(expected: Mapping[str, object]) -> dict[str, object]:
    return {
        "emotion_labels": sorted(expected["emotion_labels"]),
        "life_events": sorted(expected["life_events"]),
        "physical_signals": sorted(expected["physical_signals"]),
        "conflict_count": expected["conflict_count"],
        "follow_up_range": [expected["follow_up_min"], expected["follow_up_max"]],
        "expected_abstain": expected["expected_abstain"],
        "expected_safety_block": expected["expected_safety_block"],
    }


def _safe_actual_summary(actual: Mapping[str, object]) -> dict[str, object]:
    return {
        "assessment_status": actual["assessment_status"],
        "emotion_labels": sorted(actual["emotion_labels"]),
        "life_events": sorted(actual["life_events"]),
        "physical_signals": sorted(actual["physical_signals"]),
        "conflict_count": actual["conflict_count"],
        "follow_up_count": actual["follow_up_count"],
        "abstained": actual["abstained"],
        "safety_blocked": actual["safety_blocked"],
        "evidence_coverage_score": actual["evidence_coverage_score"],
        "source_types": actual["source_types"],
    }


def _error_result(
    case_id: str,
    case_type: str,
    expected: Mapping[str, object],
    reason_code: str,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "type": case_type,
        "status": "ERROR",
        "reason_code": reason_code,
        "failure_reasons": [],
        "expected_summary": _safe_expected_summary(_expected_fields(expected)),
        "actual_summary": None,
    }


def _provider_summary(provider: object | None) -> dict[str, object]:
    if provider is None:
        return {
            "status": "BLOCKED",
            "reason_code": "QWEN_FORMAL_EVAL_ENV_BLOCKED",
            "provider": None,
            "model": None,
            "missing": ["endpoint", "key", "model_or_local_runtime"],
        }
    return {
        "status": "AVAILABLE",
        "reason_code": None,
        "provider": type(provider).__name__,
        "model": getattr(provider, "model", None),
        "missing": [],
    }


def _optional_text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the formal Sprint 4 evaluation through production code"
    )
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--safety-cases", required=False, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--case", required=False)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    report = run_evaluation(
        cases_path=args.cases,
        safety_cases_path=args.safety_cases,
        output_path=args.output,
        case_id=args.case,
    )
    summary = {
        key: report[key]
        for key in (
            "total_cases",
            "executed_count",
            "passed_count",
            "failed_count",
            "error_count",
            "qwen_formal",
            "metrics",
            "threshold",
        )
    }
    print(json.dumps(report if args.verbose else summary, ensure_ascii=False, indent=2))
    return 0 if report["threshold"]["status"] == "PASS" else 1  # type: ignore[index]


if __name__ == "__main__":
    raise SystemExit(main())
