from __future__ import annotations

import json
import tempfile
from dataclasses import asdict
from pathlib import Path

from .chroma_store import ChromaKnowledgeStore, KnowledgeChunk
from .providers import KnowledgeHit


DEMO_CHUNKS_PATH = Path(__file__).resolve().parents[2] / "knowledge" / "demo_chunks.jsonl"


def load_demo_chunks(path: Path = DEMO_CHUNKS_PATH) -> list[KnowledgeChunk]:
    chunks: list[KnowledgeChunk] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            chunks.append(
                KnowledgeChunk(
                    chunk_id=record["chunk_id"],
                    text=record["text"],
                    metadata=record["metadata"],
                )
            )
    return chunks


def run_demo(persist_directory: Path | None = None) -> list[KnowledgeHit]:
    directory = persist_directory or Path(tempfile.mkdtemp(prefix="harmonyai-chroma-"))
    store = ChromaKnowledgeStore(directory)
    store.upsert(load_demo_chunks())
    return store.query("焦虑 角调", limit=3)


if __name__ == "__main__":
    print(json.dumps([asdict(hit) for hit in run_demo()], ensure_ascii=False, indent=2))
