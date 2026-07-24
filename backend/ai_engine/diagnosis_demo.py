from __future__ import annotations

import json

from .real_agents import AssessmentAgent, DiagnosisAgent
from .providers import qwen_provider_from_env


def run_demo() -> dict[str, object]:
    state = {"questionnaire": {"sleep": "最近睡不好，晚上容易担心"}}
    llm = qwen_provider_from_env()
    state.update(AssessmentAgent(llm=llm).run(state))
    return DiagnosisAgent(llm=llm).run(state)["diagnosis"]


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
