"""Shared deterministic energy and structure projection for Agent3 output."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GenerationDesign:
    """Transport and public presentation view of one existing music decision."""

    intro_seconds: int
    main_seconds: int
    outro_seconds: int
    energy_curve: str

    @property
    def structure_value(self) -> str:
        parts = []
        if self.intro_seconds > 0:
            parts.append("渐入")
        if self.main_seconds > 0:
            parts.append("稳定展开")
        if self.outro_seconds > 0:
            parts.append("渐收")
        return " · ".join(parts) or "完整展开"

    @property
    def structure_explanation(self) -> str:
        return f"本次采用{self.structure_value}的结构安排，使音乐段落保持自然衔接。"


def derive_generation_design(*, bpm: int, duration_seconds: int) -> GenerationDesign:
    """Project the existing Agent3 BPM/duration decision without new inference."""

    intro = min(60, max(1, duration_seconds // 6))
    outro = min(60, max(1, duration_seconds // 6))
    main = duration_seconds - intro - outro
    if main < 0:
        intro = duration_seconds // 2
        outro = duration_seconds - intro
        main = 0

    if bpm <= 68:
        energy_curve = "平稳舒缓"
    elif bpm <= 78:
        energy_curve = "平稳专注"
    else:
        energy_curve = "轻快有活力"

    return GenerationDesign(
        intro_seconds=intro,
        main_seconds=main,
        outro_seconds=outro,
        energy_curve=energy_curve,
    )
