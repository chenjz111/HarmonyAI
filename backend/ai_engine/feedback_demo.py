from __future__ import annotations

import json
import tempfile
from pathlib import Path

from .feedback_store import SQLiteFeedbackStore
from .real_agents import FeedbackAgent


def run_demo() -> dict[str, object]:
    store = SQLiteFeedbackStore(Path(tempfile.mkdtemp(prefix="harmonyai-feedback-") ) / "feedback.sqlite3")
    return FeedbackAgent(store).run({
        "run_id": "demo-run",
        "session_id": "feedback-demo",
        "user_id": "demo-user",
        "feedback": {"rating": 4, "comment": "舒缓"},
    })["feedback"]


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
