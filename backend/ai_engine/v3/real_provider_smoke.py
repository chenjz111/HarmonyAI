"""Owner-only V3.1 real Provider smoke orchestration.

Automated tests may inject fake dependencies, but the environment entry point
never creates Mock Providers or hash embeddings.  Its output is intentionally
limited to safe identifiers, counts, versions and validation states.
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Mapping, Sequence
import json
import os
from pathlib import Path

from backend.ai_engine.v3.rag_index_receipt import (
    IndexReceipt,
    canonical_index_checksum,
)
from backend.ai_engine.v3.v31_pipeline import (
    V31PipelineBlocked,
    execute_v31_ai_pipeline,
)
from backend.app.schemas.v3.flow_v31 import ConfirmedUserState


class RealProviderSmokeFailure(RuntimeError):
    """A smoke precondition or non-contract provider result failed."""

    def __init__(self, error_code: str, safe_message: str = "Real Smoke 未通过。") -> None:
        self.error_code = error_code
        self.safe_message = safe_message
        super().__init__(f"{error_code}: {safe_message}")


def run_real_provider_smoke(
    *,
    config: Mapping[str, object],
    dependencies,
    fixture: Mapping[str, object],
    receipt: Mapping[str, object],
    real_validation: bool = False,
) -> dict[str, object]:
    """Run the existing V3.1 pipeline with injected boundaries.

    ``real_validation`` is false for automated fake-transport tests and true
    only for the environment command after readiness and receipt checks pass.
    """

    embedding_model = str(config.get("embedding_model") or "")
    embedding_dimension = int(config.get("embedding_dimension") or 0)
    qwen_model = str(config.get("qwen_model") or "")
    if embedding_model != "text-embedding-v4" or embedding_dimension != 1024:
        raise RealProviderSmokeFailure("PRODUCTION_EMBEDDING_NOT_APPROVED")
    required_receipt = ("collection_name", "knowledge_version", "corpus_manifest_checksum", "index_checksum", "chunk_count")
    if any(not receipt.get(field) for field in required_receipt):
        raise RealProviderSmokeFailure("RAG_INDEX_RECEIPT_INVALID")

    state_payload = fixture.get("confirmed_user_state")
    snapshot_payload = fixture.get("assessment_snapshot")
    if not isinstance(state_payload, Mapping) or not isinstance(snapshot_payload, Mapping):
        raise RealProviderSmokeFailure("SMOKE_FIXTURE_INVALID")
    try:
        state = ConfirmedUserState.model_validate(state_payload)
    except (TypeError, ValueError) as error:
        raise RealProviderSmokeFailure("SMOKE_FIXTURE_INVALID") from error
    snapshot = dict(snapshot_payload)
    # The index receipt, not the synthetic fixture, is authoritative for the
    # current corpus identity.
    snapshot["knowledge_version"] = receipt["knowledge_version"]
    snapshot["manifest_checksum"] = receipt["corpus_manifest_checksum"]
    snapshot.setdefault("embedding_version", "text-embedding-v4@1024")

    try:
        pipeline = asyncio.run(
            execute_v31_ai_pipeline(
                confirmed_user_state=state,
                assessment_snapshot=snapshot,
                rag_store=dependencies.rag_store,
                diagnosis_provider=dependencies.diagnosis_provider,
                tone_mapping=dependencies.tone_mapping,
                generation_parameter_rules=dependencies.generation_parameter_rules,
            )
        )
    except V31PipelineBlocked as error:
        raise RealProviderSmokeFailure(error.error_code) from None

    status = pipeline.diagnosis_execution.status
    if status not in {"success", "abstained"}:
        raise RealProviderSmokeFailure(
            pipeline.diagnosis_execution.reason_code or "DIAGNOSIS_FAILED"
        )
    called_provider = status == "success" or pipeline.diagnosis_execution.attempts > 0
    return {
        "status": "REAL_SMOKE_PASSED" if real_validation else "NOT_REAL_VALIDATED",
        "embedding_model": embedding_model,
        "embedding_dimension": embedding_dimension,
        "corpus_manifest_checksum": str(receipt["corpus_manifest_checksum"]),
        "index_checksum": str(receipt["index_checksum"]),
        "collection_name": str(receipt["collection_name"]),
        "retrieved_chunk_count": len(pipeline.rag_result.hits),
        "qwen_model": qwen_model,
        "provider_status": status,
        "schema_validation": "passed" if called_provider else "not_called",
        "medical_rule_validation": "passed" if called_provider else "not_called",
    }


def run_real_provider_smoke_from_environment(
    *,
    manifest_path: str | Path,
    chunks_path: str | Path,
    receipt_path: str | Path,
    fixture_path: str | Path,
) -> dict[str, object]:
    """Run smoke with environment-backed real factories and no fallback."""

    from backend.app.core.agent_config import (
        V31ReadinessFailure,
        get_v31_ai_pipeline_dependencies,
        get_v31_provider_config,
    )

    environment = dict(os.environ)
    config = get_v31_provider_config(environment)
    if not config.real_agents:
        raise V31ReadinessFailure("V31_REAL_MODE_NOT_ENABLED")
    if config.readiness_error is not None:
        raise V31ReadinessFailure(config.readiness_error)
    if not Path(manifest_path).is_file() or not Path(chunks_path).is_file():
        raise V31ReadinessFailure("RAG_CORPUS_NOT_CONFIGURED")
    try:
        receipt_payload = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
        fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
        receipt = IndexReceipt.model_validate(receipt_payload)
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as error:
        raise V31ReadinessFailure("RAG_INDEX_RECEIPT_INVALID") from error
    if receipt.index_checksum != canonical_index_checksum(receipt):
        raise V31ReadinessFailure("RAG_INDEX_RECEIPT_CHECKSUM_MISMATCH")

    environment["RAG_CORPUS_MANIFEST_PATH"] = str(manifest_path)
    environment["RAG_CORPUS_CHUNKS_PATH"] = str(chunks_path)
    dependencies = get_v31_ai_pipeline_dependencies(environment)
    store = dependencies.rag_store
    if (
        getattr(store, "active_collection_name", None) != receipt.collection_name
        or getattr(store.manifest, "manifest_checksum", None) != receipt.corpus_manifest_checksum
        or getattr(store, "collection_count", 0) != receipt.chunk_count
    ):
        raise V31ReadinessFailure("RAG_INDEX_RECEIPT_MISMATCH")
    return run_real_provider_smoke(
        config=config.safe_dict(),
        dependencies=dependencies,
        fixture=fixture,
        receipt=receipt.model_dump(mode="json"),
        real_validation=True,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Owner V3.1 real-provider smoke test.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--chunks", required=True)
    parser.add_argument("--index-receipt", required=True)
    parser.add_argument("--fixture", required=True)
    args = parser.parse_args(argv)
    try:
        result = run_real_provider_smoke_from_environment(
            manifest_path=args.manifest,
            chunks_path=args.chunks,
            receipt_path=args.index_receipt,
            fixture_path=args.fixture,
        )
    except Exception as error:
        error_code = getattr(error, "error_code", "REAL_SMOKE_FAILED")
        print(json.dumps({"status": "failed", "error_code": error_code}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
