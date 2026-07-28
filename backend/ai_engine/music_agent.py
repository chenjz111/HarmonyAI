from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


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

    music_feature = prescription.get("music_feature")
    if not isinstance(music_feature, Mapping):
        return _failed("INVALID_INPUT")
    tone_id = music_feature.get("tone_id")
    bpm = music_feature.get("bpm")
    if not isinstance(tone_id, str) or not tone_id or not _is_number(bpm):
        return _failed("INVALID_INPUT")

    matching_tracks = [
        track for track in catalog if track.get("tone_id") == tone_id
    ]
    playable_matches = [track for track in matching_tracks if _is_playable(track)]
    if not playable_matches:
        error_code = (
            "TRACK_AUDIO_UNAVAILABLE" if matching_tracks else "NO_MATCHING_TRACK"
        )
        return _failed(error_code, _fallback_tracks(catalog, excluded=matching_tracks))

    track = min(
        playable_matches,
        key=lambda item: abs(float(item.get("bpm", bpm)) - float(bpm)),
    )
    music_parameters = {
        key: music_feature[key]
        for key in ("tone_id", "bpm", "duration_minutes", "instruments")
        if key in music_feature
    }
    reasons = prescription.get("recommendation_reasons")
    return {
        "status": "success",
        "generation_mode": "matched",
        "track_id": track["track_id"],
        "title": track["title"],
        "audio_url": track["audio_url"],
        "duration": track["duration"],
        "source": track["source"],
        "music_parameters": music_parameters,
        "match_explanation": (
            f"Matched local catalog track by tone_id={tone_id} and nearest BPM."
        ),
        "prescription_sources": list(reasons) if _is_string_list(reasons) else [],
    }


def _is_catalog(catalog: object) -> bool:
    return isinstance(catalog, Sequence) and not isinstance(catalog, (str, bytes)) and all(
        isinstance(track, Mapping) for track in catalog
    )


def _withheld_result(prescription: Mapping[str, object]) -> dict[str, object] | None:
    if prescription.get("status") == "blocked_safety":
        return {
            "status": "blocked_safety",
            "generation_mode": "withheld",
            "action": "withhold_music_playback",
            "error_code": "SAFETY_BLOCKED",
            "fallback_tracks": [],
        }
    confidence = prescription.get("confidence")
    low_confidence = (
        isinstance(confidence, Mapping)
        and (
            confidence.get("level") == "low"
            or (
                _is_number(confidence.get("score"))
                and float(confidence["score"]) < 0.4
            )
        )
    )
    if prescription.get("generation_mode") == "withheld" or low_confidence:
        return {
            "status": "degraded",
            "generation_mode": "withheld",
            "action": "withhold_music_playback",
            "error_code": "LOW_CONFIDENCE",
            "fallback_tracks": [],
        }
    return None


def _is_playable(track: Mapping[str, object]) -> bool:
    return all(
        (
            isinstance(track.get("track_id"), str) and bool(track["track_id"]),
            isinstance(track.get("title"), str) and bool(track["title"]),
            isinstance(track.get("audio_url"), str) and bool(track["audio_url"]),
            _is_number(track.get("duration")) and float(track["duration"]) > 0,
            isinstance(track.get("source"), str) and bool(track["source"]),
        )
    )


def _fallback_tracks(
    catalog: Sequence[Mapping[str, object]], *, excluded: Sequence[Mapping[str, object]]
) -> list[dict[str, object]]:
    excluded_ids = {id(track) for track in excluded}
    return [
        {
            "track_id": track["track_id"],
            "title": track["title"],
            "audio_url": track["audio_url"],
            "duration": track["duration"],
            "source": track["source"],
        }
        for track in catalog
        if id(track) not in excluded_ids and _is_playable(track)
    ]


def _failed(error_code: str, fallback_tracks: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {
        "status": "failed",
        "generation_mode": "matched",
        "error_code": error_code,
        "fallback_tracks": fallback_tracks or [],
    }


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)
