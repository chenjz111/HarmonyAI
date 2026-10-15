"""Offline catalog fallback behavior for Music Agent V2."""

from backend.ai_engine.music_agent import match_music_v2


def test_missing_requested_tone_returns_an_honest_playable_fallback():
    prescription = {
        "status": "success",
        "generation_mode": "matched",
        "music_feature": {
            "tone_id": "shang",
            "tone_name": "商调",
            "bpm": 66,
            "instruments": ["二胡", "洞箫"],
        },
        "recommendation_reasons": ["辅助辨证倾向映射为商调。"],
    }
    catalog = [
        {
            "music_id": "music_jiao_001",
            "title": "角调·舒心",
            "source_type": "matched",
            "stream_url": "/static/music/jiao-demo.wav",
            "tone_id": "jiao",
            "mode": "角调",
            "bpm": 68,
            "duration_seconds": 30,
            "instruments": ["古琴", "古筝"],
        }
    ]

    result = match_music_v2(prescription, catalog)

    assert result["agent_id"] == "music_agent"
    assert result["status"] == "degraded"
    assert result["error_code"] == "NO_MATCHING_TRACK"
    assert result["fallback_applied"] is True
    assert result["requested_tone_id"] == "shang"
    assert result["music_id"] == "music_jiao_001"
    assert result["stream_url"] == "/static/music/jiao-demo.wav"
    assert result["mode"] == "角调"
    assert result["source_type"] == "matched"
