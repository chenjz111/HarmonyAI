import math

import pytest


def prescription(**overrides):
    data = {
        "status": "success",
        "generation_mode": "matched",
        "music_feature": {
            "tone_id": "jiao",
            "bpm": 68,
            "duration_minutes": 15,
            "instruments": ["guzheng", "guqin"],
        },
        "recommendation_reasons": ["local rule mapped the tendency to jiao"],
    }
    data.update(overrides)
    return data


def test_local_catalog_match_returns_a_playable_track_and_prescription_parameters():
    from backend.ai_engine.music_agent import match_music_v2

    result = match_music_v2(
        prescription(),
        [
            {
                "track_id": "track-jiao-01",
                "title": "Jiao Calm",
                "audio_url": "local://music/jiao-calm.mp3",
                "duration": 900,
                "source": "local_catalog",
                "tone_id": "jiao",
                "bpm": 68,
                "instruments": ["guzheng", "guqin"],
            },
            {
                "track_id": "track-zhi-01",
                "title": "Zhi Calm",
                "audio_url": "local://music/zhi-calm.mp3",
                "duration": 900,
                "source": "local_catalog",
                "tone_id": "zhi",
                "bpm": 70,
                "instruments": ["pipa"],
            },
        ],
    )

    assert result == {
        "agent_id": "music_agent",
        "legacy_alias": "generation_agent",
        "status": "success",
        "music_id": "track-jiao-01",
        "title": "Jiao Calm",
        "source_type": "matched",
        "stream_url": "local://music/jiao-calm.mp3",
        "mode": "jiao",
        "bpm": 68,
        "duration_seconds": 900,
        "instruments": ["guzheng", "guqin"],
        "ambient_sounds": [],
        "rights_note": "本地曲库匹配结果",
        "match_explanation": ["local rule mapped the tendency to jiao"],
        "fallback_music_id": "track-zhi-01",
    }


def test_missing_matching_track_or_audio_returns_a_failed_result_with_fallbacks():
    from backend.ai_engine.music_agent import match_music_v2

    result = match_music_v2(
        prescription(),
        [
            {
                "track_id": "track-jiao-offline",
                "title": "Jiao Offline",
                "audio_url": "",
                "duration": 900,
                "source": "local_catalog",
                "tone_id": "jiao",
                "bpm": 68,
            },
            {
                "track_id": "track-zhi-01",
                "title": "Zhi Calm",
                "audio_url": "local://music/zhi-calm.mp3",
                "duration": 900,
                "source": "local_catalog",
                "tone_id": "zhi",
                "bpm": 70,
            },
        ],
    )

    assert result == {
        "agent_id": "music_agent",
        "legacy_alias": "generation_agent",
        "status": "failed",
        "source_type": "matched",
        "error_code": "TRACK_AUDIO_UNAVAILABLE",
        "fallback_music_id": "track-zhi-01",
    }


def test_blocked_or_low_confidence_prescription_never_returns_a_playable_track():
    from backend.ai_engine.music_agent import match_music_v2

    result = match_music_v2(
        prescription(status="blocked_safety", generation_mode="withheld"),
        [
            {
                "track_id": "track-jiao-01",
                "title": "Jiao Calm",
                "audio_url": "local://music/jiao-calm.mp3",
                "duration": 900,
                "source": "local_catalog",
                "tone_id": "jiao",
                "bpm": 68,
            }
        ],
    )

    assert result == {
        "agent_id": "music_agent",
        "legacy_alias": "generation_agent",
        "status": "blocked_safety",
        "source_type": "matched",
        "action": "withhold_music_playback",
        "error_code": "SAFETY_BLOCKED",
        "fallback_music_id": None,
    }


def test_low_confidence_prescription_never_returns_a_playable_track():
    from backend.ai_engine.music_agent import match_music_v2

    result = match_music_v2(
        prescription(confidence={"level": "low", "score": 0.2}),
        [
            {
                "track_id": "track-jiao-01",
                "title": "Jiao Calm",
                "audio_url": "local://music/jiao-calm.mp3",
                "duration": 900,
                "source": "local_catalog",
                "tone_id": "jiao",
                "bpm": 68,
            }
        ],
    )

    assert result == {
        "agent_id": "music_agent",
        "legacy_alias": "generation_agent",
        "status": "degraded",
        "source_type": "matched",
        "action": "withhold_music_playback",
        "error_code": "LOW_CONFIDENCE",
        "fallback_music_id": None,
    }


@pytest.mark.parametrize("invalid_bpm", [None, "68", math.nan, math.inf, -math.inf])
def test_invalid_catalog_bpm_returns_a_failed_result_with_a_playable_fallback(invalid_bpm):
    from backend.ai_engine.music_agent import match_music_v2

    result = match_music_v2(
        prescription(),
        [
            {
                "track_id": "track-jiao-invalid-bpm",
                "title": "Jiao Invalid BPM",
                "audio_url": "local://music/jiao-invalid-bpm.mp3",
                "duration": 900,
                "source": "local_catalog",
                "tone_id": "jiao",
                "bpm": invalid_bpm,
            },
            {
                "track_id": "track-zhi-01",
                "title": "Zhi Calm",
                "audio_url": "local://music/zhi-calm.mp3",
                "duration": 900,
                "source": "local_catalog",
                "tone_id": "zhi",
                "bpm": 70,
            },
        ],
    )

    assert result == {
        "agent_id": "music_agent",
        "legacy_alias": "generation_agent",
        "status": "failed",
        "source_type": "matched",
        "error_code": "NO_PLAYABLE_TRACK",
        "fallback_music_id": "track-zhi-01",
    }


def test_invalid_inputs_return_a_failed_result_instead_of_raising():
    from backend.ai_engine.music_agent import match_music_v2

    result = match_music_v2("not-a-prescription", "not-a-catalog")

    assert result == {
        "agent_id": "music_agent",
        "legacy_alias": "generation_agent",
        "status": "failed",
        "source_type": "matched",
        "error_code": "INVALID_INPUT",
        "fallback_music_id": None,
    }


def test_generated_mode_is_rejected_because_sprint3_only_matches_local_music():
    from backend.ai_engine.music_agent import match_music_v2

    result = match_music_v2(
        prescription(generation_mode="generated"),
        [],
    )

    assert result == {
        "agent_id": "music_agent",
        "legacy_alias": "generation_agent",
        "status": "failed",
        "source_type": "matched",
        "error_code": "MODE_NOT_AVAILABLE",
        "fallback_music_id": None,
    }


def test_canonical_music_contract_is_flat_and_marks_local_match():
    from backend.ai_engine.music_agent import match_music_v2

    result = match_music_v2(
        prescription(),
        [
            {
                "music_id": "music-jiao-01",
                "title": "角调·舒缓",
                "stream_url": "/static/music/jiao-calm.wav",
                "duration_seconds": 900,
                "source_type": "matched",
                "rights_note": "比赛演示授权曲目",
                "mode": "角调",
                "tone_id": "jiao",
                "bpm": 68,
                "instruments": ["古筝", "古琴"],
                "ambient_sounds": ["流水"],
            }
        ],
    )

    assert result == {
        "agent_id": "music_agent",
        "legacy_alias": "generation_agent",
        "status": "success",
        "music_id": "music-jiao-01",
        "title": "角调·舒缓",
        "source_type": "matched",
        "stream_url": "/static/music/jiao-calm.wav",
        "mode": "角调",
        "bpm": 68,
        "duration_seconds": 900,
        "instruments": ["古筝", "古琴"],
        "ambient_sounds": ["流水"],
        "rights_note": "比赛演示授权曲目",
        "match_explanation": [
            "local rule mapped the tendency to jiao"
        ],
        "fallback_music_id": None,
    }
