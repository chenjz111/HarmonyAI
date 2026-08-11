import json
from pathlib import Path

import pytest

from evals.sprint4.generate_predictions import UnavailableAdapter, generate_predictions
from evals.sprint4.prediction_schema import PredictionValidationError, validate_prediction


ROOT = Path(__file__).resolve().parents[2]


def test_prediction_schema_rejects_missing_status():
    with pytest.raises(PredictionValidationError, match="status"):
        validate_prediction({"evidence_items": []})


def test_generator_writes_one_sanitized_prediction_per_case(tmp_path):
    output = tmp_path / "predictions.jsonl"

    report = generate_predictions(
        cases_path=ROOT / "evals/sprint4/cases.jsonl",
        safety_cases_path=ROOT / "evals/sprint4/safety-cases.jsonl",
        output_path=output,
        adapter=UnavailableAdapter(),
    )

    rows = [
        json.loads(line)
        for line in output.read_text(encoding="utf-8").splitlines()
    ]
    assert report["case_count"] == 55
    assert report["safety_case_count"] == 5
    assert len(rows) == 60
    assert all(row["predicted"]["status"] == "unavailable" for row in rows)
    assert all("narrative_text" not in row["predicted"] for row in rows)
