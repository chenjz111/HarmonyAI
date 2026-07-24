from backend.ai_engine.providers import FallbackLLMProvider, InMemoryVectorStore


def test_fallback_llm_returns_explainable_rule_response():
    result = FallbackLLMProvider().complete("请分析肝郁化火")

    assert "规则引擎" in result
    assert "仅供参考" in result


def test_memory_vector_store_returns_matching_knowledge_first():
    store = InMemoryVectorStore()
    store.add("角调与木、肝相关", {"source": "demo-source"})
    store.add("宫调与土、脾相关", {"source": "other-source"})

    hits = store.search("肝 角调", limit=1)

    assert len(hits) == 1
    assert hits[0].metadata["source"] == "demo-source"
