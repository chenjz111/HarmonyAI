"""Validate the frozen Sprint 4 questionnaire and evaluation assets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


class AssetValidationError(ValueError):
    """Raised when a Sprint 4 asset is structurally invalid."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssetValidationError(f"invalid JSON file: {path}") from exc
    if not isinstance(value, dict):
        raise AssetValidationError(f"JSON root must be an object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise AssetValidationError(f"cannot read file: {path}") from exc

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AssetValidationError(
                f"invalid JSONL at {path}: line {line_number}"
            ) from exc
        if not isinstance(value, dict):
            raise AssetValidationError(
                f"JSONL record must be an object at {path}: line {line_number}"
            )
        records.append(value)
    return records


def _require_count(name: str, actual: int, expected: int, path: Path) -> None:
    if actual != expected:
        raise AssetValidationError(
            f"{name} count mismatch in {path}: expected {expected}, got {actual}"
        )


def _validate_cases(
    records: list[dict[str, Any]],
    path: Path,
    *,
    require_safety: bool,
    seen_ids: set[str],
) -> None:
    for index, record in enumerate(records, start=1):
        case_id = record.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise AssetValidationError(f"missing case_id in {path}: record {index}")
        if case_id in seen_ids:
            raise AssetValidationError(f"duplicate case_id in {path}: {case_id}")
        seen_ids.add(case_id)
        if not isinstance(record.get("input"), dict):
            raise AssetValidationError(f"missing input in {path}: case {case_id}")
        if not isinstance(record.get("expected"), dict):
            raise AssetValidationError(f"missing expected in {path}: case {case_id}")
        if require_safety and record.get("expected", {}).get("safety_expected") != "block":
            raise AssetValidationError(
                f"invalid safety_expected in {path}: case {case_id}"
            )


def validate_assets(
    questionnaire_path: Path,
    scoring_path: Path,
    cases_path: Path,
    safety_cases_path: Path,
) -> dict[str, object]:
    """Validate and summarize the frozen Sprint 4 asset set."""

    questionnaire = _read_json(Path(questionnaire_path))
    scoring = _read_json(Path(scoring_path))
    cases = _read_jsonl(Path(cases_path))
    safety_cases = _read_jsonl(Path(safety_cases_path))

    if questionnaire.get("schema_version") != "questionnaire_v2.1":
        raise AssetValidationError(
            f"invalid schema_version in {questionnaire_path}: expected questionnaire_v2.1"
        )
    if scoring.get("schema_version") != "questionnaire_scoring_v2.1":
        raise AssetValidationError(
            f"invalid schema_version in {scoring_path}: expected questionnaire_scoring_v2.1"
        )

    questions = questionnaire.get("questions")
    if not isinstance(questions, list):
        raise AssetValidationError(f"missing questions in {questionnaire_path}")
    _require_count("question", len(questions), 20, questionnaire_path)
    question_ids = [
        question.get("question_id")
        for question in questions
        if isinstance(question, dict)
    ]
    if len(question_ids) != 20 or len(set(question_ids)) != 20:
        raise AssetValidationError(f"duplicate or invalid question id in {questionnaire_path}")

    seen_ids: set[str] = set()
    _validate_cases(cases, Path(cases_path), require_safety=False, seen_ids=seen_ids)
    _validate_cases(
        safety_cases,
        Path(safety_cases_path),
        require_safety=True,
        seen_ids=seen_ids,
    )
    _require_count("case", len(cases), 55, cases_path)
    _require_count("safety case", len(safety_cases), 5, safety_cases_path)

    return {
        "question_count": len(questions),
        "case_count": len(cases),
        "safety_case_count": len(safety_cases),
        "total_case_count": len(cases) + len(safety_cases),
        "questionnaire_schema_version": questionnaire["schema_version"],
        "errors": [],
    }


def _default_paths(repo_root: Path) -> argparse.Namespace:
    return argparse.Namespace(
        questionnaire=repo_root / "knowledge/questionnaire-v2.1.json",
        scoring=repo_root / "knowledge/questionnaire-scoring-v2.1.json",
        cases=repo_root / "evals/sprint4/cases.jsonl",
        safety_cases=repo_root / "evals/sprint4/safety-cases.jsonl",
    )


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    defaults = _default_paths(repo_root)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questionnaire", type=Path, default=defaults.questionnaire)
    parser.add_argument("--scoring", type=Path, default=defaults.scoring)
    parser.add_argument("--cases", type=Path, default=defaults.cases)
    parser.add_argument("--safety-cases", type=Path, default=defaults.safety_cases)
    args = parser.parse_args()
    try:
        report = validate_assets(
            args.questionnaire,
            args.scoring,
            args.cases,
            args.safety_cases,
        )
    except AssetValidationError as exc:
        print(json.dumps({"errors": [str(exc)]}, ensure_ascii=False))
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
