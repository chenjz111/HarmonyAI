def test_offline_demo_returns_json_compatible_result():
    from backend.ai_engine.demo import run_demo

    result = run_demo()

    assert result["prescription"]["tone_id"] == "jiao"
    assert isinstance(result["prescription"]["prompt"]["text"], str)
