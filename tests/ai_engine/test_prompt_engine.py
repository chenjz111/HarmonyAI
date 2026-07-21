from pathlib import Path

import pytest

from backend.ai_engine.prompt_engine import PromptEngine, TemplateNotFoundError


def test_render_includes_structured_music_parameters():
    engine = PromptEngine(Path("prompt/v1"))

    result = engine.render("CN_V1", {"duration": 15, "bpm": 68, "tone": "角调式"})

    assert result.template_version == "1.0.0"
    assert "15分钟" in result.text
    assert "68 BPM" in result.text
    assert "角调式" in result.text


def test_missing_template_raises_explicit_error():
    engine = PromptEngine(Path("prompt/v1"))

    with pytest.raises(TemplateNotFoundError):
        engine.render("MISSING", {})


def test_missing_optional_parameter_uses_safe_fallback():
    engine = PromptEngine(Path("prompt/v1"))

    result = engine.render("CN_V1", {"duration": 15})

    assert "60 BPM" in result.text
    assert "纯音乐" in result.text
