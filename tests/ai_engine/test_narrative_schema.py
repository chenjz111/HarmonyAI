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
        "work pressure, racing mind, chest tightness",
        source_type="narrative",
        provider=provider,
    )

    prompt = provider.request.system_prompt
    assert "Scan every sentence" in prompt
    assert "Emit different facts as separate items" in prompt
    assert "work or exam pressure" in prompt.lower()
    assert "chest tightness" in prompt.lower()
    assert "\u5de5\u4f5c\u538b\u529b\u7279\u522b\u5927" in prompt
    assert "\u6ca1\u6709" in prompt


@pytest.mark.asyncio
async def test_life_event_translation_normalizes_to_grounded_trigger_span():
    from backend.ai_engine.narrative_schema import extract_narrative

    provider = MockProvider(
        {
            "items": [
                {
                    "category": "life_event",
                    "label": "life_event",
                    "value": "work_pressure",
                    "polarity": "present",
                    "time_window": None,
                    "quote": "work pressure is intense",
                    "source_ref": "narrative:sentence_1",
                    "extraction_confidence": 0.9,
                    "negated": False,
                }
            ]
        }
    )

    result = await extract_narrative(
        "Recently, work pressure is intense.",
        source_type="narrative",
        provider=provider,
    )

    assert result.status == "processed"
    assert result.items[0].value == "work pressure"


@pytest.mark.asyncio
async def test_extraction_prompt_requires_grounded_negated_items():
    from backend.ai_engine.narrative_schema import extract_narrative

    provider = CapturingProvider()
    await extract_narrative(
        "I am not feeling low.",
        source_type="narrative",
        provider=provider,
    )

    prompt = provider.request.system_prompt
    assert "negated statements" in prompt
    assert "polarity=absent" in prompt
    assert "negated=true" in prompt
@pytest.mark.asyncio
async def test_grounded_lexical_supplement_fills_clear_canonical_signals():
    from backend.ai_engine.narrative_schema import extract_narrative

    text = (
        "\u6700\u8fd1\u4e24\u5468\u5de5\u4f5c\u538b\u529b\u5f88\u5927\uff0c"
        "\u8111\u5b50\u505c\u4e0d\u4e0b\u6765\uff0c\u80f8\u53e3\u53d1\u95f7\u3002"
    )
    result = await extract_narrative(
        text,
        source_type="narrative",
        provider=MockProvider({"items": []}),
    )

    labels = {item.label for item in result.items}
    assert {"tension_worry", "overthinking", "chest_tightness", "life_event", "duration"} <= labels
    life_event = next(item for item in result.items if item.label == "life_event")
    assert life_event.value == "\u5de5\u4f5c\u538b\u529b"
    assert life_event.quote in text


@pytest.mark.asyncio
async def test_grounded_lexical_supplement_preserves_explicit_good_state_as_absence():
    from backend.ai_engine.narrative_schema import extract_narrative

    text = "\u8fd9\u6bb5\u65f6\u95f4\u72b6\u6001\u8fd8\u884c\uff0c\u6ca1\u4ec0\u4e48\u7279\u522b\u4e0d\u8212\u670d\u7684\u3002"
    result = await extract_narrative(
        text,
        source_type="narrative",
        provider=MockProvider({"items": []}),
    )

    low_mood = next(item for item in result.items if item.label == "low_mood")
    assert low_mood.polarity == "absent"
    assert low_mood.negated is True
    assert low_mood.value == 0
