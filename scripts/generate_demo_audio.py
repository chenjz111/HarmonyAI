"""Generate pentatonic healing music for Sprint 2 demo.

Creates a 60-second calming pentatonic melody (角调式, E-pentatonic, ~68 BPM)
using pure sine waves. No external dependencies — uses Python stdlib only.

Output: frontend/static/music/jiao-demo.wav
"""
import math
import struct
import wave
from pathlib import Path

# ---------------------------------------------------------------------------
# Audio parameters
# ---------------------------------------------------------------------------
SAMPLE_RATE = 44100
DURATION_SEC = 60
BPM = 68
BEAT_SEC = 60 / BPM

# Pentatonic scale: 角调式 (E-pentatonic: E G A C D)
# Root at E4 (330 Hz), with octave variations
PENTATONIC = {
    "E3": 165.0,   # 角 (root, lower octave)
    "G3": 196.0,   # 徵
    "A3": 220.0,   # 羽
    "C4": 261.6,   # 宫
    "D4": 293.7,   # 商
    "E4": 329.6,   # 角 (root)
    "G4": 392.0,   # 徵
    "A4": 440.0,   # 羽
    "C5": 523.3,   # 宫
    "D5": 587.3,   # 商
    "E5": 659.3,   # 角
}

# Melody pattern: (note_name, beats) — slow, calming, pentatonic
# Designed to feel like a traditional guzheng meditation piece
MELODY = [
    # Intro — gentle rising
    ("E4", 2), ("G4", 2), ("A4", 2), ("E4", 2),
    # Phrase 1
    ("E4", 1.5), ("G4", 0.5), ("A4", 2), ("C5", 1), ("A4", 1), ("G4", 2),
    # Phrase 2 — descent
    ("A4", 1.5), ("G4", 0.5), ("E4", 2), ("D4", 1), ("C4", 1), ("A3", 2),
    # Phrase 3 — mid register
    ("G4", 2), ("A4", 1), ("C5", 1), ("D5", 2), ("C5", 1), ("A4", 1), ("G4", 2),
    # Bridge — calm
    ("E4", 2), ("D4", 1), ("C4", 1), ("A3", 2), ("G3", 1), ("E3", 1), ("A3", 2),
    # Phrase 4 — return
    ("C4", 1), ("D4", 1), ("E4", 2), ("G4", 1.5), ("A4", 0.5), ("E4", 2),
    ("G4", 1), ("A4", 1), ("C5", 2), ("A4", 1), ("G4", 1), ("E4", 2),
    # Outro
    ("C4", 1), ("D4", 1), ("E4", 1), ("C4", 1), ("A3", 2), ("E4", 3),
]

# Gentle volume envelope: attack, sustain, release
ENVELOPE = {
    "attack": 0.05,   # 50ms fade in
    "release": 0.15,  # 150ms fade out
}


def sine_wave(freq: float, duration_sec: float, sample_rate: int = SAMPLE_RATE) -> list[float]:
    """Generate a sine wave at the given frequency with envelope."""
    n_samples = int(duration_sec * sample_rate)
    attack_samples = int(ENVELOPE["attack"] * sample_rate)
    release_samples = int(ENVELOPE["release"] * sample_rate)

    samples = []
    for i in range(n_samples):
        t = i / sample_rate
        # Main tone with soft harmonics (simulating plucked string)
        value = (
            math.sin(2 * math.pi * freq * t) * 0.6
            + math.sin(2 * math.pi * freq * 2 * t) * 0.2   # 2nd harmonic
            + math.sin(2 * math.pi * freq * 3 * t) * 0.08  # 3rd harmonic
        )

        # Volume envelope
        envelope_vol = 1.0
        if i < attack_samples:
            envelope_vol = i / attack_samples
        elif i >= n_samples - release_samples:
            envelope_vol = (n_samples - i) / release_samples

        # Overall volume: 0.35 prevents clipping with harmonics
        samples.append(value * envelope_vol * 0.35)

    return samples


def generate() -> Path:
    """Generate the demo audio file."""
    output_dir = Path(__file__).resolve().parents[1] / "frontend" / "static" / "music"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "jiao-demo.wav"

    all_samples: list[float] = []
    time_pos = 0.0

    for note_name, beats in MELODY:
        freq = PENTATONIC[note_name]
        duration = beats * BEAT_SEC * 0.85  # slight gap between notes (legato feel)
        gap = beats * BEAT_SEC * 0.15

        # Note
        all_samples.extend(sine_wave(freq, duration))
        # Silence gap
        all_samples.extend([0.0] * int(gap * SAMPLE_RATE))
        time_pos += beats * BEAT_SEC

    # Normalize
    max_val = max(abs(s) for s in all_samples) if all_samples else 1.0
    if max_val > 0:
        all_samples = [s / max_val * 0.8 for s in all_samples]

    # Write WAV
    with wave.open(str(output_path), "w") as wf:
        wf.setnchannels(1)  # mono
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(SAMPLE_RATE)
        for sample in all_samples:
            # Clamp to [-1, 1] then convert to 16-bit int
            clamped = max(-1.0, min(1.0, sample))
            int_sample = int(clamped * 32767)
            wf.writeframes(struct.pack("<h", int_sample))

    return output_path


if __name__ == "__main__":
    path = generate()
    size_mb = path.stat().st_size / (1024 * 1024)
    print(f"Generated: {path}")
    print(f"Duration: {DURATION_SEC}s, BPM: {BPM}, Scale: E-pentatonic (角调式)")
    print(f"File size: {size_mb:.1f} MB")
    print("License: project-owned, no copyright issues.")
