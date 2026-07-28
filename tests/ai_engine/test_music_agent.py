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
        "status": "success",
        "generation_mode": "matched",
        "track_id": "track-jiao-01",
        "title": "Jiao Calm",
        "audio_url": "local://music/jiao-calm.mp3",
        "duration": 900,
        "source": "local_catalog",
        "music_parameters": {
            "tone_id": "jiao",
            "bpm": 68,
            "duration_minutes": 15,
            "instruments": ["guzheng", "guqin"],
        },
        "match_explanation": "Matched local catalog track by tone_id=jiao and nearest BPM.",
        "prescription_sources": ["local rule mapped the tendency to jiao"],
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
        "status": "failed",
        "generation_mode": "matched",
        "error_code": "TRACK_AUDIO_UNAVAILABLE",
        "fallback_tracks": [
            {
                "track_id": "track-zhi-01",
                "title": "Zhi Calm",
                "audio_url": "local://music/zhi-calm.mp3",
                "duration": 900,
                "source": "local_catalog",
            }
        ],
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
        "status": "blocked_safety",
        "generation_mode": "withheld",
        "action": "withhold_music_playback",
        "error_code": "SAFETY_BLOCKED",
        "fallback_tracks": [],
    }


def test_invalid_inputs_return_a_failed_result_instead_of_raising():
    from backend.ai_engine.music_agent import match_music_v2

    result = match_music_v2("not-a-prescription", "not-a-catalog")

    assert result == {
        "status": "failed",
        "generation_mode": "matched",
        "error_code": "INVALID_INPUT",
        "fallback_tracks": [],
    }
