"""Agent wiring configuration — Sprint 2.

Controls whether API routers use deterministic stubs or real agents (Qwen + Chroma).
Set HARMONYAI_REAL_AGENTS=true to enable real agents.

Real agents gracefully fall back to rule-based logic when Qwen is not configured,
so they work offline even when enabled.
"""
from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------
_USE_REAL = os.getenv("HARMONYAI_REAL_AGENTS", "").strip().lower() in ("true", "1", "yes")


def use_real_agents() -> bool:
    return _USE_REAL


# ---------------------------------------------------------------------------
# Lazy-initialised singletons (created only when real agents are enabled)
# ---------------------------------------------------------------------------
_knowledge_store: object | None = None
_feedback_store: object | None = None
_data_dir: Path | None = None


def _get_data_dir() -> Path:
    global _data_dir
    if _data_dir is None:
        _data_dir = Path(__file__).resolve().parents[3] / "data"
        _data_dir.mkdir(parents=True, exist_ok=True)
    return _data_dir


def get_knowledge_store():
    """Return a ChromaKnowledgeStore (or None if real agents are disabled)."""
    global _knowledge_store
    if not _USE_REAL:
        return None
    if _knowledge_store is None:
        from backend.ai_engine.chroma_store import ChromaKnowledgeStore
        from backend.ai_engine.chroma_demo import load_demo_chunks

        store = ChromaKnowledgeStore(_get_data_dir() / "chroma")
        if store.count() == 0:
            store.upsert(load_demo_chunks())
        _knowledge_store = store
    return _knowledge_store


def get_feedback_store():
    """Return a SQLiteFeedbackStore (or None if real agents are disabled)."""
    global _feedback_store
    if not _USE_REAL:
        return None
    if _feedback_store is None:
        from backend.ai_engine.feedback_store import SQLiteFeedbackStore

        _feedback_store = SQLiteFeedbackStore(_get_data_dir() / "feedback.sqlite3")
    return _feedback_store


def get_llm_provider():
    """Return a QwenCompatibleProvider (or None if not configured)."""
    if not _USE_REAL:
        return None
    from backend.ai_engine.providers import qwen_provider_from_env

    return qwen_provider_from_env()
