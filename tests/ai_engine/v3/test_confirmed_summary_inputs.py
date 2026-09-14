"""Confirmed prose reaches real retrieval and provider transport boundaries."""
import asyncio
import json

from backend.ai_engine.v3.rag_store import VersionedRagStore
from backend.ai_engine.v3.v31_pipeline import execute_v31_ai_pipeline
from backend.ai_engine.v3.diagnosis_provider import DiagnosisProvider
from tests.ai_engine.v3.test_rag_store_v31 import FakeEmbedding, FakeClient, _manifest, _chunk, _query
from tests.ai_engine.v3.test_v31_pipeline import _snapshot, _confirmed_state, _mapping, _rules, _rag_result


def test_real_retrieval_embedding_receives_confirmed_text():
    embedding = FakeEmbedding()
    store = VersionedRagStore(persist_directory="unused", collection_name="authority_test", embedding_provider=embedding, client=FakeClient(), production=False)
    store.ingest(_manifest(), [_chunk()])
    result = store.query(_query(), confirmed_state_text="最近一周睡后恢复感不足，休息后缓解。")
    assert result.status == "success"
    assert "最近一周睡后恢复感不足，休息后缓解。" in embedding.texts[-1]


def test_pipeline_passes_authoritative_text_to_retrieval_and_provider():
    captured = {}
    class Rag:
        def query(self, query, *, confirmed_state_text=None):
            captured["retrieval_text"] = confirmed_state_text
            assert query.claim_codes == ["unrefreshing_sleep"]
            return _rag_result()
    class Backend:
        async def acomplete_json(self, system_prompt, user_prompt):
            captured["provider"] = json.loads(user_prompt)
            return {"status": "success", "candidate_tendencies": [{
                "syndrome_code": "syndrome_1", "display_name": "测试倾向", "relative_support": 0.8,
                "supporting_fact_ids": ["fact_1"], "contradicting_fact_ids": [],
                "knowledge_chunk_ids": ["chunk_1"], "reasoning_summary": "根据确认状态整理的倾向。",
            }], "abstained": False, "abstain_reason": None}
    provider = DiagnosisProvider(backend=Backend(), allowed_syndrome_codes={"syndrome_1"}, allowed_fact_ids={"fact_1"}, allowed_chunk_ids={"chunk_1"})
    text = "最近一周睡眠恢复感一般。"
    result = asyncio.run(execute_v31_ai_pipeline(confirmed_user_state=_confirmed_state(),
        assessment_snapshot={**_snapshot(), "confirmed_state_text": text}, rag_store=Rag(), diagnosis_provider=provider,
        tone_mapping=_mapping(), generation_parameter_rules=_rules()))
    assert result.diagnosis.status == "success"
    assert captured["retrieval_text"] == text
    assert captured["provider"]["confirmed_state_text"] == text
