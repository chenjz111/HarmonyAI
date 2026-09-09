"""Pure-Python MP3 duration probe (no decoding, no extra dependencies).

Computes the real duration of an MPEG audio file by walking Layer III frame
headers and summing frame samples. It never decodes PCM and never falls back to
a guessed/requested duration — it returns the measured seconds or ``None`` when
the file cannot be parsed as MPEG audio.

MPEG1 Layer III: 1152 samples/frame; MPEG2/2.5 Layer III: 576 samples/frame.
Frame length for Layer III:

    frame_len = int(samples_per_frame * bitrate / (8 * samplerate)) + padding

Only the constant tables below are needed. This utility is intentionally small
and deterministic so generated-asset duration is read from the actual saved
file (Owner rule: never store the requested duration as the real duration).
"""

from __future__ import annotations

from pathlib import Path

# bitrate_kbps[version][layer-1][bitrate_index]
# version: 0 -> MPEG2.5, 1 -> reserved, 2 -> MPEG2, 3 -> MPEG1
_BITRATES: dict[int, dict[int, tuple[int, ...]]] = {
    3: {
        1: (0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448, 0),
        2: (0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384, 0),
        3: (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0),
    },
    2: {
        1: (0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256, 0),
        2: (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0),
        3: (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0),
    },
    0: {
        1: (0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256, 0),
        2: (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0),
        3: (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0),
    },
}

_SAMPLE_RATES: dict[int, tuple[int, ...]] = {
    3: (44100, 48000, 32000),
    2: (22050, 24000, 16000),
    0: (11025, 12000, 8000),
}

_SAMPLES_PER_FRAME_LAYER3 = {3: 1152, 2: 576, 0: 576}


def _skip_id3v2(payload: bytes) -> int:
    """Return the byte offset just past an ID3v2 tag (0 when absent)."""
    if payload[:3] != b"ID3" or len(payload) < 10:
        return 0
    size = payload[6:10]
    synchsafe = (
        (size[0] << 21) | (size[1] << 14) | (size[2] << 7) | size[3]
    )
    # 10-byte header + tag size + optional footer (flag 0x10)
    footer = 10 if (payload[5] & 0x10) else 0
    return 10 + synchsafe + footer


def mp3_duration_seconds(payload: bytes) -> float | None:
    """Return measured seconds for an MPEG Layer III stream, else ``None``.

    Returns ``None`` (never an exception) when the payload cannot be parsed as
    MPEG audio, so callers can keep the documented fallback semantics.
    """
    if not payload:
        return None
    offset = _skip_id3v2(payload)
    data = payload[offset:]

    # locate the first frame sync
    index = 0
    while index + 4 <= len(data):
        if data[index] == 0xFF and (data[index + 1] & 0xE0) == 0xE0:
            break
        index += 1
    if index + 4 > len(data):
        return None

    first = data[index : index + 4]
    version = (first[1] >> 3) & 0x3
    layer_bits = (first[1] >> 1) & 0x3
    if version == 1 or layer_bits != 1:  # reserved version or not Layer III
        return None
    bitrate_index = (first[2] >> 4) & 0xF
    sample_rate_index = (first[2] >> 2) & 0x3
    padding = (first[2] >> 1) & 0x1
    bitrates = _BITRATES.get(version, {}).get(3)
    if bitrates is None or bitrate_index in (0, 15):
        return None
    bitrate_kbps = bitrates[bitrate_index]
    sample_rates = _SAMPLE_RATES.get(version)
    if sample_rates is None or sample_rate_index == 3:
        return None
    samplerate = sample_rates[sample_rate_index]
    samples_per_frame = _SAMPLES_PER_FRAME_LAYER3[version]

    frame_length = int(samples_per_frame * bitrate_kbps * 1000 / (8 * samplerate))
    frame_length += padding

    frames = 0
    cursor = index
    while cursor + frame_length <= len(data):
        header = data[cursor : cursor + 4]
        if header[0] != 0xFF or (header[1] & 0xE0) != 0xE0:
            break
        v = (header[1] >> 3) & 0x3
        lay = (header[1] >> 1) & 0x3
        if v == 1 or lay != 1:
            break
        frames += 1
        cursor += frame_length

    if frames <= 0:
        return None
    return frames * samples_per_frame / samplerate


def mp3_duration_seconds_from_file(path: str | Path) -> float | None:
    """Convenience wrapper that reads a saved asset file."""
    file_path = Path(path)
    if not file_path.is_file():
        return None
    return mp3_duration_seconds(file_path.read_bytes())
