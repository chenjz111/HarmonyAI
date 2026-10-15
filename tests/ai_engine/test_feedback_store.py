from backend.ai_engine.feedback_store import SQLiteFeedbackStore


def test_sqlite_feedback_round_trip(tmp_path):
    store = SQLiteFeedbackStore(tmp_path / "feedback.sqlite3")

    store.save(run_id="run-1", session_id="s-1", user_id="u-1", rating=4, comment="舒缓")

    assert store.count() == 1
