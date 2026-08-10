import json


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
