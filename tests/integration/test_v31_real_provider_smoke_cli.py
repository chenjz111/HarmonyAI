"""Offline orchestration tests for the Owner-only V3.1 Real Smoke command."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).parents[2]


def _fixture():
    return json.loads(
        (ROOT / "tests/fixtures/v31-real-provider-smoke-input.json").read_text(
            encoding="utf-8"
        )
    )


def test_smoke_runs_fake_embedding_chroma_qwen_chain_with_safe_output():
    from backend.ai_engine.v3.diagnosis_provider import DiagnosisProvider
    from backend.ai_engine.v3.real_provider_smoke import run_real_provider_smoke
    from tests.ai_engine.v3.test_v31_pipeline import _mapping, _rag_result, _rules

    class Rag:
        chunk_checksums = {"chunk_1": "sha256:chunk"}
        manifest = SimpleNamespace(manifest_checksum="sha256:manifest")

        def query(self, query):
            del query
            return _rag_result()

    class Backend:
        model = "qwen-test"

        async def acomplete_json(self, system_prompt, user_prompt):
            del system_prompt, user_prompt
            return {
                "status": "success",
                "candidate_tendencies": [
                    {
                        "syndrome_code": "syndrome_1",
                        "display_name": "safe tendency",
                        "relative_support": 0.8,
                        "supporting_fact_ids": ["fact_1"],
                        "contradicting_fact_ids": [],
                        "knowledge_chunk_ids": ["chunk_1"],
                        "reasoning_summary": "grounded summary",
                    }
                ],
                "abstained": False,
                "abstain_reason": None,
            }

    provider = DiagnosisProvider(
        backend=Backend(),
        allowed_syndrome_codes={"syndrome_1"},
        allowed_fact_ids={"fact_1"},
        allowed_chunk_ids={"chunk_1"},
        medical_rule_version="medical-rules-v3.1-r1",
    )
    from tests.ai_engine.v3.test_v31_pipeline import _confirmed_state, _snapshot

    dependencies = SimpleNamespace(
        rag_store=Rag(),
        diagnosis_provider=provider,
        tone_mapping=_mapping(),
        generation_parameter_rules=_rules(),
        medical_rule_version="medical-rules-v3.1-r1",
    )
    receipt = {
        "collection_name": "harmony_v31_medical_v3.1_text-embedding-v4_1024_d1024",
        "knowledge_version": "medical_v3.1",
        "corpus_manifest_checksum": "sha256:manifest",
        "index_checksum": "sha256:index",
        "chunk_count": 1,
    }
    result = run_real_provider_smoke(
        config={
            "embedding_model": "text-embedding-v4",
            "embedding_dimension": 1024,
            "qwen_model": "qwen-test",
        },
        dependencies=dependencies,
        fixture={
            "confirmed_user_state": _confirmed_state().model_dump(mode="json"),
            "assessment_snapshot": _snapshot(),
        },
        receipt=receipt,
    )

    assert result["status"] == "NOT_REAL_VALIDATED"
    assert result["embedding_model"] == "text-embedding-v4"
    assert result["embedding_dimension"] == 1024
    assert result["retrieved_chunk_count"] == 1
    assert result["provider_status"] == "success"
    assert result["schema_validation"] == "passed"
    assert result["medical_rule_validation"] == "passed"
    assert "api_key" not in json.dumps(result).lower()


def test_smoke_missing_real_configuration_fails_without_mock(monkeypatch):
    from backend.ai_engine.v3.real_provider_smoke import (
        run_real_provider_smoke_from_environment,
    )
    from backend.app.core import agent_config

    monkeypatch.setenv("HARMONYAI_REAL_AGENTS", "true")
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_WORKSPACE_ID", raising=False)

    with pytest.raises(agent_config.V31ReadinessFailure, match="DASHSCOPE_PROVIDER_NOT_CONFIGURED"):
        run_real_provider_smoke_from_environment(
            manifest_path="approved-manifest.json",
            chunks_path="approved-chunks.json",
            receipt_path="receipt.json",
            fixture_path="fixture.json",
        )


def test_smoke_preserves_agent3_blocking_error_code(monkeypatch):
    from backend.ai_engine.v3 import real_provider_smoke
    from backend.ai_engine.v3.agent3 import Agent3Blocked
    from backend.ai_engine.v3.real_provider_smoke import (
        RealProviderSmokeFailure,
        run_real_provider_smoke,
    )

    async def blocked_pipeline(**kwargs):
        del kwargs
        raise Agent3Blocked("MUSIC_PARAMETER_ASSET_NOT_CONFIGURED")

    monkeypatch.setattr(real_provider_smoke, "execute_v31_ai_pipeline", blocked_pipeline)

    with pytest.raises(RealProviderSmokeFailure) as error:
        run_real_provider_smoke(
            config={
                "embedding_model": "text-embedding-v4",
                "embedding_dimension": 1024,
                "qwen_model": "qwen-test",
            },
            dependencies=SimpleNamespace(
                rag_store=object(),
                diagnosis_provider=object(),
                tone_mapping={},
                generation_parameter_rules={},
            ),
            fixture={
                "confirmed_user_state": _fixture()["confirmed_user_state"],
                "assessment_snapshot": _fixture()["assessment_snapshot"],
            },
            receipt={
                "collection_name": "collection",
                "knowledge_version": "knowledge",
                "corpus_manifest_checksum": "sha256:manifest",
                "index_checksum": "sha256:index",
                "chunk_count": 1,
            },
        )

    assert error.value.error_code == "MUSIC_PARAMETER_ASSET_NOT_CONFIGURED"


def _smoke_with_pipeline(
    monkeypatch,
    *,
    hits,
    status,
    attempts,
    real_validation=True,
    qwen_model="qwen3.6-plus-2026-04-02",
):
    from backend.ai_engine.v3 import real_provider_smoke
    from backend.ai_engine.v3.real_provider_smoke import run_real_provider_smoke

    async def fake_pipeline(**kwargs):
        del kwargs
        return SimpleNamespace(
            rag_result=SimpleNamespace(hits=hits),
            diagnosis_execution=SimpleNamespace(
                status=status,
                attempts=attempts,
                reason_code=None,
            ),
        )

    monkeypatch.setattr(real_provider_smoke, "execute_v31_ai_pipeline", fake_pipeline)
    return run_real_provider_smoke(
        config={
            "embedding_model": "text-embedding-v4",
            "embedding_dimension": 1024,
            "qwen_model": qwen_model,
        },
        dependencies=SimpleNamespace(
            rag_store=object(),
            diagnosis_provider=object(),
            tone_mapping={},
            generation_parameter_rules={},
        ),
        fixture={
            "confirmed_user_state": _fixture()["confirmed_user_state"],
            "assessment_snapshot": _fixture()["assessment_snapshot"],
        },
        receipt={
            "collection_name": "collection",
            "knowledge_version": "knowledge",
            "corpus_manifest_checksum": "sha256:manifest",
            "index_checksum": "sha256:index",
            "chunk_count": 1,
        },
        real_validation=real_validation,
    )


def test_real_smoke_fails_when_rag_has_no_approved_hits(monkeypatch):
    from backend.ai_engine.v3.real_provider_smoke import RealProviderSmokeFailure

    with pytest.raises(RealProviderSmokeFailure) as error:
        _smoke_with_pipeline(
            monkeypatch,
            hits=[],
            status="abstained",
            attempts=0,
        )

    assert error.value.error_code == "RAG_NO_APPROVED_HITS"


def test_real_smoke_fails_when_qwen_was_not_called(monkeypatch):
    from backend.ai_engine.v3.real_provider_smoke import RealProviderSmokeFailure

    with pytest.raises(RealProviderSmokeFailure) as error:
        _smoke_with_pipeline(
            monkeypatch,
            hits=[SimpleNamespace(chunk_id="chunk_1")],
            status="abstained",
            attempts=0,
        )

    assert error.value.error_code == "QWEN_NOT_CALLED"


def test_real_smoke_pass_requires_retrieval_provider_and_validation(monkeypatch):
    result = _smoke_with_pipeline(
        monkeypatch,
        hits=[SimpleNamespace(chunk_id="chunk_1")],
        status="abstained",
        attempts=1,
    )

    assert result["status"] == "REAL_SMOKE_PASSED"
    assert result["qwen_model"] == "qwen3.6-plus-2026-04-02"
    assert result["schema_validation"] == "passed"
    assert result["medical_rule_validation"] == "passed"
    serialized = json.dumps(result)
    assert "api-key-secret" not in serialized
    assert "workspace-secret" not in serialized


def test_real_smoke_fails_when_actual_qwen_model_is_not_reported(monkeypatch):
    from backend.ai_engine.v3.real_provider_smoke import RealProviderSmokeFailure

    with pytest.raises(RealProviderSmokeFailure) as error:
        _smoke_with_pipeline(
            monkeypatch,
            hits=[SimpleNamespace(chunk_id="chunk_1")],
            status="success",
            attempts=1,
            qwen_model="",
        )

    assert error.value.error_code == "QWEN_MODEL_NOT_REPORTED"
