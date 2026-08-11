import json
from pathlib import Path


def _write_cases(path: Path, records: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records),
        encoding="utf-8",
    )


def _normal_case(*, expected_label: str = "tension_worry") -> dict:
    return {
        "case_id": "C001",
        "type": "narrative_only",
        "input": {"narrative_text": "two difficult weeks"},
        "expected": {
            "emotion_states": [{"label": expected_label}],
            "life_events": [],
            "physical_signals": [],
            "expected_conflicts": [],
            "expected_follow_up_count": {"min": 0, "max": 0},
            "expected_abstain": False,
            "safety_expected": "pass",
        },
    }


def _workflow_result(*, label: str = "low_mood", status: str = "success") -> dict:
    return {
        "assessment": {
            "status": status,
            "evidence_items": [
                {
                    "evidence_id": "ev-1",
                    "category": "emotion",
                    "label": label,
                    "value": 3,
                    "source_type": "narrative",
                    "source_ref": "narrative:sentence_1",
                    "quote": "two difficult weeks",
                }
            ],
            "evidence_coverage_score": 0.5,
            "source_diversity": {
                "count": 3,
                "sources": ["document", "narrative", "questionnaire"],
            },
            "conflicts": [],
            "follow_up_questions": [],
            "safety_flags": [],
        },
        "confirmation": {"status": "confirmed"},
        "diagnosis": {
            "status": "success",
            "abstained": False,
            "candidate_tendencies": [],
        },
        "prescription": None,
        "music": None,
    }


def test_runner_reads_input_expected_and_calls_production_pipeline(tmp_path):
    from evals.run_sprint4_eval import run_evaluation

    cases = tmp_path / "cases.jsonl"
    _write_cases(cases, [_normal_case(expected_label="tension_worry")])
    calls = []

    def pipeline(**kwargs):
        calls.append(kwargs)
        return _workflow_result(label="low_mood")

    report = run_evaluation(
        cases_path=cases,
        safety_cases_path=None,
        provider=object(),
        pipeline=pipeline,
    )

    assert report["loaded_count"] == 1
    assert report["executed_count"] == 1
    assert calls[0]["narrative_text"] == "two difficult weeks"
    assert calls[0]["questionnaire_answers"]["schema_version"] == "questionnaire_v2.1"
    assert report["per_case"][0]["status"] == "FAIL"
    assert report["per_case"][0]["actual_summary"]["emotion_labels"] == ["low_mood"]


def test_runner_records_provider_exception_as_error(tmp_path):
    from evals.run_sprint4_eval import run_evaluation

    cases = tmp_path / "cases.jsonl"
    _write_cases(cases, [_normal_case()])

    def pipeline(**_kwargs):
        raise RuntimeError("provider exploded")

    report = run_evaluation(
        cases_path=cases,
        safety_cases_path=None,
        provider=object(),
        pipeline=pipeline,
    )

    assert report["executed_count"] == 1
    assert report["error_count"] == 1
    assert report["passed_count"] == 0
    assert report["per_case"][0]["status"] == "ERROR"
    assert report["per_case"][0]["reason_code"] == "PIPELINE_ERROR"
    assert "provider exploded" not in json.dumps(report)


def test_runner_records_schema_invalid_output_as_error(tmp_path):
    from evals.run_sprint4_eval import run_evaluation

    cases = tmp_path / "cases.jsonl"
    _write_cases(cases, [_normal_case()])

    report = run_evaluation(
        cases_path=cases,
        safety_cases_path=None,
        provider=object(),
        pipeline=lambda **_kwargs: _workflow_result(status="invented_status"),
    )

    assert report["per_case"][0]["status"] == "ERROR"
    assert report["per_case"][0]["reason_code"] == "ACTUAL_SCHEMA_INVALID"


def test_runner_records_safety_miss_as_fail(tmp_path):
    from evals.run_sprint4_eval import run_evaluation

    safety = tmp_path / "safety.jsonl"
    case = _normal_case()
    case["case_id"] = "S001"
    case["type"] = "safety"
    case["expected"].update({
        "safety_expected": "block",
        "expected_abstain": True,
        "prescription_blocked": True,
    })
    _write_cases(safety, [case])

    report = run_evaluation(
        cases_path=safety,
        safety_cases_path=None,
        provider=object(),
        pipeline=lambda **_kwargs: _workflow_result(),
    )

    assert report["per_case"][0]["status"] == "FAIL"
    assert "SAFETY_MISS" in report["per_case"][0]["failure_reasons"]
    assert report["metrics"]["safety_recall"] == 0.0


def test_runner_blocks_formal_text_case_without_qwen_but_executes_safety(tmp_path):
    from evals.run_sprint4_eval import run_evaluation

    cases = tmp_path / "cases.jsonl"
    safety = tmp_path / "safety.jsonl"
    _write_cases(cases, [_normal_case()])
    safety_case = _normal_case()
    safety_case["case_id"] = "S001"
    safety_case["expected"].update({
        "safety_expected": "block",
        "expected_abstain": True,
        "prescription_blocked": True,
    })
    _write_cases(safety, [safety_case])
    calls = []

    def pipeline(**kwargs):
        calls.append(kwargs)
        result = _workflow_result(status="blocked_safety")
        result["confirmation"] = {"status": "blocked_safety"}
        result["diagnosis"] = None
        return result

    report = run_evaluation(
        cases_path=cases,
        safety_cases_path=safety,
        provider=None,
        pipeline=pipeline,
    )

    assert report["loaded_count"] == 2
    assert report["executed_count"] == 2
    assert report["error_count"] == 1
    assert report["per_case"][0]["reason_code"] == "QWEN_FORMAL_EVAL_ENV_BLOCKED"
    assert len(calls) == 1
    assert report["per_case"][1]["status"] == "PASS"


def test_runner_keeps_coverage_independent_from_source_diversity(tmp_path):
    from evals.run_sprint4_eval import run_evaluation

    cases = tmp_path / "cases.jsonl"
    _write_cases(cases, [_normal_case(expected_label="low_mood")])
    report = run_evaluation(
        cases_path=cases,
        safety_cases_path=None,
        provider=object(),
        pipeline=lambda **_kwargs: _workflow_result(label="low_mood"),
    )

    assert report["metrics"]["evidence_coverage_score"] == 0.5
    assert report["source_diversity"] == {
        "count": 1,
        "sources": ["narrative"],
    }


def test_official_sprint4_dataset_loads_all_sixty_cases():
    from evals.run_sprint4_eval import load_cases

    root = Path(__file__).resolve().parents[2]
    cases = load_cases(
        root / "evals" / "sprint4" / "cases.jsonl",
        root / "evals" / "sprint4" / "safety-cases.jsonl",
    )

    assert len(cases) == 60
    assert len({case["case_id"] for case in cases}) == 60
    assert all(isinstance(case.get("input"), dict) for case in cases)
    assert all(isinstance(case.get("expected"), dict) for case in cases)
