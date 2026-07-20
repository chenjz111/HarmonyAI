from backend.ai_engine.sprint2_demo import run_demo


def test_sprint2_demo_returns_full_stubbed_closed_loop():
    result = run_demo()

    assert result["generation"]["output"]["audio"]["url"] == "local://music/jiao-demo.mp3"
    assert result["feedback"]["output"]["decision"]["action"] == "continue"
