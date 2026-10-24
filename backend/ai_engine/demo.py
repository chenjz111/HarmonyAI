from __future__ import annotations

import json
from pathlib import Path

from .models import WorkflowInput
from .prompt_engine import PromptEngine
from .workflow import run_workflow


def run_demo() -> dict[str, object]:
    project_root = Path(__file__).resolve().parents[2]
    result = run_workflow(
        WorkflowInput(
            user_id="demo-user",
            session_id="demo-session",
            emotion_scores={"anxiety": 82, "anger": 60},
        ),
        PromptEngine(project_root / "prompt" / "v1"),
    )
    return result.to_dict()


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
