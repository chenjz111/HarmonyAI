from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .prompt_engine import PromptEngine
from .real_agents import MVP_SYNDROMES


_DISCLAIMER = "本结果仅用于音乐调养参考，不构成医学诊断。"
_TONE_CONFIG = {
    "jiao": {"tone_name": "角调", "bpm": 68, "instruments": ["古筝", "古琴"]},
    "zhi": {"tone_name": "徵调", "bpm": 70, "instruments": ["琵琶", "古琴"]},
    "gong": {"tone_name": "宫调", "bpm": 62, "instruments": ["编钟", "古琴"]},
    "shang": {"tone_name": "商调", "bpm": 66, "instruments": ["二胡", "洞箫"]},
    "yu": {"tone_name": "羽调", "bpm": 58, "instruments": ["箫", "古琴"]},
}


def run_prescription_v2(
    diagnosis: Mapping[str, object],
    knowledge_store: object | None = None,
) -> dict:
    """Return only a matched music recommendation for a safe, supported tendency."""
    diagnosis_data = dict(diagnosis)
    withheld_reason = _withheld_reason(diagnosis_data)
    if withheld_reason is not None:
        return _withheld(withheld_reason)

    primary = diagnosis_data["primary_tendency"]
    assert isinstance(primary, Mapping)
    tendency_id = primary["id"]
    assert isinstance(tendency_id, str)
    syndrome = MVP_SYNDROMES[tendency_id]
    tone_id = str(syndrome["tone_id"])
    tone = _TONE_CONFIG[tone_id]
    prompt = PromptEngine(Path(__file__).resolve().parents[2] / "prompt" / "v1").render(
        "CN_V1",
        {
            "duration": 15,
            "bpm": tone["bpm"],
            "tone": tone["tone_name"],
            "style": "传统五声音阶疗愈音乐",
        },
    )
    evidence, knowledge_degradation, warnings = _knowledge_evidence(
        knowledge_store,
        str(syndrome["name"]),
    )
    return {
        "agent_id": "prescription_agent",
        "status": "success",
        "generation_mode": "matched",
        "music_feature": {
            "tone_id": tone_id,
            "tone_name": tone["tone_name"],
            "bpm": tone["bpm"],
            "duration_minutes": 15,
            "instruments": tone["instruments"],
        },
        "prompt_template": {
            "template_id": prompt.template_id,
            "template_version": prompt.template_version,
            "text": prompt.text,
        },
        "recommendation_reasons": [
            f"辅助辨证倾向 {tendency_id} 映射为{tone['tone_name']}音乐参数。",
            "已结合知识库检索证据。" if evidence else "已使用审核本地规则。",
        ],
        "parameter_sources": {
            "tone_id": "reviewed_local_rule",
            "bpm": "reviewed_local_rule",
            "duration_minutes": "reviewed_local_rule",
            "instruments": "reviewed_local_rule",
            "prompt": "reviewed_local_rule",
        },
        "evidence": evidence,
        "warnings": warnings,
        "knowledge_degradation": knowledge_degradation,
        "disclaimer": _DISCLAIMER,
    }


def _withheld_reason(diagnosis: Mapping[str, object]) -> str | None:
    if diagnosis.get("status") == "blocked_safety":
        return "SAFETY_BLOCKED"
    if diagnosis.get("status") == "degraded" or diagnosis.get("assessment_status") == "degraded":
        return "ASSESSMENT_DEGRADED"
    confidence = diagnosis.get("confidence")
    if not isinstance(confidence, Mapping) or confidence.get("level") == "low":
        return "LOW_CONFIDENCE"
    score = confidence.get("score")
    if not isinstance(score, (int, float)) or score < 0.4:
        return "LOW_CONFIDENCE"
    conflicts = diagnosis.get("conflicts")
    if isinstance(conflicts, list) and len(conflicts) >= 2:
        return "SEVERE_CONFLICTS"
    primary = diagnosis.get("primary_tendency")
    if not isinstance(primary, Mapping) or primary.get("id") not in MVP_SYNDROMES:
        return "UNKNOWN_TENDENCY"
    return None


def _withheld(reason: str) -> dict:
    return {
        "agent_id": "prescription_agent",
        "status": "blocked_safety" if reason == "SAFETY_BLOCKED" else "degraded",
        "action": "withhold_music_recommendation",
        "generation_mode": "withheld",
        "warnings": ["当前信息不适合输出普通音乐调养建议。"],
        "withheld_reason": reason,
        "disclaimer": _DISCLAIMER,
    }


def _knowledge_evidence(
    knowledge_store: object | None,
    query_text: str,
) -> tuple[list[dict[str, object]], dict[str, object], list[str]]:
    if knowledge_store is None:
        return (
            [],
            {"active": True, "reason_codes": ["KNOWLEDGE_STORE_NOT_CONFIGURED"]},
            ["知识库未配置，已使用审核本地规则。"],
        )
    try:
        query = getattr(knowledge_store, "query")
        hits = query(query_text, limit=3)
        evidence = [
            {
                "text": hit.text,
                "metadata": dict(hit.metadata),
                "distance": hit.distance,
            }
            for hit in hits
        ]
    except Exception:
        return (
            [],
            {"active": True, "reason_codes": ["KNOWLEDGE_RETRIEVAL_FAILED"]},
            ["知识检索失败，已使用审核本地规则。"],
        )
    return evidence, {"active": False, "reason_codes": []}, []
