from __future__ import annotations

import json
import tempfile
from pathlib import Path

from .chroma_demo import load_demo_chunks
from .chroma_store import ChromaKnowledgeStore
from .real_agents import PrescriptionAgent


def run_demo() -> dict[str, object]:
    store = ChromaKnowledgeStore(Path(tempfile.mkdtemp(prefix="harmonyai-prescription-")))
    store.upsert(load_demo_chunks())
    return PrescriptionAgent(knowledge_store=store).run({
        "diagnosis": {
            "confidence": 0.55,
            "output": {"syndrome_diagnosis": {"primary": {"syndrome_id": "syd_001", "name": "肝郁化火"}}},
        }
    })["prescription"]


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
