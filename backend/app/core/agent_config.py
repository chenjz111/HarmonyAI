"""Agent wiring configuration for legacy V3.0 and frozen V3.1 boundaries.

The legacy ``get_knowledge_store``/``get_llm_provider`` functions retain their
V3.0 demo-compatible behavior. V3.1 callers must use the explicit readiness
gated factories below; those factories never load demo chunks or silently
switch to a mock provider.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path


class V31ReadinessFailure(RuntimeError):
    """Safe failure for a V3.1 real dependency that is not ready."""

    def __init__(self, error_code: str, safe_message: str = "V3.1 实时能力尚未就绪。") -> None:
        self.error_code = error_code
        self.safe_message = safe_message
        super().__init__(f"{error_code}: {safe_message}")

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


def get_v31_embedding_provider(environment: Mapping[str, str] | None = None):
    """Build the V3.1 approved embedding adapter without enabling demo mode."""
    from backend.ai_engine.v3.embedding_provider import embedding_provider_from_environment

    values = environment if environment is not None else os.environ
    return embedding_provider_from_environment(values)


def get_v31_provider_config(environment: Mapping[str, str] | None = None):
    """Return the one V3.1 readiness view used by all real factories."""
    from backend.ai_engine.v3.provider_config import V31ProviderConfig

    values = environment if environment is not None else os.environ
    return V31ProviderConfig.from_environment(values)


def _require_v31_real_config(environment: Mapping[str, str]):
    config = get_v31_provider_config(environment)
    if not config.real_agents:
        raise V31ReadinessFailure("V31_REAL_MODE_NOT_ENABLED")
    if config.readiness_error is not None:
        raise V31ReadinessFailure(config.readiness_error)
    return config


def get_v31_rag_store(environment: Mapping[str, str] | None = None, *, client=None):
    """Build the production-gated V3.1 RAG store; never consults demo data."""
    values = environment if environment is not None else os.environ
    config = _require_v31_real_config(values)
    manifest_path = values.get("RAG_CORPUS_MANIFEST_PATH", "").strip()
    chunks_path = values.get("RAG_CORPUS_CHUNKS_PATH", "").strip()
    if (
        not manifest_path
        or not Path(manifest_path).is_file()
        or not chunks_path
        or not Path(chunks_path).is_file()
    ):
        raise V31ReadinessFailure("RAG_CORPUS_NOT_CONFIGURED")
    from backend.ai_engine.v3.rag_ingestion import (
        ProductionCorpusNotReady,
        load_production_corpus,
    )
    from backend.ai_engine.v3.rag_store import RagStoreFailure, VersionedRagStore

    embedding_provider = get_v31_embedding_provider(values)
    if embedding_provider is None:
        raise V31ReadinessFailure("EMBEDDING_FACTORY_NOT_READY")
    try:
        manifest, chunks = load_production_corpus(manifest_path, chunks_path)
        store = VersionedRagStore(
            persist_directory=config.chroma_persist_directory,
            collection_name=config.chroma_collection,
            embedding_provider=embedding_provider,
            client=client,
            production=True,
        )
        store.ingest(manifest, chunks)
        return store
    except ProductionCorpusNotReady as error:
        raise V31ReadinessFailure(error.error_code, error.safe_message) from None
    except RagStoreFailure as error:
        raise V31ReadinessFailure(error.error_code, error.safe_message) from None


def get_v31_diagnosis_provider(
    environment: Mapping[str, str] | None = None,
    *,
    allowed_syndrome_codes: set[str],
    allowed_fact_ids: set[str],
    allowed_chunk_ids: set[str],
):
    """Build Qwen only after the shared V3.1 readiness gate passes."""
    values = environment if environment is not None else os.environ
    _require_v31_real_config(values)
    from backend.ai_engine.v3.diagnosis_provider import diagnosis_provider_from_environment

    provider = diagnosis_provider_from_environment(
        values,
        allowed_syndrome_codes=allowed_syndrome_codes,
        allowed_fact_ids=allowed_fact_ids,
        allowed_chunk_ids=allowed_chunk_ids,
    )
    if provider is None:
        raise V31ReadinessFailure("QWEN_FACTORY_NOT_READY")
    return provider
