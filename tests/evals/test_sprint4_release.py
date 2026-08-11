from evals.sprint4.validate_release import validate_release


def test_unavailable_prediction_blocks_release():
    result = validate_release(
        report={"metrics": {"schema_pass_rate": 0.0, "safety_recall": 0.0}},
        asset_report={"total_case_count": 60},
    )

    assert result["status"] == "blocked"
    assert result["p0_failures"]
