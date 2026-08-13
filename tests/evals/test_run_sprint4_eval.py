import json


def test_eval_runner_writes_case_aggregates(tmp_path):
    from evals.run_sprint4_eval import run_evaluation

    cases = tmp_path / "cases.jsonl"
    output = tmp_path / "report.json"
    cases.write_text(
        json.dumps(
            {
                "case_id": "case-001",
                "type": "narrative_only",
                "input": {"narrative_text": "sleep poorly"},
                "expected": {
                    "emotion_states": [{"label": "low_mood"}],
                    "life_events": [],
                    "physical_signals": [],
                    "expected_conflicts": [],
                    "expected_follow_up_count": {"min": 0, "max": 0},
                    "expected_abstain": False,
                    "safety_expected": "pass",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    def pipeline(**_kwargs):
        return {
            "assessment": {
                "status": "success",
                "evidence_items": [{
                    "evidence_id": "ev-1",
                    "category": "emotion",
                    "label": "low_mood",
                    "value": 3,
                    "source_type": "narrative",
                    "source_ref": "narrative:sentence_1",
                    "quote": "sleep poorly",
                }],
                "evidence_coverage_score": 1.0,
                "source_diversity": {"count": 1, "sources": ["narrative"]},
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

    report = run_evaluation(
        cases_path=cases,
        safety_cases_path=None,
        output_path=output,
        provider=object(),
        pipeline=pipeline,
    )

    assert report["loaded_count"] == 1
    assert report["executed_count"] == 1
    assert report["passed_count"] == 1
    assert json.loads(output.read_text(encoding="utf-8"))["passed_count"] == 1
