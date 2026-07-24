from __future__ import annotations

import json

from .real_agents import AssessmentAgent
from .providers import qwen_provider_from_env


def run_demo() -> dict[str, object]:
    return AssessmentAgent(llm=qwen_provider_from_env()).run({"questionnaire": {"sleep": "最近睡不好，晚上容易担心"}})["assessment"]


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
