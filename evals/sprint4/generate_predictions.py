"""Generate sanitized JSONL predictions for the Sprint 4 evaluation set."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Protocol

from .prediction_schema import sanitize_prediction, validate_prediction


class PredictionAdapter(Protocol):
    """Boundary for a real or test model provider."""

    def predict(self, case: dict[str, Any]) -> dict[str, Any]: ...


class UnavailableAdapter:
    """Explicit no-provider adapter used when a model endpoint is unavailable."""

    name = "unavailable"

    def predict(self, case: dict[str, Any]) -> dict[str, Any]:
        del case
        return {
            "status": "unavailable",
            "evidence_items": [],
            "candidate_tendencies": [],
            "abstained": True,
            "safety_flags": [],
            "reason_code": "PREDICTION_PROVIDER_REQUIRED",
        }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number} must contain an object")
        records.append(value)
    return records


def generate_predictions(
    *,
    cases_path: str | Path,
    safety_cases_path: str | Path,
    output_path: str | Path,
    adapter: PredictionAdapter,
) -> dict[str, object]:
    cases = _read_jsonl(Path(cases_path))
    safety_cases = _read_jsonl(Path(safety_cases_path))
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for case in [*cases, *safety_cases]:
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id or case_id in seen_ids:
            raise ValueError("prediction input contains an invalid or duplicate case_id")
        seen_ids.add(case_id)
        predicted = sanitize_prediction(adapter.predict(case))
        validate_prediction(predicted)
        rows.append(
            {
                "case_id": case_id,
                "type": case.get("type"),
                "predicted": predicted,
                "prediction_metadata": {
                    "adapter": getattr(adapter, "name", adapter.__class__.__name__),
                    "status": predicted["status"],
                },
            }
        )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return {
        "case_count": len(cases),
        "safety_case_count": len(safety_cases),
        "total_case_count": len(rows),
        "output_path": str(output),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--safety-cases", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = generate_predictions(
        cases_path=args.cases,
        safety_cases_path=args.safety_cases,
        output_path=args.output,
        adapter=UnavailableAdapter(),
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
