from __future__ import annotations

import json

from .real_agents import AssessmentAgent, DiagnosisAgent


def run_demo() -> dict[str, object]:
    """Run a deterministic offline assessment-to-diagnosis demo."""
    state = {"questionnaire": {"sleep": "recently poor sleep"}}
    state.update(AssessmentAgent(llm=None).run(state))
    return DiagnosisAgent(llm=None).run(state)["diagnosis"]


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
