import json

import pytest


def test_eval_runner_writes_case_aggregates(tmp_path):
    from evals.run_sprint4_eval import run_evaluation

    cases = tmp_path / "cases.jsonl"
    cases.write_text(
        json.dumps(
            {
                "case_id": "case-001",
                "predicted": {
                    "status": "success",
                    "evidence_items": [
                        {"source_ref": "narrative:sentence_1"}
                    ],
                    "candidate_tendencies": [
                        {"supporting_evidence_ids": ["ev-1"]}
                    ],
                    "abstained": False,
                    "safety_flags": [],
                },
                "gold": {
                    "source_refs": ["narrative:sentence_1"],
                    "abstained": False,
                    "safety_blocked": False,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    report = run_evaluation(cases_path=cases, safety_cases_path=None)

    assert report["case_count"] == 1
    assert report["metrics"]["evidence_citation_accuracy"] == 1.0


def test_evaluation_rejects_cases_without_predictions(tmp_path):
    from evals.run_sprint4_eval import EvaluationInputError, run_evaluation

    cases = tmp_path / "cases.jsonl"
    cases.write_text('{"case_id":"C001","gold":{}}\n', encoding="utf-8")

    with pytest.raises(EvaluationInputError, match="predicted"):
        run_evaluation(cases_path=cases, safety_cases_path=None)
