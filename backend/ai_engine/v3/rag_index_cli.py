"""Owner-executable builder for an approved V3.1 Chroma index."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
import os
from pathlib import Path

from backend.ai_engine.v3.rag_index_receipt import IndexReceipt, build_index_receipt
from backend.ai_engine.v3.rag_ingestion import (
    ProductionCorpusNotReady,
    load_production_corpus,
)
from backend.ai_engine.v3.rag_store import RagStoreFailure, VersionedRagStore


class IndexBuildFailure(RuntimeError):
    """Safe index-build failure without provider credentials or source text."""

    def __init__(self, error_code: str, safe_message: str) -> None:
        self.error_code = error_code
        self.safe_message = safe_message
        super().__init__(f"{error_code}: {safe_message}")


def build_index(
    *,
    manifest_path: str | Path,
    chunks_path: str | Path,
    persist_directory: str,
    collection_name: str,
    embedding_provider,
    client=None,
    receipt_path: str | Path | None = None,
) -> IndexReceipt:
    """Validate, ingest and count-check an approved corpus before writing receipt."""

    if getattr(embedding_provider, "dimension", None) != 1024:
        raise IndexBuildFailure(
            "EMBEDDING_DIMENSION_INVALID",
            "生产索引必须使用 1024 维 Embedding。",
        )
    try:
        manifest, chunks = load_production_corpus(manifest_path, chunks_path)
        store = VersionedRagStore(
            persist_directory=persist_directory,
            collection_name=collection_name,
            embedding_provider=embedding_provider,
            client=client,
            production=True,
        )
        store.ingest(manifest, chunks)
        if store.collection_count != manifest.chunk_count:
            raise IndexBuildFailure(
                "RAG_INDEX_COUNT_MISMATCH",
                "Chroma 索引数量与医学语料清单不一致。",
            )
        receipt = build_index_receipt(
            manifest,
            chunks,
            store.active_collection_name or collection_name,
        )
    except IndexBuildFailure:
        raise
    except ProductionCorpusNotReady as error:
        raise IndexBuildFailure(error.error_code, error.safe_message) from None
    except RagStoreFailure as error:
        raise IndexBuildFailure(error.error_code, error.safe_message) from None

    if receipt_path is not None:
        path = Path(receipt_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(receipt.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the approved V3.1 Chroma index.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--chunks", required=True)
    parser.add_argument("--chroma-dir", required=True)
    parser.add_argument("--collection", default="harmony_v31")
    parser.add_argument("--receipt", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    from backend.app.core.agent_config import get_v31_embedding_provider

    provider = get_v31_embedding_provider(os.environ)
    if provider is None:
        result = {
            "status": "readiness_failed",
            "error_code": "EMBEDDING_FACTORY_NOT_READY",
        }
        print(json.dumps(result, ensure_ascii=False))
        return 2
    try:
        receipt = build_index(
            manifest_path=args.manifest,
            chunks_path=args.chunks,
            persist_directory=args.chroma_dir,
            collection_name=args.collection,
            embedding_provider=provider,
            receipt_path=args.receipt,
        )
    except IndexBuildFailure as error:
        print(
            json.dumps(
                {"status": "failed", "error_code": error.error_code},
                ensure_ascii=False,
            )
        )
        return 1
    print(
        json.dumps(
            {
                "status": "success",
                "collection_name": receipt.collection_name,
                "chunk_count": receipt.chunk_count,
                "corpus_manifest_checksum": receipt.corpus_manifest_checksum,
                "index_checksum": receipt.index_checksum,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
