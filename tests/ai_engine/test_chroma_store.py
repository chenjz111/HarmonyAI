from backend.ai_engine.chroma_store import ChromaKnowledgeStore, KnowledgeChunk
from backend.ai_engine.chroma_demo import run_demo


def test_upsert_persists_chunks_for_a_new_store_instance(tmp_path):
    store = ChromaKnowledgeStore(tmp_path)
    store.upsert(
        [
            KnowledgeChunk(
                chunk_id="demo_001",
                text="焦虑时可使用角调音乐进行放松。",
                metadata={"source_type": "demo"},
            )
        ]
    )

    reopened = ChromaKnowledgeStore(tmp_path)

    assert reopened.count() == 1


def test_query_returns_matching_document_and_traceability_metadata(tmp_path):
    store = ChromaKnowledgeStore(tmp_path)
    store.upsert(
        [
            KnowledgeChunk(
                chunk_id="demo_001",
                text="焦虑时可使用角调音乐进行放松。",
                metadata={"source_type": "demo", "credibility_level": "D"},
            ),
            KnowledgeChunk(
                chunk_id="demo_002",
                text="宫调音乐用于思虑过度的放松演示。",
                metadata={"source_type": "demo", "credibility_level": "D"},
            ),
        ]
    )

    hits = store.query("焦虑 角调", limit=1)

    assert hits[0].text == "焦虑时可使用角调音乐进行放松。"
    assert hits[0].metadata["credibility_level"] == "D"


def test_blank_query_returns_no_hits(tmp_path):
    assert ChromaKnowledgeStore(tmp_path).query("   ") == []


def test_demo_ingests_three_seed_chunks_and_returns_traceable_hit(tmp_path):
    hits = run_demo(tmp_path)

    assert hits
    assert hits[0].metadata["source_type"] == "demo"
    assert hits[0].metadata["credibility_level"] == "D"
