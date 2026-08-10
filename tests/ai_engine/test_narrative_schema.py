import pytest

from backend.ai_engine.providers import MockProvider


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
