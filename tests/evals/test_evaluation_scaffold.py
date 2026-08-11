import json


def test_narrative_only_scaffold_does_not_count_as_user_questionnaire_evidence(tmp_path):
    from evals.run_sprint4_eval import run_evaluation

    cases = tmp_path / "cases.jsonl"
    cases.write_text(json.dumps({
        "case_id": "C001",
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
    }), encoding="utf-8")

    def pipeline(**_kwargs):
        return {
            "assessment": {
                "status": "success",
                "evidence_items": [
                    {
                        "evidence_id": "ev-q",
                        "category": "emotion",
                        "label": "calm_wellbeing",
                        "value": 0,
                        "polarity": "absent",
                        "source_type": "questionnaire",
                        "source_ref": "questionnaire:q10_calm_wellbeing",
                    },
                    {
                        "evidence_id": "ev-n",
                        "category": "emotion",
                        "label": "low_mood",
                        "value": 3,
                        "polarity": "present",
                        "source_type": "narrative",
                        "source_ref": "narrative:sentence_1",
                        "quote": "sleep poorly",
                    },
                ],
                "evidence_coverage_score": 0.5,
                "source_diversity": {
                    "count": 2,
                    "sources": ["narrative", "questionnaire"],
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

    report = run_evaluation(
        cases_path=cases,
        safety_cases_path=None,
        provider=object(),
        pipeline=pipeline,
    )

    assert report["metrics"]["evidence_citation_accuracy"] == 1.0
    assert report["source_diversity"] == {
        "count": 1,
        "sources": ["narrative"],
    }
