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


class SequenceProvider:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    async def complete_json(self, request):
        self.requests.append(request)
        data = self.responses[len(self.requests) - 1]
        return ProviderResponse(
            data=data,
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
    assert "tension_worry" in prompt
    assert "sleep_disturbance" in prompt
    assert "chest_tightness" in prompt
    assert "life_event" in prompt


@pytest.mark.asyncio
async def test_extraction_preserves_unknown_time_window_as_none():
    from backend.ai_engine.narrative_schema import extract_narrative

    provider = MockProvider(
        {
            "items": [
                {
                    "category": "emotion_state",
                    "label": "tension_worry",
                    "value": 3,
                    "polarity": "present",
                    "time_window": None,
                    "quote": "最近有些紧张",
                    "source_ref": "narrative:sentence_1",
                    "extraction_confidence": 0.8,
                    "negated": False,
                }
            ]
        }
    )

    result = await extract_narrative(
        "最近有些紧张。",
        source_type="narrative",
        provider=provider,
    )

    assert result.status == "processed"
    assert result.items[0].time_window is None


@pytest.mark.asyncio
async def test_extraction_maps_canonical_label_category_alias():
    from backend.ai_engine.narrative_schema import extract_narrative

    provider = MockProvider(
        {
            "items": [
                {
                    "category": "tension_worry",
                    "label": "tension_worry",
                    "value": 3,
                    "polarity": "present",
                    "time_window": None,
                    "quote": "最近有些紧张",
                    "source_ref": "narrative:sentence_1",
                    "extraction_confidence": 0.8,
                    "negated": False,
                }
            ]
        }
    )

    result = await extract_narrative(
        "最近有些紧张。",
        source_type="narrative",
        provider=provider,
    )

    assert result.status == "processed"
    assert result.items[0].category == "emotion_state"


@pytest.mark.asyncio
async def test_extraction_retries_one_schema_failure_then_uses_valid_response():
    from backend.ai_engine.narrative_schema import extract_narrative

    valid = {
        "items": [
            {
                "category": "emotion_state",
                "label": "tension_worry",
                "value": 3,
                "polarity": "present",
                "time_window": "过去两周",
                "quote": "最近有些紧张",
                "source_ref": "narrative:sentence_1",
                "extraction_confidence": 0.8,
                "negated": False,
            }
        ]
    }
    provider = SequenceProvider({"items": {}}, valid)

    result = await extract_narrative(
        "最近有些紧张。",
        source_type="narrative",
        provider=provider,
    )

    assert result.status == "processed"
    assert result.items[0].label == "tension_worry"
    assert len(provider.requests) == 2


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
@pytest.mark.asyncio
async def test_extraction_prompt_requests_all_grounded_facts_as_separate_items():
    from backend.ai_engine.narrative_schema import extract_narrative

    provider = CapturingProvider()
    await extract_narrative(
        "????????????????????",
        source_type="narrative",
        provider=provider,
    )

    prompt = provider.request.system_prompt
    assert "????" in prompt
    assert "????????" in prompt
    assert "????" in prompt
    assert "??" in prompt
