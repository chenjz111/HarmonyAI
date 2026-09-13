"""MP3 duration probe — VBR / Xing / VBRI structure compatibility.

The probe must handle real provider output (ID3v2 tag + a Xing/Info header frame
whose length differs from the following VBR frames). A fixed-bitrate,
hand-spliced MP3 is NOT sufficient evidence, so these tests build real
structures: Xing/Info header frames, VBRI headers, mixed-bitrate frame chains
and an explicitly anomalous file that must be refused instead of persisted.
"""

from pathlib import Path

from backend.app.core.audio_duration import (
    mp3_duration_info,
    mp3_duration_seconds,
    mp3_duration_seconds_from_file,
)

SAMPLERATE = 44100
SAMPLES_PER_FRAME = 1152  # MPEG1 Layer III

# MPEG1 Layer III, 44.1 kHz, no CRC, stereo, no padding
_BITRATE_INDEX = {32: 1, 40: 2, 48: 3, 56: 4, 64: 5, 80: 6, 96: 7, 112: 8,
                  128: 9, 160: 10, 192: 11, 224: 12, 256: 13, 320: 14}


def _frame_length(bitrate_kbps: int, padding: int = 0) -> int:
    return (
        SAMPLES_PER_FRAME // 8 * bitrate_kbps * 1000 // SAMPLERATE + padding
    )


def _frame(bitrate_kbps: int, padding: int = 0) -> bytes:
    header = bytes(
        [
            0xFF,
            0xFB,  # MPEG1 Layer III, no CRC
            (_BITRATE_INDEX[bitrate_kbps] << 4) | 0x00 | (padding << 1),
            0x00,  # stereo
        ]
    )
    return header + bytes(max(0, _frame_length(bitrate_kbps, padding) - 4))


def _xing_frame(bitrate_kbps: int, total_frames: int) -> bytes:
    """A Xing header frame (its own size differs from the VBR data frames)."""
    body = bytearray(_frame(bitrate_kbps))
    side_info = 32  # MPEG1 stereo
    xing_pos = 4 + side_info
    body[xing_pos : xing_pos + 4] = b"Xing"
    body[xing_pos + 4 : xing_pos + 8] = (0x0001).to_bytes(4, "big")  # frames present
    body[xing_pos + 8 : xing_pos + 12] = int(total_frames).to_bytes(4, "big")
    return bytes(body)


def _vbri_frame(bitrate_kbps: int, total_frames: int) -> bytes:
    body = bytearray(_frame(bitrate_kbps))
    vbri_pos = 4 + 32
    body[vbri_pos : vbri_pos + 4] = b"VBRI"
    body[vbri_pos + 14 : vbri_pos + 18] = int(total_frames).to_bytes(4, "big")
    return bytes(body)


def _id3v2(size: int = 0) -> bytes:
    synchsafe = bytes(
        [(size >> 21) & 0x7F, (size >> 14) & 0x7F, (size >> 7) & 0x7F, size & 0x7F]
    )
    return b"ID3\x03\x00\x00" + synchsafe + b"\x00\x00"


def _cbr_mp3(*, seconds: float, bitrate_kbps: int = 128) -> bytes:
    frames = max(1, int(seconds * SAMPLERATE / SAMPLES_PER_FRAME))
    return _frame(bitrate_kbps) * frames


def _real_smoke_like_mp3(*, duration_seconds: float = 75.781, data_bitrate: int = 32) -> bytes:
    """Reproduce the Owner real smoke structure (~304 KB, ~75.8 s).

    ID3v2 tag + a Xing header frame encoded at a different bitrate (the classic
    first-frame trap) + ~2900 VBR data frames, then the Xing frame count.
    """
    total_frames = max(2, round(duration_seconds * SAMPLERATE / SAMPLES_PER_FRAME))
    return (
        _id3v2(0)
        + _xing_frame(128, total_frames)
        + _frame(data_bitrate) * (total_frames - 1)
    )


# ------------------------------------------------------------- regression: P0


def test_real_smoke_like_xing_vbr_mp3_measures_correct_duration():
    """The old probe returned ~0.05 s here (first-frame length assumption)."""
    payload = _real_smoke_like_mp3(duration_seconds=75.781, data_bitrate=32)

    info = mp3_duration_info(payload)
    assert info is not None
    assert 75.4 <= info.duration_seconds <= 76.2
    assert info.source == "xing"
    assert info.header_frames is not None and info.header_frames >= 2900
    assert 8.0 <= info.average_bitrate_kbps <= 448.0
    # sanity: the payload really is ~300 KB like the real smoke file
    assert 280_000 <= len(payload) <= 320_000


def test_header_frame_longer_than_data_frames_is_not_used_as_frame_size():
    payload = _real_smoke_like_mp3(duration_seconds=75.781, data_bitrate=32)
    measured = mp3_duration_seconds(payload)
    assert measured is not None
    assert measured > 60.0  # never the ~0.05 s first-frame artefact


def test_cbr_fixed_bitrate_still_measures():
    measured = mp3_duration_seconds(_cbr_mp3(seconds=3.0))
    assert measured is not None
    assert 2.9 <= measured <= 3.1


def test_id3v2_tag_is_skipped():
    measured = mp3_duration_seconds(_id3v2(0) + _cbr_mp3(seconds=1.5))
    assert measured is not None
    assert 1.4 <= measured <= 1.6


# ----------------------------------------------------------------- VBR without Xing


def test_vbr_without_xing_scans_each_frame_header():
    frames = [_frame(32), _frame(64), _frame(128), _frame(64), _frame(32)] * 20
    payload = b"".join(frames)
    info = mp3_duration_info(payload)
    assert info is not None
    assert info.source == "scan"
    expected = len(frames) * SAMPLES_PER_FRAME / SAMPLERATE
    assert abs(info.duration_seconds - expected) < 0.05
    assert info.frames == len(frames)


def test_vbri_frame_count_is_used():
    total_frames = 2000
    payload = _vbri_frame(128, total_frames) + _frame(32) * (total_frames - 1)
    info = mp3_duration_info(payload)
    assert info is not None
    assert info.source == "vbri"
    expected = total_frames * SAMPLES_PER_FRAME / SAMPLERATE
    assert abs(info.duration_seconds - expected) < 0.1


def test_xing_count_wins_when_scan_is_truncated_by_trailing_garbage():
    total_frames = 1500
    payload = (
        _xing_frame(128, total_frames)
        + _frame(32) * (total_frames - 1)
        + b"\x00" * 4096  # trailing non-audio bytes end the physical scan early
    )
    info = mp3_duration_info(payload)
    assert info is not None
    expected = total_frames * SAMPLES_PER_FRAME / SAMPLERATE
    assert abs(info.duration_seconds - expected) < 0.2


# --------------------------------------------------------------- anomaly refusal


def test_implausible_duration_is_refused_instead_of_returned():
    """A ~300 KB file claiming ~0.03 s must never be measured as 0.03 s."""
    payload = _xing_frame(128, 1) + b"\x00" * 300_000
    assert mp3_duration_seconds(payload) is None
    assert mp3_duration_info(payload) is None


def test_unparseable_payloads_return_none():
    assert mp3_duration_seconds(b"") is None
    assert mp3_duration_seconds(b"\x00\x01\x02 just text") is None
    assert mp3_duration_seconds(b"\xff\xfb\x90") is None  # truncated header


def test_file_helper(tmp_path: Path):
    good = tmp_path / "a.mp3"
    good.write_bytes(_real_smoke_like_mp3(duration_seconds=20.0, data_bitrate=32))
    measured = mp3_duration_seconds_from_file(good)
    assert measured is not None and measured > 15.0

    missing = tmp_path / "missing.mp3"
    assert mp3_duration_seconds_from_file(missing) is None
