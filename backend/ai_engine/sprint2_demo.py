"""Command-line demonstration of the Sprint 2 five-Agent stub workflow."""

from __future__ import annotations

import json

from .langgraph_workflow import run_stub_workflow


def run_demo() -> dict[str, object]:
    return run_stub_workflow(
        user_id="demo-user",
        session_id="sprint2-demo",
        emotion_scores={"anxiety": 82, "anger": 60},
    )


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
