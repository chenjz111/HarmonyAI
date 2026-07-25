"""Tests for narrative_text feature — Sprint 2.

Covers:
  1. Empty text compatibility (no regression)
  2. Normal free text analysis
  3. Qwen unavailable degradation
  4. Invalid JSON degradation
  5. Oversized text truncation
"""
import json

from backend.ai_engine.narrative_schema import (
    NarrativeAnalysis,
    NARRATIVE_SYSTEM_PROMPT,
    check_safety_alert,
    sanitize_narrative,
    MAX_NARRATIVE_LENGTH,
)
from backend.ai_engine.real_agents import AssessmentAgent


# ── Fake LLM for testing ──

class FakeNarrativeLLM:
    """Returns a valid narrative analysis JSON."""

    def __init__(self, response=None):
        self._response = response or {
            "life_events": [
                {"description": "工作压力大", "timeframe": "recent"}
            ],
            "emotion_signals": [
                {"emotion": "anxiety", "intensity": 72, "evidence": "失眠烦躁"}
            ],
            "physical_signals": [
                {"symptom": "失眠", "severity": "moderate", "evidence": "入睡困难"}
            ],
            "evidence": "工作压力、失眠",
            "summary": "用户近期工作压力大，伴随失眠和焦虑",
            "needs_confirmation": False,
        }

    def complete_json(self, system_prompt, user_prompt):
        return self._response


class FakeInvalidJSONLLM:
    """Returns truly invalid JSON (wrong types) — triggers retry then fallback."""

    def complete_json(self, system_prompt, user_prompt):
        # emotion_signals item with wrong intensity type
        return {"emotion_signals": [{"emotion": "anxiety", "intensity": "high", "evidence": "x"}],
                "evidence": "some text", "summary": "test"}


class FakeErrorLLM:
    """Simulates Qwen unavailability."""

    def __init__(self):
        self.call_count = 0

    def complete_json(self, system_prompt, user_prompt):
        self.call_count += 1
        from backend.ai_engine.providers import LLMProviderError
        raise LLMProviderError("Qwen unavailable")


# ── Test 1: Empty text — no regression ──

def test_empty_narrative_text_runs_questionnaire_only():
    """When narrative_text is None/empty, existing questionnaire logic runs unchanged."""
    result = AssessmentAgent(llm=None).run({
        "questionnaire": {"sleep": "最近睡不好"},
        "narrative_text": None,
    })
    env = result["assessment"]
    assert env["output"]["analysis_mode"] == "questionnaire_only"
    assert env["output"]["degraded"] is True
    assert "emotion_profile" in env["output"]


def test_empty_whitespace_narrative_is_treated_as_none():
    """Whitespace-only narrative_text is sanitized to None."""
    result = AssessmentAgent(llm=None).run({
        "questionnaire": {"sleep": "最近睡不好"},
        "narrative_text": "   \n  ",
    })
    env = result["assessment"]
    assert env["output"]["analysis_mode"] == "questionnaire_only"


# ── Test 2: Normal free text analysis ──

def test_narrative_with_llm_produces_text_and_questionnaire_mode():
    """When narrative_text is provided and LLM is available, returns integrated analysis."""
    llm = FakeNarrativeLLM()
    result = AssessmentAgent(llm=llm).run({
        "questionnaire": {"sleep": "最近睡不好"},
        "narrative_text": "最近工作压力很大，晚上总睡不着，白天很烦躁",
    })
    env = result["assessment"]
    assert env["output"]["analysis_mode"] == "text_and_questionnaire"
    assert env["output"]["degraded"] is False
    assert "narrative_analysis" in env["output"]
    na = env["output"]["narrative_analysis"]
    assert len(na["emotion_signals"]) >= 1
    assert len(na["life_events"]) >= 1


# ── Test 3: Qwen unavailable degradation ──

def test_narrative_without_llm_degrades_gracefully():
    """When LLM is None, narrative_text is ignored and questionnaire mode runs."""
    result = AssessmentAgent(llm=None).run({
        "questionnaire": {"sleep": "最近睡不好"},
        "narrative_text": "最近压力很大，睡不好",
    })
    env = result["assessment"]
    assert env["output"]["analysis_mode"] == "questionnaire_only"
    assert env["output"]["degraded"] is True
    assert env["status"] == "degraded"


def test_narrative_with_error_llm_degrades():
    """When LLM raises errors, falls back to questionnaire_only."""
    result = AssessmentAgent(llm=FakeErrorLLM()).run({
        "questionnaire": {"sleep": "最近睡不好"},
        "narrative_text": "最近压力很大",
    })
    env = result["assessment"]
    assert env["output"]["analysis_mode"] == "questionnaire_only"
    assert env["output"]["degraded"] is True


# ── Test 4: Invalid JSON degradation ──

def test_narrative_with_invalid_json_degrades_after_retry():
    """When LLM returns invalid JSON, retry fails, fallback to questionnaire_only."""
    result = AssessmentAgent(llm=FakeInvalidJSONLLM()).run({
        "questionnaire": {"sleep": "最近睡不好"},
        "narrative_text": "最近压力很大，睡不好",
    })
    env = result["assessment"]
    assert env["output"]["analysis_mode"] == "questionnaire_only"
    assert env["output"]["degraded"] is True
    assert "emotion_profile" in env["output"]


# ── Test 5: Oversized text ──

def test_narrative_max_length():
    """sanitize_narrative caps at MAX_NARRATIVE_LENGTH."""
    long_text = "焦" * 2000
    result = sanitize_narrative(long_text)
    assert result is not None
    assert len(result) <= MAX_NARRATIVE_LENGTH


# ── Safety check tests ──

def test_safety_alert_detects_self_harm_keywords():
    assert check_safety_alert("我最近不想活了，很痛苦") is True
    assert check_safety_alert("最近工作压力大，睡眠不好") is False


def test_safety_alert_blocks_llm_and_returns_help_recommendation():
    """When safety keywords detected, skips LLM and returns professional help action."""
    llm = FakeNarrativeLLM()
    result = AssessmentAgent(llm=llm).run({
        "questionnaire": {"sleep": "差"},
        "narrative_text": "我真的不想活了，没有意义了",
    })
    env = result["assessment"]
    assert env["output"]["action"] == "recommend_professional_help"
    assert env["status"] == "degraded"
    assert env["confidence"] == 0.0


# ── Pydantic schema validation ──

def test_narrative_analysis_schema_rejects_invalid_types():
    """NarrativeAnalysis rejects invalid types for required fields."""
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        NarrativeAnalysis(emotion_signals=[{"emotion": "anxiety", "intensity": "not_a_number"}])


def test_narrative_analysis_schema_accepts_valid_data():
    na = NarrativeAnalysis(
        life_events=[{"description": "加班", "timeframe": "recent"}],
        emotion_signals=[{"emotion": "anxiety", "intensity": 70, "evidence": "烦躁"}],
        physical_signals=[{"symptom": "失眠", "severity": "severe", "evidence": "睡不着"}],
        evidence="加班导致失眠",
        summary="工作压力引发的焦虑状态",
        needs_confirmation=False,
    )
    assert na.emotion_signals[0].emotion == "anxiety"
    assert na.emotion_signals[0].intensity == 70
