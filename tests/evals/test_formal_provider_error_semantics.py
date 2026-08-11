import json


def test_provider_degradation_from_production_pipeline_is_error_not_pass(tmp_path):
    from evals.run_sprint4_eval import run_evaluation

    cases = tmp_path / "cases.jsonl"
    cases.write_text(json.dumps({
        "case_id": "C001",
        "type": "narrative_only",
        "input": {"narrative_text": "sleep poorly"},
        "expected": {
            "emotion_states": [],
            "life_events": [],
            "physical_signals": [],
            "expected_conflicts": [],
            "expected_follow_up_count": {"min": 0, "max": 4},
            "expected_abstain": True,
            "safety_expected": "pass",
        },
    }), encoding="utf-8")

    def pipeline(**_kwargs):
        return {
            "assessment": {
                "status": "degraded",
                "evidence_items": [],
                "evidence_coverage_score": 0.0,
                "source_diversity": {"count": 0, "sources": []},
                "conflicts": [],
                "follow_up_questions": [],
                "safety_flags": [],
                "input_processing_status": {
                    "narrative": {"status": "unavailable"},
                    "document": {"status": "skipped"},
                    "questionnaire": {"status": "processed"},
                },
                "degradation": {
                    "active": True,
                    "reason_codes": ["READ_TIMEOUT"],
                },
            },
            "confirmation": {"status": "confirmed"},
            "diagnosis": {"status": "degraded", "abstained": True},
            "prescription": None,
            "music": None,
        }

    report = run_evaluation(
        cases_path=cases,
        safety_cases_path=None,
        provider=object(),
        pipeline=pipeline,
    )

    assert report["per_case"][0]["status"] == "ERROR"
    assert report["per_case"][0]["reason_code"] == "PROVIDER_ERROR"
    assert report["passed_count"] == 0
