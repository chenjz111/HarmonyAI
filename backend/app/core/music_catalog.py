"""Load and validate the controlled competition music catalog."""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path


_CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "music_catalog.json"
_REPO_ROOT = Path(__file__).resolve().parents[3]
_REQUIRED_FIELDS = {
    "music_id",
    "title",
    "source_type",
    "stream_url",
    "tone_id",
    "mode",
    "bpm",
    "duration_seconds",
    "instruments",
}


@lru_cache(maxsize=1)
def load_music_catalog() -> tuple[dict[str, object], ...]:
    raw = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise RuntimeError("music catalog must be a non-empty list")

    catalog = []
    for item in raw:
        if not isinstance(item, dict) or not _REQUIRED_FIELDS <= set(item):
            raise RuntimeError("music catalog entry is incomplete")
        if item["source_type"] != "matched":
            raise RuntimeError("competition catalog only supports matched tracks")
        stream_url = item["stream_url"]
        if not isinstance(stream_url, str) or not stream_url.startswith("/static/music/"):
            raise RuntimeError("music stream URL must use the controlled static path")
        audio_path = _REPO_ROOT / "frontend" / stream_url.lstrip("/")
        if not audio_path.is_file():
            raise RuntimeError("catalog audio file is missing")
        catalog.append(dict(item))
    return tuple(catalog)
