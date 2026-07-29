import json

from backend.ai_engine.providers import QwenCompatibleProvider, qwen_provider_from_env
from backend.ai_engine.providers import KnowledgeHit
from backend.ai_engine.real_agents import (
    AssessmentAgent,
    DiagnosisAgent,
    FeedbackAgent,
    PrescriptionAgent,
)
from backend.ai_engine.feedback_store import SQLiteFeedbackStore


class FakeJsonLLM:
    def __init__(self, response):
        self.response = response

    def complete_json(self, system_prompt: str, user_prompt: str):
        return self.response


def test_assessment_fallback_maps_sleep_problem_to_anxiety():
    result = AssessmentAgent(llm=None).run({"questionnaire": {"sleep": "最近睡不好"}})["assessment"]

    assert result["output"]["emotion_profile"]["dominant_emotion"] == "anxiety"
    assert result["status"] == "degraded"


def test_assessment_rejects_malformed_llm_json():
    result = AssessmentAgent(llm=FakeJsonLLM({})).run(
        {"questionnaire": {"sleep": "poor"}}
    )["assessment"]

    assert result["status"] == "degraded"
    # LLM returned malformed JSON but questionnaire data exists,
    # so rule-based fallback still produces a moderate-confidence result.
    assert result["confidence"] == 0.55


def test_diagnosis_rejects_malformed_llm_json():
    result = DiagnosisAgent(llm=FakeJsonLLM({})).run(
        {"assessment": {"confidence": 0.8, "output": {"emotion_profile": {"dominant_emotion": "anxiety"}}}}
    )["diagnosis"]

    assert result["status"] == "degraded"
    assert result["confidence"] <= 0.3


def test_diagnosis_uses_structured_llm_json_when_available():
    llm = FakeJsonLLM({"syndrome_id": "syd_001", "confidence": 0.78})
    result = DiagnosisAgent(llm=llm).run(
        {"assessment": {"output": {"dominant_emotion": "anxiety"}}}
    )["diagnosis"]

    assert result["output"]["syndrome_diagnosis"]["primary"]["syndrome_id"] == "syd_001"
    assert result["confidence"] == 0.78


def test_qwen_provider_parses_chat_completion_json():
    captured = {}

    def transport(url, headers, body, timeout):
        captured.update(url=url, headers=headers, body=body, timeout=timeout)
        return json.dumps(
            {"choices": [{"message": {"content": '{"confidence": 0.8}'}}]}
        ).encode()

    provider = QwenCompatibleProvider(
        base_url="https://qwen.example/v1",
        api_key="test-key",
        model="qwen-test",
        transport=transport,
    )

    result = provider.complete_json("system", "user")

    assert result == {"confidence": 0.8}
    assert captured["url"].endswith("/chat/completions")
    assert captured["headers"]["Authorization"] == "Bearer test-key"


def test_qwen_provider_can_be_created_from_environment(monkeypatch):
    monkeypatch.setenv("QWEN_BASE_URL", "https://qwen.example/v1")
    monkeypatch.setenv("QWEN_API_KEY", "test-key")
    monkeypatch.setenv("QWEN_MODEL", "qwen-test")

    provider = qwen_provider_from_env()

    assert provider is not None
    assert provider.model == "qwen-test"


class FakeKnowledgeStore:
    def query(self, query_text, limit=3):
        return [KnowledgeHit("角调可用于演示放松。", {"source_type": "demo"}, 0.9, 0.1)]


def test_prescription_returns_chroma_evidence_and_prompt():
    result = PrescriptionAgent(knowledge_store=FakeKnowledgeStore()).run(
        {"diagnosis": {"output": {"syndrome_diagnosis": {"primary": {"syndrome_id": "syd_001"}}}}}
    )["prescription"]

    assert result["output"]["music_feature"]["tone_id"] == "jiao"
    assert result["output"]["evidence"]
    assert result["output"]["prompt_template"]["template_id"] == "CN_V1"


def test_prescription_blocks_low_confidence_diagnosis():
    result = PrescriptionAgent(knowledge_store=None).run(
        {"diagnosis": {"confidence": 0.2, "output": {}}}
    )["prescription"]

    assert result["status"] == "degraded"
    assert result["output"]["action"] == "recommend_professional"
    assert "music_feature" not in result["output"]


def test_feedback_agent_persists_rating(tmp_path):
    store = SQLiteFeedbackStore(tmp_path / "feedback.sqlite3")
    result = FeedbackAgent(store).run(
        {"run_id": "run-1", "session_id": "s-1", "user_id": "u-1", "feedback": {"rating": 4, "comment": "舒缓"}}
    )["feedback"]

    assert result["status"] == "success"
    assert store.count() == 1
