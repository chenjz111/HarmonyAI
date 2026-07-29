from __future__ import annotations

from datetime import datetime, timezone

from .models import EvaluationResult, PrescriptionResult, WorkflowInput, WorkflowResult
from .prompt_engine import PromptEngine


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _evaluate(data: WorkflowInput) -> EvaluationResult:
    if not data.emotion_scores:
        dominant_emotion = "neutral"
        score = 0
        confidence = 0.3
        reason = ["fallback: 未提供情绪评分，使用中性画像"]
    else:
        dominant_emotion, score = max(data.emotion_scores.items(), key=lambda item: item[1])
        confidence = min(0.95, max(0.4, score / 100))
        reason = [f"主导情绪 {dominant_emotion} 得分为 {score}"]

    return EvaluationResult(
        agent_id="evaluation_agent",
        agent_version="1.0.0",
        user_id=data.user_id,
        session_id=data.session_id,
        dominant_emotion=dominant_emotion,
        emotion_score=score,
        confidence=confidence,
        reason=reason,
        warnings={"recommend_professional": confidence < 0.4},
        processing_time_ms=0,
        timestamp=_timestamp(),
    )


def _prescribe(data: WorkflowInput, evaluation: EvaluationResult, prompt_engine: PromptEngine) -> PrescriptionResult:
    tone_id = {"fear": "yu", "neutral": "gong"}.get(evaluation.dominant_emotion, "jiao")
    tone_name = {"jiao": "角调式", "yu": "羽调式", "gong": "宫调式"}[tone_id]
    bpm = 68 if tone_id == "jiao" else 60
    prompt = prompt_engine.render(
        "CN_V1",
        {"duration": 15, "bpm": bpm, "tone": tone_name, "style": "中国民族风纯音乐"},
    )
    return PrescriptionResult(
        agent_id="prescription_agent",
        agent_version="1.0.0",
        user_id=data.user_id,
        session_id=data.session_id,
        tone_id=tone_id,
        tone_name=tone_name,
        bpm=bpm,
        instruments=["古筝", "古琴"],
        prompt=prompt,
        confidence=evaluation.confidence,
        reason=[f"规则映射：{evaluation.dominant_emotion} → {tone_name}"],
        warnings=evaluation.warnings,
        processing_time_ms=0,
        timestamp=_timestamp(),
    )


def run_workflow(data: WorkflowInput, prompt_engine: PromptEngine) -> WorkflowResult:
    evaluation = _evaluate(data)
    prescription = _prescribe(data, evaluation, prompt_engine)
    return WorkflowResult(evaluation=evaluation, prescription=prescription)
