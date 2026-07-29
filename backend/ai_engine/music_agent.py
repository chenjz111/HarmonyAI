from __future__ import annotations

from collections.abc import Mapping, Sequence
import math


def match_music_v2(
    prescription: Mapping[str, object],
    catalog: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Match a safe V2 prescription to one playable local catalog track."""
    if not isinstance(prescription, Mapping) or not _is_catalog(catalog):
        return _failed("INVALID_INPUT")

    withheld = _withheld_result(prescription)
    if withheld is not None:
        return withheld
    if prescription.get("generation_mode") not in {None, "matched"}:
        return _failed("MODE_NOT_AVAILABLE")

    music_feature = prescription.get("music_feature")
    if not isinstance(music_feature, Mapping):
        return _failed("INVALID_INPUT")
    tone_id = music_feature.get("tone_id")
    bpm = music_feature.get("bpm")
    if not isinstance(tone_id, str) or not tone_id or not _is_finite_number(bpm):
        return _failed("INVALID_INPUT")

    matching_tracks = [
        track for track in catalog if track.get("tone_id") == tone_id
    ]
    playable_matches = [track for track in matching_tracks if _is_playable(track)]
    if not playable_matches:
        error_code = "NO_MATCHING_TRACK"
        if matching_tracks:
            error_code = (
                "TRACK_AUDIO_UNAVAILABLE"
                if any(not _has_audio(track) for track in matching_tracks)
                else "NO_PLAYABLE_TRACK"
            )
        return _failed(
            error_code,
            _fallback_music_id(catalog, excluded=matching_tracks),
        )

    track = min(
        playable_matches,
        key=lambda item: abs(float(item.get("bpm", bpm)) - float(bpm)),
    )
    reasons = prescription.get("recommendation_reasons")
    explanations = (
        list(reasons)
        if _is_string_list(reasons)
        else [
            (
                "按处方调式和最接近的 BPM 从本地曲库完成匹配。"
            )
        ]
    )
    return {
        "agent_id": "music_agent",
        "legacy_alias": "generation_agent",
        "status": "success",
        "music_id": _track_value(track, "music_id", "track_id"),
        "title": track["title"],
        "source_type": "matched",
        "stream_url": _track_value(
            track,
            "stream_url",
            "audio_url",
        ),
        "mode": (
            track.get("mode")
            or music_feature.get("tone_name")
            or tone_id
        ),
        "bpm": track["bpm"],
        "duration_seconds": _track_value(
            track,
            "duration_seconds",
            "duration",
        ),
        "instruments": _track_instruments(track, music_feature),
        "ambient_sounds": _string_list(
            track.get("ambient_sounds"),
        ),
        "rights_note": (
            track.get("rights_note")
            if isinstance(track.get("rights_note"), str)
            else "本地曲库匹配结果"
        ),
        "match_explanation": explanations,
        "fallback_music_id": _fallback_music_id(
            catalog,
            excluded=[track],
        ),
    }


def _is_catalog(catalog: object) -> bool:
    return isinstance(catalog, Sequence) and not isinstance(catalog, (str, bytes)) and all(
        isinstance(track, Mapping) for track in catalog
    )


def _withheld_result(prescription: Mapping[str, object]) -> dict[str, object] | None:
    if prescription.get("status") == "blocked_safety":
        return {
            "agent_id": "music_agent",
            "legacy_alias": "generation_agent",
            "status": "blocked_safety",
            "source_type": "matched",
            "action": "withhold_music_playback",
            "error_code": "SAFETY_BLOCKED",
            "fallback_music_id": None,
        }
    confidence = prescription.get("confidence")
    low_confidence = (
        isinstance(confidence, Mapping)
        and (
            confidence.get("level") == "low"
            or (
                _is_finite_number(confidence.get("score"))
                and float(confidence["score"]) < 0.4
            )
        )
    )
    if prescription.get("generation_mode") == "withheld" or low_confidence:
        return {
            "agent_id": "music_agent",
            "legacy_alias": "generation_agent",
            "status": "degraded",
            "source_type": "matched",
            "action": "withhold_music_playback",
            "error_code": "LOW_CONFIDENCE",
            "fallback_music_id": None,
        }
    return None


def _is_playable(track: Mapping[str, object]) -> bool:
    return all(
        (
            isinstance(
                _track_value(track, "music_id", "track_id"),
                str,
            )
            and bool(_track_value(track, "music_id", "track_id")),
            isinstance(track.get("title"), str) and bool(track["title"]),
            isinstance(
                _track_value(track, "stream_url", "audio_url"),
                str,
            )
            and bool(_track_value(track, "stream_url", "audio_url")),
            _is_finite_number(
                _track_value(
                    track,
                    "duration_seconds",
                    "duration",
                )
            )
            and float(
                _track_value(
                    track,
                    "duration_seconds",
                    "duration",
                )
            )
            > 0,
            track.get("source_type") in {None, "matched"},
            _is_finite_number(track.get("bpm")),
        )
    )


def _has_audio(track: Mapping[str, object]) -> bool:
    value = _track_value(track, "stream_url", "audio_url")
    return isinstance(value, str) and bool(value)


def _fallback_music_id(
    catalog: Sequence[Mapping[str, object]], *, excluded: Sequence[Mapping[str, object]]
) -> str | None:
    excluded_ids = {id(track) for track in excluded}
    fallback = next(
        (
            track
            for track in catalog
            if id(track) not in excluded_ids and _is_playable(track)
        ),
        None,
    )
    if fallback is None:
        return None
    value = _track_value(fallback, "music_id", "track_id")
    return value if isinstance(value, str) else None


def _failed(
    error_code: str,
    fallback_music_id: str | None = None,
) -> dict[str, object]:
    return {
        "agent_id": "music_agent",
        "legacy_alias": "generation_agent",
        "status": "failed",
        "source_type": "matched",
        "error_code": error_code,
        "fallback_music_id": fallback_music_id,
    }


def _is_finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _is_string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _track_value(
    track: Mapping[str, object],
    canonical_name: str,
    legacy_name: str,
) -> object:
    return track.get(canonical_name, track.get(legacy_name))


def _track_instruments(
    track: Mapping[str, object],
    music_feature: Mapping[str, object],
) -> list[str]:
    track_instruments = _string_list(track.get("instruments"))
    if track_instruments:
        return track_instruments
    return _string_list(music_feature.get("instruments"))


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
