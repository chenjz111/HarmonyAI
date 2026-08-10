def confirmed_assessment_with_conflict():
    return {
        "assessment_id": "asmt-v21-dx-001",
        "status": "success",
        "requires_user_confirmation": False,
        "revision": 2,
        "emotion_profile": {
            "dimension_scores": {
                "tension_worry": 100,
                "irritability_anger": 75,
                "overthinking": 0,
            }
        },
        "evidence_items": [
            {
                "evidence_id": "ev-tension",
                "label": "tension_worry",
                "value": 4,
                "source_type": "questionnaire",
                "confirmed": True,
            },
            {
                "evidence_id": "ev-irritability",
                "label": "irritability_anger",
                "value": 3,
                "source_type": "questionnaire",
                "confirmed": True,
            },
            {
                "evidence_id": "ev-contradicting",
                "label": "tension_worry",
                "value": 0,
                "source_type": "narrative",
                "confirmed": True,
            },
        ],
        "conflicts": [],
        "degradation": {"active": False, "reason_codes": []},
    }


def unconfirmed_assessment():
    assessment = confirmed_assessment_with_conflict()
    assessment["requires_user_confirmation"] = True
    return assessment


def test_diagnosis_returns_candidates_with_supporting_and_contradicting_evidence():
    from backend.ai_engine.diagnosis_v2 import run_diagnosis_v21

    result = run_diagnosis_v21(confirmed_assessment_with_conflict(), provider=None)

    assert result["abstained"] is False
    candidate = result["candidate_tendencies"][0]
    assert candidate["supporting_evidence_ids"]
    assert candidate["contradicting_evidence_ids"]


def test_diagnosis_abstains_before_provider_when_assessment_is_unconfirmed():
    from backend.ai_engine.diagnosis_v2 import run_diagnosis_v21

    result = run_diagnosis_v21(unconfirmed_assessment(), provider=None)

    assert result["abstained"] is True
    assert result["abstain_reason"] == "ASSESSMENT_NOT_CONFIRMED"


def test_diagnosis_abstains_when_evidence_coverage_is_insufficient():
    from backend.ai_engine.diagnosis_v2 import run_diagnosis_v21

    assessment = confirmed_assessment_with_conflict()
    assessment["evidence_coverage_score"] = 0.2

    result = run_diagnosis_v21(assessment, provider=None)

    assert result["abstained"] is True
    assert result["abstain_reason"] == "INSUFFICIENT_EVIDENCE"
