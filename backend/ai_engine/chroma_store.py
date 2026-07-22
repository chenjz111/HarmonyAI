from __future__ import annotations

import json
import math
from dataclasses import dataclass
from hashlib import blake2b
from pathlib import Path
from typing import Mapping, Sequence

import chromadb

from .providers import KnowledgeHit


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    text: str
    metadata: Mapping[str, object]


class ChromaKnowledgeStore:
    def __init__(
        self,
        persist_directory: Path | str,
        collection_name: str = "harmony_knowledge",
    ) -> None:
        directory = Path(persist_directory)
        directory.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(directory))
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=None,
        )

    def upsert(self, chunks: Sequence[KnowledgeChunk]) -> None:
        if not chunks:
            return

        self._collection.upsert(
            ids=[chunk.chunk_id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            metadatas=[self._serialize_metadata(chunk.metadata) for chunk in chunks],
            embeddings=[self._embed(chunk.text) for chunk in chunks],
        )

    def count(self) -> int:
        return self._collection.count()

    def query(self, query_text: str, limit: int = 3) -> list[KnowledgeHit]:
        if not query_text.strip() or limit <= 0 or self.count() == 0:
            return []

        result = self._collection.query(
            query_embeddings=[self._embed(query_text)],
            n_results=min(limit, self.count()),
            include=["documents", "metadatas", "distances"],
        )
        documents = result["documents"][0]
        metadatas = result["metadatas"][0]
        distances = result["distances"][0]
        return [
            KnowledgeHit(
                text=document,
                metadata=dict(metadata or {}),
                score=float(distance),
            )
            for document, metadata, distance in zip(documents, metadatas, distances)
            if document is not None and distance is not None
        ]

    @staticmethod
    def _serialize_metadata(metadata: Mapping[str, object]) -> dict[str, str | int | float | bool]:
        serialized: dict[str, str | int | float | bool] = {}
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)):
                serialized[key] = value
            elif value is not None:
                serialized[key] = json.dumps(value, ensure_ascii=False, sort_keys=True)
        return serialized

    @staticmethod
    def _embed(text: str) -> list[float]:
        vector = [0.0] * 64
        for character in text:
            index = int.from_bytes(
                blake2b(character.encode("utf-8"), digest_size=2).digest(), "big"
            ) % len(vector)
            vector[index] += 1.0

        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude == 0:
            vector[0] = 1.0
            return vector
        return [value / magnitude for value in vector]
