from __future__ import annotations

from typing import Any

from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from .providers import AsyncJsonProvider
from .sprint4_contracts import (
    NarrativeEvidence,
    NarrativeExtractionResult,
    ProviderError,
    ProviderRequest,
)


NARRATIVE_CATEGORIES = frozenset(
    {
        "emotion_state",
        "worry_thought",
        "irritability",
        "mood_interest",
        "fear_unease",
        "sleep",
        "energy",
        "appetite",
        "physical_signal",
        "life_event",
        "duration",
        "daily_impact",
        "goal_and_expectation",
    }
)
_POLARITIES = frozenset(
    {"present", "absent", "reduced", "increased", "unchanged"}
)
_ALLOWED_ITEM_FIELDS = frozenset(
    {
        "category",
        "label",
        "value",
        "polarity",
        "time_window",
        "quote",
        "source_ref",
        "extraction_confidence",
        "negated",
    }
)
_CATEGORY_BY_CANONICAL_LABEL = {
    "tension_worry": "emotion_state",
    "calm_wellbeing": "emotion_state",
    "emotional_recovery": "emotion_state",
    "overthinking": "worry_thought",
    "worry_control": "worry_thought",
    "irritability_anger": "irritability",
    "low_mood": "mood_interest",
    "interest_loss": "mood_interest",
    "fear_unease": "fear_unease",
    "sleep_disturbance": "sleep",
    "unrefreshing_sleep": "sleep",
    "low_energy": "energy",
    "appetite_change": "appetite",
    "chest_tightness": "physical_signal",
    "head_heaviness": "physical_signal",
    "limb_fatigue": "physical_signal",
    "neck_tension": "physical_signal",
    "palpitation": "physical_signal",
    "stomach_discomfort": "physical_signal",
    "sweating": "physical_signal",
    "life_event": "life_event",
    "duration": "duration",
    "daily_impact": "daily_impact",
    "user_goal": "goal_and_expectation",
}


def _narrative_system_prompt(source_type: Literal["narrative", "document"]) -> str:
    categories = ", ".join(sorted(NARRATIVE_CATEGORIES))
    return (
        "你是证据提取器，只返回 JSON，不要 Markdown，不生成诊断或治疗结论。"
        "根对象必须是 {\"items\": [...]}，items 必须是 JSON 数组；没有可靠证据时返回空数组。"
        "每个 item 只能包含并必须包含以下字段："
        "{\"category\":string,\"label\":string,\"value\":string|number|boolean|null,"
        "\"polarity\":\"present|absent|reduced|increased|unchanged\","
        "\"time_window\":string|null,\"quote\":string,\"source_ref\":string,"
        "\"extraction_confidence\":number,\"negated\":boolean}。"
        f"category 只能是：{categories}。"
        "label/value 必须使用以下 canonical 规则："
        "emotion_state label 只能是 tension_worry、calm_wellbeing、emotional_recovery；"
        "worry_thought label 只能是 overthinking、worry_control；"
        "irritability label 必须是 irritability_anger；"
        "mood_interest label 只能是 low_mood、interest_loss；fear_unease label 必须是 fear_unease；"
        "sleep label 只能是 sleep_disturbance、unrefreshing_sleep；energy label 必须是 low_energy；"
        "appetite label 必须是 appetite_change；"
        "physical_signal label 只能是 chest_tightness、head_heaviness、limb_fatigue、neck_tension、palpitation、stomach_discomfort、sweating；value 使用同一个 canonical label；"
        "life_event label 必须是 life_event，value 必须是 quote 中逐字出现的简短事件诱因；"
        "duration label 必须是 duration，value 只能是 1_to_2_weeks、2_weeks_to_1_month、1_to_3_months、over_3_months、recurrent_unclear；"
        "daily_impact label 必须是 daily_impact，value 必须是 0 到 4 的整数；goal_and_expectation label 必须是 user_goal。"
        "无法确定时间时 time_window 必须为 null；polarity 只能逐字使用给定的五个英文枚举。"
        "quote 必须逐字复制自用户原文，禁止改写或补造；"
        "Scan every sentence and extract every grounded fact; do not select only one or two."
        "Emit different facts as separate items. Work or exam pressure is a life_event;"
        "a racing mind is overthinking; irritability is irritability_anger; chest tightness is"
        "chest_tightness; poor sleep is sleep_disturbance. One sentence may support multiple items."
        "Represent grounded negated statements too, using polarity=absent and negated=true."
        f"source_ref 必须以 {source_type}: 开头；"
        "extraction_confidence 必须在 0 到 1 之间。"
    )


async def extract_narrative(
    text: str,
    *,
    source_type: Literal["narrative", "document"],
    provider: AsyncJsonProvider,
) -> NarrativeExtractionResult:
    """Extract grounded evidence from one reliable text source."""
    normalized_text = text.strip() if isinstance(text, str) else ""
    if not normalized_text:
        return NarrativeExtractionResult(
            status="unavailable",
            items=(),
            evidence_quotes=(),
            reason_code="EMPTY_TEXT",
            warnings=("文本为空，未执行结构化提取。",),
        )

    base_prompt = _narrative_system_prompt(source_type)
    last_schema_error: str | None = None

    for schema_attempt in range(2):
        system_prompt = base_prompt
        if schema_attempt:
            system_prompt += (
                " 上一次 JSON 未通过结构校验。请纠正后完整重答；"
                f"校验错误类型：{last_schema_error}。"
            )

        try:
            response = await provider.complete_json(
                ProviderRequest(
                    system_prompt=system_prompt,
                    user_prompt=normalized_text,
                    operation="narrative_extraction",
                    prompt_version="narrative_extraction_v2.1",
                )
            )
        except ProviderError as exc:
            status = "degraded" if exc.retryable else "unavailable"
            return NarrativeExtractionResult(
                status=status,
                items=(),
                evidence_quotes=(),
                reason_code=exc.reason_code,
                warnings=(exc.user_message,),
            )
        except Exception as exc:
            return NarrativeExtractionResult(
                status="unavailable",
                items=(),
                evidence_quotes=(),
                reason_code="PROVIDER_UNEXPECTED_ERROR",
                warnings=(f"文本提取不可用：{type(exc).__name__}",),
            )

        try:
            items = _normalize_items(
                response.data.get("items"),
                normalized_text,
                source_type,
            )
        except ValueError as exc:
            last_schema_error = str(exc)
            if schema_attempt == 0:
                continue
            return NarrativeExtractionResult(
                status="degraded",
                items=(),
                evidence_quotes=(),
                reason_code="NARRATIVE_SCHEMA_ERROR",
                warnings=(last_schema_error,),
                model_metadata=_provider_metadata(response),
            )
        return NarrativeExtractionResult(
            status="processed",
            items=tuple(items),
            evidence_quotes=tuple(items),
            model_metadata=_provider_metadata(response),
        )

    raise AssertionError("schema retry loop exhausted")


def _normalize_items(
    raw_items: object,
    source_text: str,
    source_type: Literal["narrative", "document"],
) -> list[NarrativeEvidence]:
    if isinstance(raw_items, (str, bytes)) or not isinstance(raw_items, list):
        raise ValueError("items must be a JSON array")

    normalized: list[NarrativeEvidence] = []
    for index, raw_item in enumerate(raw_items, start=1):
        if not isinstance(raw_item, Mapping):
            raise ValueError(f"items[{index}] must be an object")
        unknown = set(raw_item) - _ALLOWED_ITEM_FIELDS
        if unknown:
            raise ValueError(f"items[{index}] has unknown fields: {sorted(unknown)}")
        category = raw_item.get("category")
        label = raw_item.get("label")
        if category not in NARRATIVE_CATEGORIES and isinstance(label, str):
            category = _CATEGORY_BY_CANONICAL_LABEL.get(label, category)
        if category not in NARRATIVE_CATEGORIES:
            raise ValueError(f"items[{index}].category is not allowed")
        quote = raw_item.get("quote")
        source_ref = raw_item.get("source_ref")
        time_window = raw_item.get("time_window")
        polarity = raw_item.get("polarity")
        confidence = raw_item.get("extraction_confidence")
        negated = raw_item.get("negated")
        if not isinstance(label, str) or not label.strip():
            raise ValueError(f"items[{index}].label is required")
        if not isinstance(quote, str) or not quote.strip() or quote not in source_text:
            raise ValueError(f"items[{index}].quote must be a source substring")
        value = raw_item.get("value")
        if category == "life_event" and (
            not isinstance(value, str) or not value.strip() or value not in quote
        ):
            value = quote.strip()
        if not isinstance(source_ref, str) or not source_ref.startswith(f"{source_type}:"):
            raise ValueError(f"items[{index}].source_ref must identify the source")
        if time_window is not None and (not isinstance(time_window, str) or not time_window.strip()):
            raise ValueError(f"items[{index}].time_window must be a string or null")
        if polarity not in _POLARITIES:
            raise ValueError(f"items[{index}].polarity is not allowed")
        if type(confidence) not in (int, float) or not 0 <= confidence <= 1:
            raise ValueError(f"items[{index}].extraction_confidence must be 0..1")
        if type(negated) is not bool:
            raise ValueError(f"items[{index}].negated must be boolean")
        normalized.append(
            NarrativeEvidence(
                category=category,
                label=label.strip(),
                value=value,
                polarity=polarity,
                time_window=time_window.strip() if isinstance(time_window, str) else None,
                quote=quote.strip(),
                source_ref=source_ref,
                extraction_confidence=float(confidence),
                negated=negated,
            )
        )
    return normalized


def _provider_metadata(response: object) -> dict[str, object] | None:
    if not hasattr(response, "provider"):
        return None
    return {
        "provider": response.provider,
        "model": response.model,
        "latency_ms": response.latency_ms,
        "tokens_input": response.input_tokens,
        "tokens_output": response.output_tokens,
        "attempts": response.attempts,
        "prompt_version": "narrative_extraction_v2.1",
    }


# Compatibility exports required by the integrated Sprint 4 narrative API.
# The canonical extraction path above remains EvidenceItem-oriented and
# source-grounded; these models preserve the existing consumer-facing shape.
def _coerce_evidence(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(str(item) for item in value if item)
    return str(value) if value else ""


class LifeEvent(BaseModel):
    description: str = Field(..., description="Brief description of the event")
    timeframe: str = Field(default="recent", description="When it happened")


class EmotionSignal(BaseModel):
    emotion: str
    intensity: int = Field(..., ge=0, le=100)
    evidence: str = ""

    _coerce_evidence = field_validator("evidence", mode="before")(_coerce_evidence)


class PhysicalSignal(BaseModel):
    symptom: str
    severity: str = "moderate"
    evidence: str = ""

    _coerce_evidence = field_validator("evidence", mode="before")(_coerce_evidence)


class NarrativeAnalysis(BaseModel):
    model_config = {"extra": "ignore"}

    life_events: list[LifeEvent] = Field(default_factory=list)
    emotion_signals: list[EmotionSignal] = Field(default_factory=list)
    physical_signals: list[PhysicalSignal] = Field(default_factory=list)
    evidence: str = ""
    summary: str = ""
    needs_confirmation: bool = False

    @field_validator("evidence", mode="before")
    @classmethod
    def _coerce_top_evidence(cls, value: Any) -> str:
        return _coerce_evidence(value)


NARRATIVE_SYSTEM_PROMPT = (
    "Extract only factual observations from the user's free text. "
    "Do not diagnose, assign syndrome labels, or suggest treatment. Return JSON."
)
SAFETY_KEYWORDS = (
    "不想活", "自杀", "结束生命", "自残", "伤害自己", "不想活了",
    "kill myself", "self-harm", "suicide", "end my life",
)
MAX_NARRATIVE_LENGTH = 1000


def check_safety_alert(text: str) -> bool:
    normalized = text.lower()
    return any(keyword.lower() in normalized for keyword in SAFETY_KEYWORDS)


def sanitize_narrative(text: str | None) -> str | None:
    if text is None:
        return None
    normalized = text.strip()
    return normalized[:MAX_NARRATIVE_LENGTH] or None
