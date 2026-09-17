"""Sprint 6 Phase 1B gate D — diagnosis/pipeline routing and persistence.

These tests drive the formal ``/api/v3/diagnoses`` entry with the approved
fake provider chain (no network, no provider keys) over real persisted evidence
rows, and assert that:

* the authoritative decision is persisted inside the checksum-protected v3.3
  read model;
* Agent3 consumes it and never re-decides (no argmax/Gong);
* prescription preserves the mode;
* preference policy cannot overwrite mode/tone;
* asset/mapping failures stay readiness failures and never become a mode.
"""

from __future__ import annotations

from hashlib import sha256
import json
import uuid

import pytest

from backend.app.core import agent_config
from backend.app.models.v3.assessment import AssessmentRevisionV3
from backend.app.models.v3.assessment import (
    FactEvidence as FactEvidenceRow,
    OrganEvidence as OrganEvidenceRow,
)
from backend.app.models.v3.diagnosis import DiagnosisRun
from backend.app.models.v3.understanding import FactSourceRef, NormalizedFact
from backend.app.services.v3 import diagnosis_service
from backend.app.services.v3.organ_dominance_service import decision_snapshot_checksum
from tests.api.v3.test_diagnosis_v3 import (
    _diagnosis_body,
    _guest_headers,
    _seed_confirmed_assessment,
    _setup_flow_session,
    client,
)
from tests.api.v3.test_diagnosis_v31_pipeline_entry import (
    _confirmed_state_for,
    _manifest,
)
from tests.sprint6_phase1b_fixtures import synthetic_evidence


def _seed_evidence(
    db, *, assessment_id: str, organ_support: dict, suffix: str = ""
) -> None:
    """Persist the synthetic confirmed evidence population for a revision."""

    evidence, links = synthetic_evidence(organ_support)
    for item in evidence:
        fact_row_id = f"nfr_{item.fact_evidence_id}{suffix}"
        db.add(
            NormalizedFact(
                fact_row_id=fact_row_id,
                fact_id=item.fact_id,
                owner_type="understanding",
                understanding_id=f"und_p1b_fixture{suffix}",
                understanding_revision=1,
                questionnaire_submission_id=None,
                fact_code=item.claim_code,
                category=item.category,
                display_name=item.display_name,
                value_json=item.value.model_dump(mode="json"),
                time_window=item.time_window,
                negated=0,
                subject="self",
                confirmation_status="confirmed",
                extraction_method="deterministic_questionnaire_mapping",
                extraction_confidence=item.reliability,
            )
        )
        db.add(
            FactSourceRef(
                fact_row_id=fact_row_id,
                source_type="questionnaire",
                source_id=f"q_{item.fact_evidence_id}{suffix}",
                span_ref=None,
            )
        )
        db.add(
            FactEvidenceRow(
                fact_evidence_row_id=f"fer_{item.fact_evidence_id}{suffix}",
                fact_evidence_id=item.fact_evidence_id,
                assessment_id=assessment_id,
                assessment_revision=1,
                normalized_fact_row_id=fact_row_id,
                claim_code=item.claim_code,
                category=item.category,
                display_name=item.display_name,
                value_json=item.value.model_dump(mode="json"),
                time_window=item.time_window,
                direction=item.direction,
                reliability=item.reliability,
                confirmation_status="confirmed",
            )
        )
    for link in links:
        db.add(
            OrganEvidenceRow(
                organ_evidence_link_id=f"oer_{link.organ_evidence_link_id}{suffix}",
                fact_evidence_row_id=f"fer_{link.fact_evidence_id}{suffix}",
                organ=link.organ.value,
                element=link.element.value,
                direction=link.direction.value,
                link_strength=link.link_strength,
                mapping_rule_id=link.mapping_rule_id,
                mapping_version=link.mapping_version,
                explanation_summary=link.explanation_summary,
            )
        )
    db.commit()


def _pipeline_dependencies(calls: list[str]):
    """Fake approved provider chain that accepts a real fact population."""

    from types import SimpleNamespace

    from backend.app.schemas.v3.diagnosis import DiagnosisProviderResponse
    from tests.ai_engine.v3.test_v31_pipeline import _mapping, _rules

    class FakeRagStore:
        manifest = _manifest()
        approved_chunk_ids = frozenset({"chunk_1"})
        chunk_checksums: dict = {}

        def query(self, query):
            calls.append(f"rag:{query.query_id}")
            from tests.ai_engine.v3.test_v31_pipeline import _rag_result

            return _rag_result()

    class FakeProvider:
        allowed_syndrome_codes = {"syndrome_1"}
        allowed_fact_ids: set = set()
        allowed_chunk_ids = {"chunk_1"}
        medical_rule_version = "medical-rules-v3.1-r1"

        async def acomplete_json(self, *, request, facts, rag_chunk_ids):
            calls.append("qwen")
            return DiagnosisProviderResponse.model_validate(
                {
                    "status": "success",
                    "candidate_tendencies": [
                        {
                            "syndrome_code": "syndrome_1",
                            "display_name": "safe tendency",
                            "relative_support": 0.8,
                            "supporting_fact_ids": [],
                            "contradicting_fact_ids": [],
                            "knowledge_chunk_ids": ["chunk_1"],
                            "reasoning_summary": "grounded summary",
                        }
                    ],
                    "abstained": False,
                    "abstain_reason": None,
                }
            )

    return SimpleNamespace(
        rag_store=FakeRagStore(),
        diagnosis_provider=FakeProvider(),
        tone_mapping=_mapping(),
        generation_parameter_rules=_rules(),
        allowed_syndrome_codes=frozenset({"syndrome_1"}),
        medical_rule_version="medical-rules-v3.1-r1",
    )


def _organ_profile(organ_support: dict) -> dict:
    total = sum(organ_support.values())
    weights = {organ: 0.0 for organ in ("liver", "heart", "spleen", "lung", "kidney")}
    for organ, value in organ_support.items():
        weights[organ] = round(value / total, 4)
    return {
        "status": "available",
        "weights": weights,
        "score_semantics": "relative_evidence_distribution",
    }


def _run_diagnosis(
    db_session_factory, monkeypatch, *, organ_support: dict, suffix: str = ""
):
    headers = _guest_headers()
    db = db_session_factory()
    session_id, user_pk, session_row = _setup_flow_session(db, headers)
    assessment_id = _seed_confirmed_assessment(
        db,
        user_pk=user_pk,
        session_row=session_row,
        organ_profile_json=_organ_profile(organ_support),
        assessment_input_revision=session_row.input_revision,
        revision_input_revision=session_row.input_revision,
    )
    _seed_evidence(
        db,
        assessment_id=assessment_id,
        organ_support=organ_support,
        suffix=suffix,
    )
    db.close()

    calls: list[str] = []
    dependencies = _pipeline_dependencies(calls)
    monkeypatch.setattr(diagnosis_service, "_v31_real_mode", lambda: True)
    monkeypatch.setattr(
        agent_config,
        "get_v31_ai_pipeline_dependencies",
        lambda: dependencies,
    )
    monkeypatch.setattr(
        diagnosis_service,
        "_load_confirmed_user_state",
        lambda *args, **kwargs: _confirmed_state_for(session_id),
    )
    monkeypatch.setattr(
        diagnosis_service,
        "get_latest_preference_snapshot",
        lambda *args, **kwargs: None,
    )
    response = client.post(
        "/api/v3/diagnoses",
        headers={**headers, "Idempotency-Key": f"p1b-{uuid.uuid4().hex}"},
        json=_diagnosis_body(session_id, assessment_id, 1),
    )
    return headers, response


def _persisted_read_model(db_session_factory, diagnosis_id: str | None = None) -> dict:
    db = db_session_factory()
    try:
        query = db.query(DiagnosisRun)
        if diagnosis_id is not None:
            query = query.filter(DiagnosisRun.diagnosis_id == diagnosis_id)
        run = query.one()
        return {
            "schema_version": run.five_tone_read_model_schema_version,
            "payload": run.five_tone_read_model_json,
            "checksum": run.five_tone_read_model_checksum,
            "generation_spec": run.generation_spec_json,
            "status": run.status,
        }
    finally:
        db.close()


def test_personalized_route_is_persisted_with_audit_and_checksum(
    db_session_factory, monkeypatch
):
    headers, response = _run_diagnosis(
        db_session_factory, monkeypatch, organ_support={"liver": 6.0, "spleen": 5.0}
    )
    assert response.status_code == 201, response.text
    stored = _persisted_read_model(db_session_factory)

    assert stored["schema_version"] == "five_tone_analysis_read_model_v3.3"
    payload = stored["payload"]
    assert payload["regulation_mode"] == "personalized_five_tone"
    assert payload["dominant_organ"] == "liver"
    assert payload["primary_tone"]["tone"] == "jiao"
    assert payload["decision_reason_code"] == "PERSONALIZED_DOMINANCE_THRESHOLDS_MET"

    decision = payload["dominance_decision"]
    assert decision["schema_id"] == "organ_dominance_decision_v1"
    assert decision["coverage"]["coverage_denominator"] == 8
    assert decision["coverage"]["coverage_gate_passed"] is True
    assert decision["organ"]["legal_candidate_organs"] == ["liver", "spleen"]
    assert decision["dominance"]["raw_ratio"] == 1.2
    assert decision["assets"]["dominance_rule_version"] == "dominance-rule-v1.0-r1"

    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    assert stored["checksum"] == f"sha256:{sha256(canonical.encode('utf-8')).hexdigest()}"

    from backend.app.schemas.v3.flow_v31 import OrganDominanceDecisionV1

    restored = OrganDominanceDecisionV1.model_validate(decision)
    assert restored.decision_snapshot_checksum == decision["decision_snapshot_checksum"]

    # Agent3 consumed the authoritative decision: the transport tone profile
    # carries exactly the decided mode and primary tone.
    transport = stored["generation_spec"]["tone_profile"]
    assert transport["regulation_mode"] == "personalized_five_tone"
    assert transport["primary_tone"] == "jiao"
    assert transport["schema_version"] == "tone_profile_v3.2"


def test_exact_tie_route_is_integrated_and_never_picks_a_tone(
    db_session_factory, monkeypatch
):
    """Phase 1A argmax would have chosen a tone here; Phase 1B must not."""

    headers, response = _run_diagnosis(
        db_session_factory,
        monkeypatch,
        organ_support={"liver": 2.0, "spleen": 2.0, "lung": 0.2},
    )
    assert response.status_code == 201, response.text
    payload = _persisted_read_model(db_session_factory)["payload"]

    assert payload["regulation_mode"] == "integrated_regulation"
    assert payload["primary_tone"] is None
    assert payload["secondary_tone"] is None
    assert payload["decision_reason_code"] == "INTEGRATED_EXACT_TOP_TIE"
    assert payload["tone_weights"] is not None
    assert "宫音" not in json.dumps(payload, ensure_ascii=False)
    transport = _persisted_read_model(db_session_factory)["generation_spec"][
        "tone_profile"
    ]
    assert transport["regulation_mode"] == "integrated_regulation"
    assert transport.get("primary_tone") is None


def test_coverage_gate_routes_to_basic_wellness_from_real_evidence(
    db_session_factory, monkeypatch
):
    _headers, response = _run_diagnosis(
        db_session_factory, monkeypatch, organ_support={"liver": 1.0}
    )
    assert response.status_code == 201, response.text
    payload = _persisted_read_model(db_session_factory)["payload"]

    assert payload["regulation_mode"] == "basic_wellness"
    assert payload["primary_tone"] is None
    assert payload["tone_weights"] is None
    assert payload["decision_reason_code"] == "BASIC_EVIDENCE_COVERAGE_BELOW_THRESHOLD"
    decision = payload["dominance_decision"]
    assert decision["coverage"]["confirmed_fact_count"] == 2
    assert decision["coverage"]["evidence_coverage"] == 0.25
    assert decision["coverage"]["coverage_gate_passed"] is False
    assert decision["dominance"]["margin_gate_state"] == "not_evaluated"


def test_repeat_runs_decide_identically(db_session_factory, monkeypatch):
    decisions = []
    for run_index in range(2):
        _headers, response = _run_diagnosis(
            db_session_factory,
            monkeypatch,
            organ_support={"spleen": 6.0, "liver": 5.0},
            suffix=f"r{run_index}",
        )
        assert response.status_code == 201, response.text
        diagnosis_id = response.json()["data"]["diagnosis_id"]
        payload = _persisted_read_model(db_session_factory, diagnosis_id)["payload"]
        decisions.append(
            {
                "mode": payload["regulation_mode"],
                "tone": payload["primary_tone"]["tone"]
                if payload["primary_tone"]
                else None,
                "reason": payload["decision_reason_code"],
                "organ": payload["dominant_organ"],
                "margin": payload["dominance_decision"]["dominance"][
                    "normalized_margin"
                ],
                "ratio": payload["dominance_decision"]["dominance"]["raw_ratio"],
            }
        )
    assert decisions[0] == decisions[1]
    assert decisions[0] == {
        "mode": "personalized_five_tone",
        "tone": "gong",
        "reason": "PERSONALIZED_DOMINANCE_THRESHOLDS_MET",
        "organ": "spleen",
        "margin": 0.091,
        "ratio": 1.2,
    }


def test_prescription_preserves_the_authoritative_mode(db_session_factory, monkeypatch):
    headers, response = _run_diagnosis(
        db_session_factory,
        monkeypatch,
        organ_support={"liver": 2.0, "spleen": 2.0, "lung": 0.2},
    )
    assert response.status_code == 201, response.text

    db = db_session_factory()
    diagnosis_id = db.query(DiagnosisRun).one().diagnosis_id
    db.close()

    prescription = client.post(
        "/api/v3/prescriptions",
        headers={**headers, "Idempotency-Key": f"p1b-rx-{uuid.uuid4().hex}"},
        json={
            "schema_version": "prescription_v3.1",
            "diagnosis_id": diagnosis_id,
            "preference_snapshot": None,
        },
    )
    assert prescription.status_code == 201, prescription.text
    data = prescription.json()["data"]
    summary = data["presentation"]["tone_summary"]
    assert "综合调适" in summary
    assert "宫调为主" not in summary
    assert "为主" not in summary
    spec = data["generation_spec"]["tone_profile"]
    assert spec["regulation_mode"] == "integrated_regulation"
    assert spec.get("primary_tone") is None


def test_asset_readiness_failure_never_becomes_a_mode(
    db_session_factory, monkeypatch
):
    monkeypatch.setenv("V31_DOMINANCE_RULE_CHECKSUM", "sha256:" + "0" * 64)
    _headers, response = _run_diagnosis(
        db_session_factory, monkeypatch, organ_support={"liver": 6.0, "spleen": 5.0}
    )
    assert response.status_code == 502, response.text
    body = response.json()
    assert body["error"]["code"] == "DOMINANCE_RULE_ASSET_CHECKSUM_MISMATCH"

    db = db_session_factory()
    try:
        run = db.query(DiagnosisRun).one_or_none()
        if run is not None:
            assert run.five_tone_read_model_json is None
    finally:
        db.close()


def test_preference_policy_never_overwrites_mode_or_tone():
    """Preference sync may change music parameters only, never the decision."""

    from backend.app.schemas.v3.prescription import PreferenceSnapshot
    from backend.app.services.v3.agent3_preference_policy import apply_preference_policy
    from tests.ai_engine.v3.test_v31_pipeline import _mapping, _rules
    from backend.ai_engine.v3.agent3 import (
        build_five_tone_analysis_v31,
        build_generation_spec_v31,
        build_tone_profile_v31,
    )
    from tests.sprint6_phase1b_fixtures import synthetic_decision

    decision = synthetic_decision(
        regulation_mode="personalized_five_tone",
        dominant_organ="liver",
        primary_tone="jiao",
    )
    profile = build_tone_profile_v31(
        diagnosis_id="diag_pref",
        organ_weights={"liver": 0.7, "spleen": 0.3},
        supporting_evidence_refs=["fev_1"],
        mapping=_mapping(),
        dominance_decision=decision,
    )
    spec = build_generation_spec_v31(profile=profile, parameter_rules=_rules())
    read_model = build_five_tone_analysis_v31(
        confirmed_user_state_ref={
            "confirmed_user_state_id": "cus_pref",
            "revision": 1,
            "content_checksum": "sha256:cus",
        },
        confirmed_state="state",
        state_tendency="tendency",
        profile=profile,
        evidence_refs=["fev_1"],
        mapping=_mapping(),
        generation_spec=spec,
        dominance_decision=decision,
    )
    preference = PreferenceSnapshot.model_validate(
        {
            "profile_id": "pref_1",
            "version": 1,
            "preferred_instruments": [{"code": "古琴", "weight": 1.0, "sample_count": 3}],
            "disliked_instruments": [],
            "preferred_bpm_range": {"min": 66, "max": 70, "weight": 1.0},
            "preferred_duration_seconds": {"value": 600, "weight": 1.0},
            "preferred_ambient": [{"code": "溪流", "weight": 1.0, "sample_count": 2}],
        }
    )
    updated, events = apply_preference_policy(read_model, preference)
    assert any(event.applied for event in events)
    assert updated.bpm.value != read_model.bpm.value

    # the authoritative decision surface is untouched
    assert updated.regulation_mode == read_model.regulation_mode
    assert updated.primary_tone == read_model.primary_tone
    assert updated.secondary_tone == read_model.secondary_tone
    assert updated.tone_weights == read_model.tone_weights
    assert updated.dominant_organ == read_model.dominant_organ
    assert updated.decision_reason_code == read_model.decision_reason_code
    assert updated.dominance_decision == read_model.dominance_decision
    assert updated.schema_version == "five_tone_analysis_read_model_v3.3"


def test_phase_1a_v32_rows_stay_readable_without_a_fabricated_audit():
    """A v3.2 row must never gain a synthesized Phase 1B decision."""

    from backend.app.services.v3 import legacy_mode_compat

    payload = {
        "schema_version": "five_tone_analysis_read_model_v3.2",
        "confirmed_user_state_ref": {
            "confirmed_user_state_id": "cus_v32",
            "revision": 1,
            "content_checksum": "sha256:cus",
        },
        "confirmed_state": "state",
        "state_tendency": "tendency",
        "analysis_rationales": [
            {"summary": "summary", "evidence_refs": ["fev_1"]}
        ],
        "regulation_mode": "personalized_five_tone",
        "tone_weights": {
            "jiao": 0.4,
            "zhi": 0.15,
            "gong": 0.15,
            "shang": 0.15,
            "yu": 0.15,
        },
        "primary_tone": {
            "tone": "jiao",
            "display_name": "角音",
            "explanation": "primary tone",
        },
        "secondary_tone": None,
        "bpm": {"value": 60, "explanation": "bpm"},
        "instruments": {"values": ["古琴"], "explanation": "instruments"},
        "ambience": {"values": ["细雨"], "explanation": "ambience"},
        "duration": {"seconds": 180, "explanation": "duration"},
        "generation": {"status": "ready", "message": "ready"},
        "disclaimer": "reference only",
    }
    resolved, compatibility = legacy_mode_compat.resolve_read_model_payload(
        payload,
        legacy_mode_compat.LegacyProvenance(source="diagnosis", diagnosis_status="success"),
    )
    assert compatibility is None
    assert resolved.schema_version == "five_tone_analysis_read_model_v3.2"
    assert resolved.regulation_mode == "personalized_five_tone"
    assert resolved.primary_tone.tone == "jiao"
    # no Phase 1B audit is invented from primary_tone / tone_weights / argmax
    assert getattr(resolved, "dominance_decision", None) is None
    assert "dominance_decision" not in resolved.model_dump(mode="json")
    assert "decision_reason_code" not in resolved.model_dump(mode="json")


def test_mapping_identity_mismatch_is_a_readiness_failure(
    db_session_factory, monkeypatch
):
    def _tampered_dependencies():
        dependencies = _pipeline_dependencies([])
        tampered = dict(dependencies.tone_mapping)
        tampered["content_checksum"] = "sha256:" + "1" * 64
        dependencies.tone_mapping = tampered
        return dependencies

    monkeypatch.setattr(diagnosis_service, "_v31_real_mode", lambda: True)
    monkeypatch.setattr(
        agent_config,
        "get_v31_ai_pipeline_dependencies",
        _tampered_dependencies,
    )
    headers = _guest_headers()
    db = db_session_factory()
    session_id, user_pk, session_row = _setup_flow_session(db, headers)
    assessment_id = _seed_confirmed_assessment(
        db,
        user_pk=user_pk,
        session_row=session_row,
        organ_profile_json=_organ_profile({"liver": 6.0, "spleen": 5.0}),
        assessment_input_revision=session_row.input_revision,
        revision_input_revision=session_row.input_revision,
    )
    _seed_evidence(db, assessment_id=assessment_id, organ_support={"liver": 6.0, "spleen": 5.0})
    db.close()
    monkeypatch.setattr(
        diagnosis_service,
        "_load_confirmed_user_state",
        lambda *args, **kwargs: _confirmed_state_for(session_id),
    )
    response = client.post(
        "/api/v3/diagnoses",
        headers={**headers, "Idempotency-Key": f"p1b-mm-{uuid.uuid4().hex}"},
        json=_diagnosis_body(session_id, assessment_id, 1),
    )
    assert response.status_code == 502, response.text
    assert response.json()["error"]["code"] == "DOMINANCE_MAPPING_IDENTITY_MISMATCH"
