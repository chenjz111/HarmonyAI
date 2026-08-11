import json
from pathlib import Path

from evals.sprint4.run_acceptance import run_acceptance


ROOT = Path(__file__).resolve().parents[2]


def test_acceptance_writes_machine_and_human_reports(tmp_path):
    report_json = tmp_path / "acceptance.json"
    report_markdown = tmp_path / "acceptance.md"

    result = run_acceptance(
        repo_root=ROOT,
        cases_path=ROOT / "evals/sprint4/cases.jsonl",
        safety_cases_path=ROOT / "evals/sprint4/safety-cases.jsonl",
        predictions_path=tmp_path / "predictions.jsonl",
        report_json=report_json,
        report_markdown=report_markdown,
        commands=[],
    )

    assert result["status"] == "blocked"
    assert report_json.exists()
    assert report_markdown.exists()
    assert "Gate 1" in report_markdown.read_text(encoding="utf-8")
    assert json.loads(report_json.read_text(encoding="utf-8"))["status"] == "blocked"
