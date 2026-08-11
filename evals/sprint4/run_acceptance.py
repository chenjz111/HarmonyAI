"""Run Sprint 4 release gates and write privacy-safe acceptance reports."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Sequence

from evals.run_sprint4_eval import EvaluationInputError, run_evaluation

from .asset_validation import AssetValidationError, validate_assets
from .validate_release import validate_release


DEFAULT_COMMANDS: tuple[dict[str, object], ...] = (
    {
        "name": "python_tests",
        "command": "py -m pytest -p no:cacheprovider --basetemp artifacts/sprint4/pytest-tmp tests/ -q",
        "cwd": ".",
    },
    {
        "name": "frontend_contract_tests",
        "command": "node --test tests/*.test.mjs",
        "cwd": "frontend",
    },
    {"name": "frontend_h5_build", "command": "npm run build:h5", "cwd": "frontend"},
)


def _command_summary(
    *,
    repo_root: Path,
    commands: Sequence[dict[str, object]],
) -> list[dict[str, object]]:
    summaries: list[dict[str, object]] = []
    for spec in commands:
        name = str(spec.get("name", "unnamed_command"))
        command = str(spec.get("command", ""))
        cwd = repo_root / str(spec.get("cwd", "."))
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=True,
                check=False,
            )
            combined = "\n".join(
                part for part in (completed.stdout, completed.stderr) if part
            )
            summaries.append(
                {
                    "name": name,
                    "return_code": completed.returncode,
                    "output_line_count": len(combined.splitlines()),
                }
            )
        except OSError:
            summaries.append(
                {"name": name, "return_code": -1, "output_line_count": 0}
            )
    return summaries


def _asset_failure(exc: Exception) -> dict[str, object]:
    return {
        "question_count": 0,
        "case_count": 0,
        "safety_case_count": 0,
        "total_case_count": 0,
        "errors": [str(exc)],
    }


def _render_markdown(result: dict[str, object]) -> str:
    gates = result.get("gates", {})
    gate_lines = []
    if isinstance(gates, dict):
        gate_lines = [f"- {name}: {status}" for name, status in gates.items()]
    release = result.get("release", {})
    release_status = release.get("status") if isinstance(release, dict) else "unknown"
    return "\n".join(
        [
            "# Sprint 4 Release Acceptance",
            "",
            f"Final status: `{result.get('status', 'unknown')}`",
            "",
            "## Gates",
            "",
            *gate_lines,
            "",
            f"Release gate: `{release_status}`",
            "",
            "## Metrics",
            "",
            "```json",
            json.dumps(result.get("metrics", {}), ensure_ascii=False, indent=2, sort_keys=True),
            "```",
            "",
            "## Command summaries",
            "",
            "Only command names, return codes and output line counts are retained; command output is not persisted.",
        ]
        + [
            f"- {item.get('name')}: return_code={item.get('return_code')}, lines={item.get('output_line_count')}"
            for item in result.get("commands", [])
            if isinstance(item, dict)
        ]
    ) + "\n"


def run_acceptance(
    *,
    repo_root: str | Path,
    cases_path: str | Path,
    safety_cases_path: str | Path,
    predictions_path: str | Path,
    report_json: str | Path,
    report_markdown: str | Path,
    commands: Sequence[dict[str, object]] | None = None,
) -> dict[str, object]:
    repo_root = Path(repo_root)
    cases_path = Path(cases_path)
    safety_cases_path = Path(safety_cases_path)
    predictions_path = Path(predictions_path)

    try:
        asset_report = validate_assets(
            repo_root / "knowledge/questionnaire-v2.1.json",
            repo_root / "knowledge/questionnaire-scoring-v2.1.json",
            cases_path,
            safety_cases_path,
        )
        asset_gate = "passed"
    except (AssetValidationError, OSError) as exc:
        asset_report = _asset_failure(exc)
        asset_gate = "blocked"

    evaluation_report: dict[str, object] = {
        "case_count": asset_report.get("case_count", 0),
        "safety_case_count": asset_report.get("safety_case_count", 0),
        "metrics": {"schema_pass_rate": 0.0, "safety_recall": 0.0},
        "unavailable_count": 1,
        "prediction_reason_codes": ["PREDICTION_PROVIDER_REQUIRED"],
    }
    evaluation_gate = "blocked"
    if asset_gate == "passed" and predictions_path.exists():
        try:
            evaluation_report = run_evaluation(
                cases_path=cases_path,
                safety_cases_path=safety_cases_path,
                predictions_path=predictions_path,
            )
            evaluation_gate = "passed"
        except (EvaluationInputError, OSError, ValueError):
            evaluation_gate = "blocked"

    release_report = validate_release(evaluation_report, asset_report)
    command_reports = _command_summary(
        repo_root=repo_root,
        commands=commands if commands is not None else DEFAULT_COMMANDS,
    )
    command_gate = "passed" if all(item["return_code"] == 0 for item in command_reports) else (
        "passed" if not command_reports else "blocked"
    )
    p0_failures = list(release_report.get("p0_failures", []))
    if asset_gate == "blocked" and "asset_validation_failed" not in p0_failures:
        p0_failures.append("asset_validation_failed")
    if evaluation_gate == "blocked" and "PREDICTION_PROVIDER_REQUIRED" not in p0_failures:
        p0_failures.append("PREDICTION_PROVIDER_REQUIRED")
    release_report["p0_failures"] = p0_failures
    if p0_failures:
        release_report["status"] = "blocked"
    elif release_report.get("p1_failures"):
        release_report["status"] = "degraded"
    else:
        release_report["status"] = "passed"

    final_status = "blocked" if p0_failures or command_gate == "blocked" else str(
        release_report["status"]
    )
    result: dict[str, object] = {
        "status": final_status,
        "gates": {
            "Gate 1 - assets": asset_gate,
            "Gate 2 - predictions": evaluation_gate,
            "Gate 3 - evaluation": evaluation_gate,
            "Gate 4 - release": release_report["status"],
            "Gate 5 - commands": command_gate,
        },
        "asset_summary": asset_report,
        "evaluation": evaluation_report,
        "release": release_report,
        "metrics": evaluation_report.get("metrics", {}),
        "commands": command_reports,
    }
    report_json = Path(report_json)
    report_markdown = Path(report_markdown)
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_markdown.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    report_markdown.write_text(_render_markdown(result), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--safety-cases", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--report-json", type=Path, required=True)
    parser.add_argument("--report-markdown", type=Path, required=True)
    parser.add_argument("--skip-command", action="store_true")
    args = parser.parse_args()
    result = run_acceptance(
        repo_root=args.repo,
        cases_path=args.cases,
        safety_cases_path=args.safety_cases,
        predictions_path=args.predictions,
        report_json=args.report_json,
        report_markdown=args.report_markdown,
        commands=[] if args.skip_command else None,
    )
    print(json.dumps({"status": result["status"], "gates": result["gates"]}, ensure_ascii=False))
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
