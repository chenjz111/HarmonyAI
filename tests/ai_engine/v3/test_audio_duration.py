"""MP3 duration probe — measured duration, never the requested duration."""

from pathlib import Path

from backend.app.core.audio_duration import (
    mp3_duration_seconds,
    mp3_duration_seconds_from_file,
)


def _mp3_bytes(*, seconds: float = 3.0) -> bytes:
    bitrate_kbps = 128
    samplerate = 44100
    samples_per_frame = 1152
    frame_length = int(samples_per_frame * bitrate_kbps * 1000 / (8 * samplerate))
    frame = b"\xff\xfb\x90\x00" + bytes(max(0, frame_length - 4))
    frames = max(1, int(seconds * samplerate / samples_per_frame) + 1)
    return frame * frames


def test_measures_synthetic_cbr_mp3():
    measured = mp3_duration_seconds(_mp3_bytes(seconds=3.0))
    assert measured is not None
    assert 2.9 <= measured <= 3.1


def test_skips_id3v2_tag_before_frames():
    audio = _mp3_bytes(seconds=1.5)
    # minimal ID3v2 header (10 bytes, zero-size tag)
    id3 = b"ID3\x03\x00\x00\x00\x00\x00\x00\x00"
    measured = mp3_duration_seconds(id3 + audio)
    assert measured is not None
    assert 1.4 <= measured <= 1.6


def test_unparseable_payload_returns_none():
    assert mp3_duration_seconds(b"") is None
    assert mp3_duration_seconds(b"\x00\x01\x02 just text") is None
    assert mp3_duration_seconds(b"\xff\xfb\x90") is None  # truncated header


def test_file_helper(tmp_path: Path):
    path = tmp_path / "a.mp3"
    path.write_bytes(_mp3_bytes(seconds=2.0))
    assert mp3_duration_seconds_from_file(path) is not None
    missing = tmp_path / "missing.mp3"
    assert mp3_duration_seconds_from_file(missing) is None
