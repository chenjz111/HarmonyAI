import json
from types import SimpleNamespace
from pathlib import Path

import evals.sprint4.run_acceptance as acceptance
from evals.sprint4.run_acceptance import DEFAULT_COMMANDS, run_acceptance


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


def test_command_summary_decodes_utf8_without_persisting_output(monkeypatch, tmp_path):
    observed = {}

    def fake_run(*args, **kwargs):
        observed.update(kwargs)
        return SimpleNamespace(returncode=0, stdout="构建完成", stderr="")

    monkeypatch.setattr(acceptance.subprocess, "run", fake_run)
    summaries = acceptance._command_summary(
        repo_root=tmp_path,
        commands=[{"name": "utf8", "command": "echo ok", "cwd": "."}],
    )

    assert observed["encoding"] == "utf-8"
    assert observed["errors"] == "replace"
    assert summaries == [{"name": "utf8", "return_code": 0, "output_line_count": 1}]


def test_default_python_gate_uses_workspace_test_runtime():
    command = str(DEFAULT_COMMANDS[0]["command"])
    assert "-p no:cacheprovider" in command
    assert "--basetemp artifacts/sprint4/pytest-tmp" in command
