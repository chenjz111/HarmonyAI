from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.ai_engine.questionnaire_v2 import (
    QuestionnaireValidationError,
    score_questionnaire_v21,
)


def test_all_formal_questionnaire_cases_match_frozen_v21_contract():
    """Catch malformed formal inputs before an expensive provider run starts."""
    root = Path(__file__).resolve().parents[2]
    invalid: list[str] = []

    for path in (
        root / "evals" / "sprint4" / "cases.jsonl",
        root / "evals" / "sprint4" / "safety-cases.jsonl",
    ):
        for line in path.read_text(encoding="utf-8").splitlines():
            case = json.loads(line)
            raw = case["input"].get("questionnaire_answers")
            if not isinstance(raw, dict):
                continue
            envelope = {
                "schema_version": "questionnaire_v2.1",
                "time_window_days": 14,
                "answers": [
                    {"question_id": question_id, "value": value}
                    for question_id, value in raw.items()
                ],
            }
            try:
                score_questionnaire_v21(envelope)
            except QuestionnaireValidationError as exc:
                invalid.append(f"{case['case_id']}: {exc}")

    assert invalid == []


def test_runner_rejects_malformed_questionnaire_before_provider_execution(tmp_path):
    """A malformed formal case must fail at load time, not become a provider error."""
    from evals.run_sprint4_eval import load_cases

    root = Path(__file__).resolve().parents[2]
    source = json.loads(
        (root / "evals" / "sprint4" / "cases.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[50]
    )
    source["input"]["questionnaire_answers"]["q18_daily_impact"] = None
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(
        json.dumps(source, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="C051.*q18_daily_impact"):
        load_cases(cases_path, None)
