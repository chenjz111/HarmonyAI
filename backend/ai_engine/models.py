from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping

from .prompt_engine import RenderedPrompt


@dataclass(frozen=True)
class WorkflowInput:
    user_id: str
    session_id: str
    emotion_scores: Mapping[str, int]


@dataclass(frozen=True)
class EvaluationResult:
    agent_id: str
    agent_version: str
    user_id: str
    session_id: str
    dominant_emotion: str
    emotion_score: int
    confidence: float
    reason: list[str]
    warnings: dict[str, bool]
    processing_time_ms: int
    timestamp: str


@dataclass(frozen=True)
class PrescriptionResult:
    agent_id: str
    agent_version: str
    user_id: str
    session_id: str
    tone_id: str
    tone_name: str
    bpm: int
    instruments: list[str]
    prompt: RenderedPrompt
    confidence: float
    reason: list[str]
    warnings: dict[str, bool]
    processing_time_ms: int
    timestamp: str


@dataclass(frozen=True)
class WorkflowResult:
    evaluation: EvaluationResult
    prescription: PrescriptionResult

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
