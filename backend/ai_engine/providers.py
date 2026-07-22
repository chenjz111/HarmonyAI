from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol


class LLMProvider(Protocol):
    def complete(self, prompt: str) -> str:
        ...


@dataclass(frozen=True)
class KnowledgeHit:
    text: str
    metadata: dict[str, object]
    score: float
    distance: float | None = None


class VectorStore(Protocol):
    def search(self, query: str, limit: int = 5) -> list[KnowledgeHit]:
        ...


class FallbackLLMProvider:
    def complete(self, prompt: str) -> str:
        del prompt
        return "规则引擎已生成保守建议；结果仅供参考，不构成医疗诊断或治疗建议。"


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._documents: list[tuple[str, dict[str, str]]] = []

    def add(self, text: str, metadata: Mapping[str, str]) -> None:
        self._documents.append((text, dict(metadata)))

    def search(self, query: str, limit: int = 5) -> list[KnowledgeHit]:
        if not query.strip() or limit <= 0:
            return []

        query_tokens = set(query.replace("，", " ").split())
        if len(query_tokens) == 1:
            query_tokens.update(query_tokens.pop())

        hits = []
        for text, metadata in self._documents:
            score = len(query_tokens.intersection(set(text))) / max(len(query_tokens), 1)
            if score > 0:
                hits.append(KnowledgeHit(text, metadata, score))
        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:limit]
