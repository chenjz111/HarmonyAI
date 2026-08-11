import pytest

from evals.sprint4.asset_validation import AssetValidationError, validate_assets


ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]


def test_validate_assets_accepts_frozen_20_55_5_assets():
    report = validate_assets(
        questionnaire_path=ROOT / "knowledge/questionnaire-v2.1.json",
        scoring_path=ROOT / "knowledge/questionnaire-scoring-v2.1.json",
        cases_path=ROOT / "evals/sprint4/cases.jsonl",
        safety_cases_path=ROOT / "evals/sprint4/safety-cases.jsonl",
    )

    assert report["question_count"] == 20
    assert report["case_count"] == 55
    assert report["safety_case_count"] == 5
    assert report["total_case_count"] == 60
    assert report["errors"] == []


def test_validate_assets_rejects_duplicate_case_ids(tmp_path):
    cases = tmp_path / "cases.jsonl"
    cases.write_text(
        '{"case_id":"C001","input":{},"expected":{}}\n'
        '{"case_id":"C001","input":{},"expected":{}}\n',
        encoding="utf-8",
    )

    with pytest.raises(AssetValidationError, match="duplicate case_id"):
        validate_assets(
            questionnaire_path=ROOT / "knowledge/questionnaire-v2.1.json",
            scoring_path=ROOT / "knowledge/questionnaire-scoring-v2.1.json",
            cases_path=cases,
            safety_cases_path=ROOT / "evals/sprint4/safety-cases.jsonl",
        )
