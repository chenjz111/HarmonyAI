"""Pure-Python MPEG audio duration probe (VBR / Xing / VBRI aware).

The probe must survive real provider output: files with an ID3v2 tag, a
Xing/Info or VBRI header frame, and frames whose length differs from the first
frame (VBR). It therefore

* parses EVERY frame header at its own offset instead of assuming all frames
  share the first frame's length;
* prefers the Xing/Info or VBRI frame count when present;
* falls back to scanning all frames;
* refuses to return a value when the result is clearly implausible (e.g. the
  implied average bitrate is outside the MPEG audio range), so callers never
  persist a bogus duration.

No decoding is performed and no third-party dependency is required.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# bitrates_kbps[version_key][layer] -> 16 entries (index 0 = free, 15 = invalid)
# version_key: 3 -> MPEG1, 2 -> MPEG2, 0 -> MPEG2.5
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

# samples per frame: version_key -> layer (1 = Layer I, 2 = Layer II, 3 = III)
_SAMPLES_PER_FRAME: dict[int, dict[int, int]] = {
    3: {1: 384, 2: 1152, 3: 1152},
    2: {1: 384, 2: 1152, 3: 576},
    0: {1: 384, 2: 1152, 3: 576},
}

# MPEG audio bitrate envelope used for the plausibility guard (kbps).
_MIN_PLAUSIBLE_AVG_KBPS = 8.0
_MAX_PLAUSIBLE_AVG_KBPS = 448.0

# Side information size (bytes) between the header and a Xing/Info tag.
_SIDE_INFO = {
    (3, 1): 17,  # MPEG1 mono
    (3, 2): 32,  # MPEG1 stereo / joint / dual
    (2, 1): 9,
    (2, 2): 17,
    (0, 1): 9,
    (0, 2): 17,
}

_HEADER_VS_SCAN_TOLERANCE = 0.05  # 5% disagreement keeps the scanned value


@dataclass(frozen=True)
class Mp3DurationInfo:
    """Measured duration plus the evidence used to obtain it."""

    duration_seconds: float
    frames: int
    samplerate: int
    average_bitrate_kbps: float
    header_frames: int | None
    source: str  # "xing" | "vbri" | "scan"


@dataclass(frozen=True)
class _FrameHeader:
    version_key: int
    layer: int
    bitrate_kbps: int
    samplerate: int
    padding: int
    channel_mode: int
    frame_length: int
    samples_per_frame: int
    has_crc: bool

    @property
    def channels(self) -> int:
        return 1 if self.channel_mode == 3 else 2


def _skip_id3v2(payload: bytes) -> int:
    if payload[:3] != b"ID3" or len(payload) < 10:
        return 0
    size = payload[6:10]
    synchsafe = (size[0] << 21) | (size[1] << 14) | (size[2] << 7) | size[3]
    footer = 10 if (payload[5] & 0x10) else 0
    return 10 + synchsafe + footer


def _parse_frame_header(payload: bytes, pos: int) -> _FrameHeader | None:
    if pos + 4 > len(payload):
        return None
    b0, b1, b2 = payload[pos], payload[pos + 1], payload[pos + 2]
    if b0 != 0xFF or (b1 & 0xE0) != 0xE0:
        return None
    version_key = (b1 >> 3) & 0x3
    layer_bits = (b1 >> 1) & 0x3
    if version_key == 1 or layer_bits == 0:
        return None
    layer = {1: 3, 2: 2, 3: 1}[layer_bits]  # 1 -> Layer III, 2 -> II, 3 -> I
    bitrate_index = (b2 >> 4) & 0xF
    sample_rate_index = (b2 >> 2) & 0x3
    padding = (b2 >> 1) & 0x1
    channel_mode = (payload[pos + 3] >> 6) & 0x3
    bitrates = _BITRATES.get(version_key, {}).get(layer)
    sample_rates = _SAMPLE_RATES.get(version_key)
    if bitrates is None or sample_rates is None:
        return None
    if bitrate_index in (0, 15) or sample_rate_index == 3:
        # free-format / invalid bitrate or reserved sample rate: unusable
        return None
    bitrate_kbps = bitrates[bitrate_index]
    samplerate = sample_rates[sample_rate_index]
    samples_per_frame = _SAMPLES_PER_FRAME[version_key][layer]
    if layer == 1:
        frame_length = (12 * bitrate_kbps * 1000 // samplerate + padding) * 4
    else:
        frame_length = (
            samples_per_frame // 8 * bitrate_kbps * 1000 // samplerate + padding
        )
    if frame_length <= 4:
        return None
    return _FrameHeader(
        version_key=version_key,
        layer=layer,
        bitrate_kbps=bitrate_kbps,
        samplerate=samplerate,
        padding=padding,
        channel_mode=channel_mode,
        frame_length=frame_length,
        samples_per_frame=samples_per_frame,
        has_crc=(b1 & 0x1) == 0,
    )


def _vbr_header_frames(
    payload: bytes, pos: int, header: _FrameHeader
) -> tuple[str | None, int | None]:
    """Return (source, frame_count) from a Xing/Info or VBRI header frame."""
    offset = pos + 4 + (2 if header.has_crc else 0)
    side_info = _SIDE_INFO.get((header.version_key, header.channels))
    if side_info is not None:
        xing_pos = offset + side_info
        tag = payload[xing_pos : xing_pos + 4]
        if tag in (b"Xing", b"Info") and xing_pos + 12 <= len(payload):
            flags = int.from_bytes(payload[xing_pos + 4 : xing_pos + 8], "big")
            if flags & 0x0001:
                frames = int.from_bytes(payload[xing_pos + 8 : xing_pos + 12], "big")
                if frames > 0:
                    return ("xing", frames)
    vbri_pos = pos + 4 + 32
    if payload[vbri_pos : vbri_pos + 4] == b"VBRI" and vbri_pos + 18 <= len(payload):
        frames = int.from_bytes(payload[vbri_pos + 14 : vbri_pos + 18], "big")
        if frames > 0:
            return ("vbri", frames)
    return (None, None)


def _first_frame_offset(payload: bytes) -> int:
    index = _skip_id3v2(payload)
    while index + 4 <= len(payload):
        if _parse_frame_header(payload, index) is not None:
            return index
        index += 1
    return -1


def mp3_duration_info(payload: bytes) -> Mp3DurationInfo | None:
    """Measured duration with evidence, or ``None`` when unusable/implausible."""
    if not payload:
        return None
    start = _first_frame_offset(payload)
    if start < 0:
        return None

    pos = start
    frames = 0
    total_samples = 0
    samplerate: int | None = None
    header_source: str | None = None
    header_frames: int | None = None
    first_samples_per_frame: int | None = None

    while True:
        header = _parse_frame_header(payload, pos)
        if header is None:
            break
        if frames == 0:
            samplerate = header.samplerate
            first_samples_per_frame = header.samples_per_frame
            header_source, header_frames = _vbr_header_frames(payload, pos, header)
        if pos + header.frame_length > len(payload):
            break
        frames += 1
        total_samples += header.samples_per_frame
        pos += header.frame_length

    if samplerate is None or frames == 0 or first_samples_per_frame is None:
        return None

    scan_duration = total_samples / samplerate
    header_duration: float | None = None
    if header_frames:
        header_duration = header_frames * first_samples_per_frame / samplerate
    size_bytes = len(payload)

    def _plausible(duration: float | None) -> bool:
        if duration is None or duration <= 0:
            return False
        average_kbps = size_bytes * 8 / duration / 1000
        return _MIN_PLAUSIBLE_AVG_KBPS <= average_kbps <= _MAX_PLAUSIBLE_AVG_KBPS

    chosen_source: str | None = None
    chosen_duration: float | None = None
    chosen_frames: int | None = None

    if header_duration is not None and header_source is not None and _plausible(header_duration):
        chosen_source, chosen_duration, chosen_frames = (
            header_source,
            header_duration,
            header_frames or frames,
        )
    elif _plausible(scan_duration):
        chosen_source, chosen_duration, chosen_frames = "scan", scan_duration, frames

    if chosen_duration is None or chosen_source is None or chosen_frames is None:
        return None

    if (
        chosen_source != "scan"
        and _plausible(scan_duration)
        and scan_duration > 0
        and abs(chosen_duration - scan_duration) / max(chosen_duration, scan_duration)
        > _HEADER_VS_SCAN_TOLERANCE
    ):
        # The declared frame count and the frames actually present disagree
        # beyond tolerance: trust the physical scan instead.
        chosen_source, chosen_duration, chosen_frames = "scan", scan_duration, frames

    return Mp3DurationInfo(
        duration_seconds=chosen_duration,
        frames=chosen_frames,
        samplerate=samplerate,
        average_bitrate_kbps=size_bytes * 8 / chosen_duration / 1000,
        header_frames=header_frames,
        source=chosen_source,
    )


def mp3_duration_seconds(payload: bytes) -> float | None:
    """Return measured seconds, or ``None`` when unusable/implausible."""
    info = mp3_duration_info(payload)
    return info.duration_seconds if info is not None else None


def mp3_duration_seconds_from_file(path: str | Path) -> float | None:
    """Convenience wrapper that reads a saved asset file."""
    file_path = Path(path)
    if not file_path.is_file():
        return None
    return mp3_duration_seconds(file_path.read_bytes())
