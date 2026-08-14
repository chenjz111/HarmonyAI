"""Controlled non-prescription comfort audio for the Safety Support track."""
from __future__ import annotations

from collections.abc import Mapping, Sequence


def select_comfort_audio(
    catalog: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Return an existing local track with explicit non-medical semantics."""
    if not catalog:
        raise RuntimeError("comfort audio catalog is empty")
    track = dict(catalog[0])
    return {
        "audio_type": "comfort_audio",
        "music_id": track["music_id"],
        "title": "温和安抚音频",
        "source_type": "curated_library",
        "stream_url": track["stream_url"],
        "duration_seconds": track["duration_seconds"],
        "personalized": False,
        "is_medical_prescription": False,
        "autoplay": False,
        "safety_notice": (
            "这段音频仅用于短时安抚，不能替代专业帮助，也不会改变当前安全状态。"
        ),
    }

