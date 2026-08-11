import pytest

from backend.ai_engine.providers import MockProvider
from backend.ai_engine.sprint4_contracts import ProviderResponse


class CapturingProvider:
    def __init__(self):
        self.request = None

    async def complete_json(self, request):
        self.request = request
        return ProviderResponse(
            data={"items": []},
            provider="mock",
            model="mock",
            latency_ms=0,
            input_tokens=0,
            output_tokens=0,
            attempts=1,
        )


@pytest.mark.asyncio
async def test_extraction_prompt_includes_frozen_output_shape():
    from backend.ai_engine.narrative_schema import extract_narrative

    provider = CapturingProvider()
    result = await extract_narrative(
        "最近两周晚上睡不好。",
        source_type="narrative",
        provider=provider,
    )

    assert result.status == "processed"
    assert provider.request is not None
    prompt = provider.request.system_prompt
    assert '"items"' in prompt
    assert '"category"' in prompt
    assert '"source_ref"' in prompt
    assert "narrative:" in prompt


@pytest.mark.asyncio
async def test_extraction_keeps_quote_time_window_and_negation():
    from backend.ai_engine.narrative_schema import extract_narrative

    provider = MockProvider(
        {
            "items": [
                {
                    "category": "sleep",
                    "label": "sleep_disturbance",
                    "value": 3,
                    "polarity": "present",
                    "time_window": "过去两周",
                    "quote": "最近两周晚上睡不好",
                    "source_ref": "narrative:sentence_1",
                    "extraction_confidence": 0.9,
                    "negated": False,
                },
                {
                    "category": "physical_signal",
                    "label": "chest_pain",
                    "value": False,
                    "polarity": "absent",
                    "time_window": "当前",
                    "quote": "没有胸痛",
                    "source_ref": "narrative:sentence_1",
                    "extraction_confidence": 0.95,
                    "negated": True,
                },
            ]
        }
    )

    result = await extract_narrative(
        "最近两周晚上睡不好，但没有胸痛。",
        source_type="narrative",
        provider=provider,
    )

    assert result.status == "processed"
    assert result.evidence_quotes[0].quote in "最近两周晚上睡不好，但没有胸痛。"
    assert any(item.negated for item in result.items)
