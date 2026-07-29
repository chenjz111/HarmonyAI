import json

import pytest

from backend.ai_engine.providers import KnowledgeHit


class FixedJsonLLM:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def complete_json(self, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        return self.response


class InvalidJsonLLM:
    def complete_json(self, system_prompt, user_prompt):
        del system_prompt, user_prompt
        raise json.JSONDecodeError("invalid", "not-json", 0)


class WorkingKnowledgeStore:
    def __init__(self):
        self.queries = []

    def query(self, query_text, limit=3):
        self.queries.append((query_text, limit))
        return [
            KnowledgeHit(
                "角调音乐可用于放松练习。",
                {"source_type": "reviewed"},
                0.9,
                0.1,
            )
        ]


class FailingKnowledgeStore:
    def query(self, query_text, limit=3):
        del query_text, limit
        raise OSError("knowledge unavailable")


class RuntimeFailingKnowledgeStore:
    def query(self, query_text, limit=3):
        del query_text, limit
        raise RuntimeError("unexpected knowledge failure")


def assessment(
    *,
    status="success",
    dimensions=None,
    conflicts=None,
    degradation=None,
):
    return {
        "agent_id": "assessment_agent",
        "session_id": "session-task5",
        "user_id": "user-task5",
        "status": status,
        "analysis_mode": "questionnaire_only",
        "sources_used": [
            {"source": "questionnaire", "status": "used"},
            {"source": "document", "status": "missing"},
            {"source": "narrative", "status": "missing"},
        ],
        "dimensions": dimensions
        or {
            "tension_worry": 100,
            "overthinking": 25,
            "irritability_anger": 75,
            "low_mood": 0,
            "interest_loss": 0,
            "fear_unease": 0,
            "sleep_disturbance": 25,
            "low_energy": 0,
            "appetite_change": 0,
            "daily_impact": 0,
        },
        "evidence": [
            {
                "claim": "紧张担忧较高",
                "sources": ["questionnaire:q02"],
                "summary": "过去七天频率较高。",
            }
        ],
        "conflicts": [] if conflicts is None else conflicts,
        "missing_information": ["document", "narrative"],
        "safety": {
            "status": "blocked_safety" if status == "blocked_safety" else "success",
            "level": "high" if status == "blocked_safety" else "none",
            "flags": ["self_harm_thoughts"] if status == "blocked_safety" else [],
            "reason_codes": ["SAFETY_SELF_HARM_OR_SUICIDE"]
            if status == "blocked_safety"
            else [],
            "block_standard_prescription": status == "blocked_safety",
        },
        "degradation": degradation
        or {"active": status == "degraded", "reason_codes": []},
    }


def normal_diagnosis(**overrides):
    diagnosis = {
        "status": "success",
        "confidence": {"level": "high", "score": 0.85},
        "primary_tendency": {
            "id": "syd_001",
            "label": "肝郁化火",
            "score": 87.5,
            "element": "木",
            "organs": ["肝"],
            "supporting_dimensions": [
                "tension_worry",
                "irritability_anger",
            ],
        },
        "secondary_tendencies": [],
        "conflicts": [],
        "warnings": [],
        "assessment_status": "success",
        "assessment_degradation": {"active": False, "reason_codes": []},
        "assessment_sources": [
            {"source": "questionnaire", "status": "used"},
        ],
    }
    diagnosis.update(overrides)
    return diagnosis


def test_multiple_independent_dimensions_create_explainable_whitelisted_tendency():
    from backend.ai_engine.diagnosis_v2 import run_diagnosis_v2

    result = run_diagnosis_v2(
        assessment(
            dimensions={
                "tension_worry": 100,
                "overthinking": 0,
                "irritability_anger": 75,
                "low_mood": 0,
                "interest_loss": 0,
                "fear_unease": 0,
                "sleep_disturbance": 0,
                "low_energy": 0,
                "appetite_change": 0,
                "daily_impact": 0,
            }
        )
    )

    assert result["status"] == "success"
    assert result["presentation"] == {"title": "辅助辨证倾向"}
    assert result["disclaimer"] == "本结果仅用于音乐调养参考，不构成医学诊断。"
    assert result["primary_tendency"] == {
        "id": "syd_001",
        "label": "肝郁化火",
        "score": 87.5,
        "element": "木",
        "organs": ["肝"],
        "supporting_dimensions": ["tension_worry", "irritability_anger"],
    }
    assert result["secondary_tendencies"] == []
    assert result["evidence_summary"] == [
        {
            "tendency_id": "syd_001",
            "dimensions": ["tension_worry", "irritability_anger"],
            "sources": ["questionnaire:q02", "questionnaire:q04"],
        }
    ]
    assert result["assessment_sources"] == [
        {"source": "questionnaire", "status": "used"},
        {"source": "document", "status": "missing"},
        {"source": "narrative", "status": "missing"},
    ]
    assert result["information_completeness"] == {
        "level": "partial",
        "missing": ["document", "narrative"],
    }
    assert result["degradation"] == {"active": False, "reason_codes": []}
    assert "diagnosis" not in json.dumps(result, ensure_ascii=False).casefold()


def test_one_question_cannot_directly_determine_a_tendency():
    from backend.ai_engine.diagnosis_v2 import run_diagnosis_v2

    result = run_diagnosis_v2(
        assessment(
            dimensions={
                "tension_worry": 100,
                "overthinking": 0,
                "irritability_anger": 0,
                "low_mood": 0,
                "interest_loss": 0,
                "fear_unease": 0,
                "sleep_disturbance": 0,
                "low_energy": 0,
                "appetite_change": 0,
                "daily_impact": 0,
            }
        )
    )

    assert result["status"] == "degraded"
    assert result["primary_tendency"] is None
    assert result["confidence"] == {"level": "low", "score": 0.2}
    assert result["warnings"] == ["信息不足：至少需要两个独立维度支持辅助辨证倾向。"]
    assert result["degradation"] == {
        "active": True,
        "reason_codes": ["INSUFFICIENT_INDEPENDENT_DIMENSIONS"],
    }


def test_two_independent_positive_dimension_scores_are_a_local_candidate():
    from backend.ai_engine.diagnosis_v2 import run_diagnosis_v2

    result = run_diagnosis_v2(
        assessment(
            dimensions={
                "tension_worry": 25,
                "overthinking": 25,
                "irritability_anger": 0,
                "low_mood": 0,
                "interest_loss": 0,
                "fear_unease": 0,
                "sleep_disturbance": 0,
                "low_energy": 0,
                "appetite_change": 0,
                "daily_impact": 0,
            }
        )
    )

    assert result["status"] == "success"
    assert result["primary_tendency"] == {
        "id": "syd_002",
        "label": "肝气郁结",
        "score": 25.0,
        "element": "木",
        "organs": ["肝"],
        "supporting_dimensions": ["tension_worry", "overthinking"],
    }


def test_blocked_safety_returns_only_a_blocked_assistive_result():
    from backend.ai_engine.diagnosis_v2 import run_diagnosis_v2

    result = run_diagnosis_v2(assessment(status="blocked_safety"))

    assert result["status"] == "blocked_safety"
    assert result["primary_tendency"] is None
    assert result["secondary_tendencies"] == []
    assert result["warnings"] == ["检测到安全风险，已停止普通音乐调养建议。"]
    assert result["degradation"] == {
        "active": True,
        "reason_codes": ["SAFETY_BLOCKED"],
    }


def test_degraded_assessment_and_conflicts_are_preserved_and_lower_confidence():
    from backend.ai_engine.diagnosis_v2 import run_diagnosis_v2

    conflicts = [
        {
            "topic": "sleep",
            "sources": ["document", "narrative"],
            "summary": "两个可靠来源不一致。",
        }
    ]
    result = run_diagnosis_v2(
        assessment(
            status="degraded",
            conflicts=conflicts,
            degradation={"active": True, "reason_codes": ["SOURCE_CONFLICT"]},
        )
    )

    assert result["status"] == "degraded"
    assert result["conflicts"] == conflicts
    assert result["confidence"] == {"level": "low", "score": 0.3}
    assert result["assessment_status"] == "degraded"
    assert result["assessment_degradation"] == {
        "active": True,
        "reason_codes": ["SOURCE_CONFLICT"],
    }
    assert result["degradation"] == {
        "active": True,
        "reason_codes": ["ASSESSMENT_DEGRADED", "SOURCE_CONFLICT"],
    }


@pytest.mark.parametrize(
    ("response", "expected_warning"),
    [
        ("not-an-object", "LLM返回无效结构，已使用本地规则。"),
        ({"tendency_id": "syd_001"}, "LLM缺少必填字段，已使用本地规则。"),
        (
            {"tendency_id": "syd_999", "confidence": 0.9},
            "LLM建议了未授权倾向，已使用本地规则。",
        ),
    ],
)
def test_invalid_or_unknown_llm_suggestion_falls_back_to_local_rules(
    response,
    expected_warning,
):
    from backend.ai_engine.diagnosis_v2 import run_diagnosis_v2

    result = run_diagnosis_v2(assessment(), llm=FixedJsonLLM(response))

    assert result["primary_tendency"]["id"] == "syd_001"
    assert result["status"] == "degraded"
    assert expected_warning in result["warnings"]
    assert result["degradation"]["active"] is True


def test_llm_whitelist_cannot_claim_a_sleep_supported_tendency_when_sleep_is_zero():
    from backend.ai_engine.diagnosis_v2 import run_diagnosis_v2

    result = run_diagnosis_v2(
        assessment(
            dimensions={
                "tension_worry": 100,
                "overthinking": 0,
                "irritability_anger": 75,
                "low_mood": 0,
                "interest_loss": 0,
                "fear_unease": 0,
                "sleep_disturbance": 0,
                "low_energy": 0,
                "appetite_change": 0,
                "daily_impact": 0,
            }
        ),
        llm=FixedJsonLLM({"tendency_id": "syd_003", "confidence": 0.75}),
    )

    assert result["status"] == "degraded"
    assert result["primary_tendency"]["id"] == "syd_001"
    assert result["primary_tendency"]["supporting_dimensions"] == [
        "tension_worry",
        "irritability_anger",
    ]
    assert result["secondary_tendencies"] == []
    assert "sleep_disturbance" not in json.dumps(result, ensure_ascii=False)
    assert result["warnings"] == [
        "LLM建议未通过本地多维证据门槛，已保留本地候选。"
    ]
    assert result["degradation"] == {
        "active": True,
        "reason_codes": ["LLM_UNSUPPORTED_TENDENCY"],
    }


def test_llm_cannot_create_a_tendency_when_no_local_multidimensional_candidate_exists():
    from backend.ai_engine.diagnosis_v2 import run_diagnosis_v2
    from backend.ai_engine.prescription_v2 import run_prescription_v2

    result = run_diagnosis_v2(
        assessment(
            dimensions={
                "tension_worry": 0,
                "overthinking": 0,
                "irritability_anger": 75,
                "low_mood": 0,
                "interest_loss": 0,
                "fear_unease": 0,
                "sleep_disturbance": 0,
                "low_energy": 0,
                "appetite_change": 0,
                "daily_impact": 0,
            }
        ),
        llm=FixedJsonLLM({"tendency_id": "syd_003", "confidence": 0.75}),
    )

    assert result["status"] == "degraded"
    assert result["primary_tendency"] is None
    assert result["secondary_tendencies"] == []
    assert result["confidence"] == {"level": "low", "score": 0.2}
    assert run_prescription_v2(result)["generation_mode"] == "withheld"


def test_malformed_llm_json_exception_falls_back_to_local_rules():
    from backend.ai_engine.diagnosis_v2 import run_diagnosis_v2

    result = run_diagnosis_v2(assessment(), llm=InvalidJsonLLM())

    assert result["status"] == "degraded"
    assert result["primary_tendency"]["id"] == "syd_001"
    assert result["warnings"] == ["LLM返回无效JSON，已使用本地规则。"]
    assert result["degradation"] == {
        "active": True,
        "reason_codes": ["LLM_INVALID_JSON"],
    }


def test_prescription_uses_matched_parameters_reasons_and_chroma_evidence():
    from backend.ai_engine.prescription_v2 import run_prescription_v2

    store = WorkingKnowledgeStore()
    result = run_prescription_v2(normal_diagnosis(), knowledge_store=store)

    assert result["status"] == "success"
    assert result["generation_mode"] == "matched"
    assert result["music_feature"] == {
        "tone_id": "jiao",
        "tone_name": "角调",
        "bpm": 68,
        "duration_minutes": 15,
        "instruments": ["古筝", "古琴"],
    }
    assert result["prompt_template"]["template_id"] == "CN_V1"
    assert result["recommendation_reasons"] == [
        "辅助辨证倾向 syd_001 映射为角调音乐参数。",
        "已结合知识库检索证据。",
    ]
    assert result["parameter_sources"] == {
        "tone_id": "reviewed_local_rule",
        "bpm": "reviewed_local_rule",
        "duration_minutes": "reviewed_local_rule",
        "instruments": "reviewed_local_rule",
        "prompt": "reviewed_local_rule",
    }
    assert result["evidence"] == [
        {
            "text": "角调音乐可用于放松练习。",
            "metadata": {"source_type": "reviewed"},
            "distance": 0.1,
        }
    ]
    assert result["knowledge_degradation"] == {
        "active": False,
        "reason_codes": [],
    }
    assert store.queries == [("肝郁化火", 3)]


@pytest.mark.parametrize(
    ("store", "expected_reason", "expected_warning"),
    [
        (
            None,
            "KNOWLEDGE_STORE_NOT_CONFIGURED",
            "知识库未配置，已使用审核本地规则。",
        ),
        (
            FailingKnowledgeStore(),
            "KNOWLEDGE_RETRIEVAL_FAILED",
            "知识检索失败，已使用审核本地规则。",
        ),
    ],
)
def test_prescription_degrades_knowledge_but_keeps_reviewed_local_music_rules(
    store,
    expected_reason,
    expected_warning,
):
    from backend.ai_engine.prescription_v2 import run_prescription_v2

    result = run_prescription_v2(normal_diagnosis(), knowledge_store=store)

    assert result["status"] == "success"
    assert result["generation_mode"] == "matched"
    assert result["music_feature"]["tone_id"] == "jiao"
    assert result["evidence"] == []
    assert result["warnings"] == [expected_warning]
    assert result["knowledge_degradation"] == {
        "active": True,
        "reason_codes": [expected_reason],
    }


def test_runtime_error_from_knowledge_query_degrades_without_losing_local_music_parameters():
    from backend.ai_engine.prescription_v2 import run_prescription_v2

    result = run_prescription_v2(
        normal_diagnosis(),
        knowledge_store=RuntimeFailingKnowledgeStore(),
    )

    assert result["status"] == "success"
    assert result["generation_mode"] == "matched"
    assert result["music_feature"]["tone_id"] == "jiao"
    assert result["evidence"] == []
    assert result["warnings"] == ["知识检索失败，已使用审核本地规则。"]
    assert result["knowledge_degradation"] == {
        "active": True,
        "reason_codes": ["KNOWLEDGE_RETRIEVAL_FAILED"],
    }


@pytest.mark.parametrize(
    ("diagnosis", "expected_reason"),
    [
        (
            normal_diagnosis(
                status="blocked_safety",
                primary_tendency=None,
                confidence={"level": "low", "score": 0.0},
            ),
            "SAFETY_BLOCKED",
        ),
        (
            normal_diagnosis(
                status="degraded",
                confidence={"level": "low", "score": 0.3},
            ),
            "ASSESSMENT_DEGRADED",
        ),
        (
            normal_diagnosis(confidence={"level": "low", "score": 0.2}),
            "LOW_CONFIDENCE",
        ),
        (
            normal_diagnosis(
                conflicts=[
                    {"topic": "sleep", "sources": ["document", "narrative"]},
                    {"topic": "mood", "sources": ["document", "narrative"]},
                ],
            ),
            "SEVERE_CONFLICTS",
        ),
        (
            normal_diagnosis(
                primary_tendency={
                    "id": "syd_999",
                    "label": "未知",
                    "score": 0.9,
                }
            ),
            "UNKNOWN_TENDENCY",
        ),
    ],
)
def test_all_withheld_paths_never_return_a_normal_music_prescription(
    diagnosis,
    expected_reason,
):
    from backend.ai_engine.prescription_v2 import run_prescription_v2

    result = run_prescription_v2(diagnosis, knowledge_store=WorkingKnowledgeStore())

    assert result == {
        "status": "degraded" if expected_reason != "SAFETY_BLOCKED" else "blocked_safety",
        "action": "withhold_music_recommendation",
        "generation_mode": "withheld",
        "warnings": ["当前信息不适合输出普通音乐调养建议。"],
        "withheld_reason": expected_reason,
        "disclaimer": "本结果仅用于音乐调养参考，不构成医学诊断。",
    }


def test_diagnosis_reads_canonical_emotion_profile_scores():
    from backend.ai_engine.diagnosis_v2 import run_diagnosis_v2

    canonical_assessment = {
        "agent_id": "assessment_agent",
        "session_id": "session-canonical",
        "user_id": "user-canonical",
        "status": "success",
        "analysis_mode": "questionnaire_only",
        "sources_used": [
            {"source": "document", "status": "missing"},
            {"source": "narrative", "status": "missing"},
            {"source": "questionnaire", "status": "used"},
        ],
        "emotion_profile": {
            "primary_states": ["紧张担忧", "烦躁易怒"],
            "secondary_states": [],
            "dimension_scores": {
                "tension_worry": 100,
                "irritability_anger": 75,
            },
            "tcm_emotion_candidates": [],
        },
        "physical_profile": {
            "sleep_disturbance": 25,
            "low_energy": 0,
            "appetite_change": 0,
            "physical_signals": [],
        },
        "life_events": {"triggers": []},
        "assessment_summary": "问卷显示紧张和烦躁较明显。",
        "extracted_evidence": [],
        "conflicts": [],
        "missing_information": ["document", "narrative"],
        "safety_flags": [],
        "degradation": {
            "triggered": False,
            "reason_code": None,
            "fallback": None,
        },
        "warnings": [],
        "disclaimer": "本结果仅用于状态评估与音乐调养参考，不构成医学诊断或治疗建议。",
    }

    result = run_diagnosis_v2(canonical_assessment)

    assert result["status"] == "success"
    assert result["primary_tendency"]["id"] == "syd_001"
    assert result["assessment_degradation"] == {
        "triggered": False,
        "reason_code": None,
        "fallback": None,
    }
