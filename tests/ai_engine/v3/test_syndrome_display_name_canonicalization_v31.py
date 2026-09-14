"""User-facing syndrome labels must come from the approved Chinese whitelist.

Agent2 (the diagnosis provider) may phrase ``display_name`` itself; the public
diagnosis read model must instead show the medically approved 证型倾向 wording
loaded from ``knowledge/v3/agent2-syndrome-whitelist-v3.1.json`` by stable
syndrome code.
"""

import asyncio
import dataclasses

import pytest

from backend.app.services.v3 import knowledge_assets
from backend.app.services.v3.knowledge_assets import (
    load_approved_syndrome_display_names,
)

CANONICAL_SYNDROME_DISPLAY_NAMES = {
    "syd_001": "肝郁化火倾向",
    "syd_002": "肝气郁结倾向",
    "syd_003": "心火上炎倾向",
    "syd_004": "心脾两虚倾向",
    "syd_005": "脾虚湿困倾向",
    "syd_006": "肺气虚倾向",
    "syd_007": "肾阴不足倾向",
    "syd_008": "心肾不交倾向",
}


@pytest.fixture(autouse=True)
def _fresh_display_name_cache(monkeypatch):
    monkeypatch.setattr(
        knowledge_assets, "_APPROVED_SYNDROME_DISPLAY_NAMES", None, raising=False
    )


def test_approved_whitelist_maps_all_eight_stable_codes_to_canonical_chinese():
    names = load_approved_syndrome_display_names()

    assert set(names) == set(CANONICAL_SYNDROME_DISPLAY_NAMES)
    assert dict(names) == CANONICAL_SYNDROME_DISPLAY_NAMES
    for name in names.values():
        assert name.endswith("倾向")


def test_unknown_syndrome_code_falls_back_without_raising():
    names = load_approved_syndrome_display_names()

    assert names.get("syndrome_not_in_whitelist", "provider raw value") == (
        "provider raw value"
    )


def test_missing_whitelist_asset_degrades_to_empty_mapping(tmp_path, monkeypatch):
    monkeypatch.setattr(knowledge_assets, "_asset_root", lambda: tmp_path)

    assert dict(load_approved_syndrome_display_names()) == {}


def test_malformed_whitelist_asset_degrades_to_empty_mapping(tmp_path, monkeypatch):
    (tmp_path / "agent2-syndrome-whitelist-v3.1.json").write_text(
        "{ not json", encoding="utf-8"
    )
    monkeypatch.setattr(knowledge_assets, "_asset_root", lambda: tmp_path)

    assert dict(load_approved_syndrome_display_names()) == {}


def _english_provider_pipeline():
    """Run the real V3.1 pipeline with a fake provider returning English labels."""

    from backend.ai_engine.v3.diagnosis_provider import DiagnosisProvider
    from backend.ai_engine.v3.v31_pipeline import execute_v31_ai_pipeline
    from tests.ai_engine.v3.test_v31_pipeline import (
        _confirmed_state,
        _mapping,
        _rag_result,
        _rules,
        _snapshot,
    )

    class Rag:
        def query(self, query):
            del query
            return _rag_result()

    class Backend:
        async def acomplete_json(self, system_prompt, user_prompt):
            del system_prompt, user_prompt
            return {
                "status": "success",
                "candidate_tendencies": [
                    {
                        "syndrome_code": "syd_005",
                        "display_name": "Spleen Deficiency",
                        "relative_support": 0.8,
                        "supporting_fact_ids": ["fact_1"],
                        "contradicting_fact_ids": [],
                        "knowledge_chunk_ids": ["chunk_1"],
                        "reasoning_summary": (
                            "Loose stool and postmeal heaviness are classic indicators."
                        ),
                    }
                ],
                "abstained": False,
                "abstain_reason": None,
            }

    provider = DiagnosisProvider(
        backend=Backend(),
        allowed_syndrome_codes={"syd_005"},
        allowed_fact_ids={"fact_1"},
        allowed_chunk_ids={"chunk_1"},
    )
    return asyncio.run(
        execute_v31_ai_pipeline(
            confirmed_user_state=_confirmed_state(),
            assessment_snapshot=_snapshot(),
            rag_store=Rag(),
            diagnosis_provider=provider,
            tone_mapping=_mapping(),
            generation_parameter_rules=_rules(),
            user_goal={"primary_goal": "sleep"},
        )
    )


def _assessment_ref():
    from backend.app.schemas.v3.assessment import AssessmentRefV31

    return AssessmentRefV31(
        assessment_id="asmt_1",
        revision=1,
        confirmation_status="confirmed",
        flow_contract_version="v3-owner-flow-1",
        input_revision=1,
        safety_policy="deferred_v3",
        safety_status=None,
    )


def _available_element_profile():
    from backend.app.schemas.v3.common import ElementProfile

    return ElementProfile(
        status="available",
        weights={"wood": 0.0, "fire": 1.0, "earth": 0.0, "metal": 0.0, "water": 0.0},
        score_semantics="relative_element_support",
    )


def test_public_read_model_uses_canonical_chinese_name_not_provider_english():
    from backend.app.services.v3.diagnosis_service import _diagnosis_from_v31_pipeline

    pipeline = _english_provider_pipeline()
    # The raw English provider value is still available for provenance/logs.
    assert pipeline.diagnosis.candidate_tendencies[0].display_name == (
        "Spleen Deficiency"
    )

    result = _diagnosis_from_v31_pipeline(
        pipeline,
        diagnosis_id="diag_canonical",
        assessment_ref=_assessment_ref(),
        element_profile=_available_element_profile(),
    )

    root = result.root
    assert root.presentation.primary_tendency == "脾虚湿困倾向"
    assert [candidate.display_name for candidate in root.candidate_tendencies] == [
        "脾虚湿困倾向"
    ]
    assert root.candidate_tendencies[0].syndrome_code == "syd_005"
    assert "Spleen Deficiency" not in root.presentation.primary_tendency


def test_unknown_provider_syndrome_code_falls_back_to_provider_display_name():
    from backend.app.services.v3.diagnosis_service import _diagnosis_from_v31_pipeline

    pipeline = _english_provider_pipeline()
    # Re-label the already-materialised response with a code outside the
    # approved whitelist to prove the fallback never crashes or invents a name.
    updated = pipeline.diagnosis.model_copy(
        update={
            "candidate_tendencies": [
                pipeline.diagnosis.candidate_tendencies[0].model_copy(
                    update={"syndrome_code": "syndrome_unapproved"}
                )
            ]
        }
    )
    pipeline = dataclasses.replace(pipeline, diagnosis=updated)

    result = _diagnosis_from_v31_pipeline(
        pipeline,
        diagnosis_id="diag_fallback",
        assessment_ref=_assessment_ref(),
        element_profile=_available_element_profile(),
    )

    root = result.root
    assert root.presentation.primary_tendency == "Spleen Deficiency"
    assert [candidate.display_name for candidate in root.candidate_tendencies] == [
        "Spleen Deficiency"
    ]
