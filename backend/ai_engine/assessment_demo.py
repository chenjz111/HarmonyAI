from __future__ import annotations

import json

from .real_agents import AssessmentAgent


def run_demo() -> dict[str, object]:
    """Run a deterministic offline assessment demo."""
    return AssessmentAgent(llm=None).run(
        {"questionnaire": {"sleep": "recently poor sleep"}}
    )["assessment"]


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
