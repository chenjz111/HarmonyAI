"""Sprint 6 Phase 1B — fixture contract, A-K expectations and boundaries.

Runs the Phase 1B fixture (I/J/K plus synthetic boundaries) through the real
dominance service. The frozen Phase 0 A-H fixture is not modified here; its
convention is referenced and its membership re-checked.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.sprint6_phase1b_fixtures import decision_from_organ_support

ROOT = Path(__file__).resolve().parents[2]
PHASE_1B_FIXTURE = ROOT / "tests" / "fixtures" / "sprint6_phase1b_cases.json"
PHASE_0_FIXTURE = ROOT / "tests" / "fixtures" / "sprint6_acceptance_cases.json"

EXPECTED_CASE_IDS = ["I", "J", "K"]
EXPECTED_BOUNDARY_IDS = [
    "zero_legal_candidate",
    "one_legal_candidate",
    "exact_raw_tie",
    "margin_exactly_threshold",
    "margin_just_below_threshold",
    "ratio_exactly_threshold",
    "ratio_just_below_threshold",
    "coverage_exactly_threshold",
    "coverage_below_threshold",
    "unresolved_major_conflict",
    "dominance_affecting_minor_conflict",
    "resolved_minor_conflict_is_audit_only",
    "unrelated_minor_conflict_is_audit_only",
]


def _fixture() -> dict:
    return json.loads(PHASE_1B_FIXTURE.read_text(encoding="utf-8"))


def _decision_for(entry: dict):
    return decision_from_organ_support(
        {organ: float(value) for organ, value in entry["organ_support"].items()},
        conflicts=entry.get("conflicts", []),
        coverage_count=entry.get("confirmed_fact_count"),
    )


def _assert_expected(decision, expected: dict) -> None:
    if "regulation_mode" in expected:
        assert decision.regulation_mode == expected["regulation_mode"]
    if "dominant_organ" in expected:
        organ = decision.dominant_organ
        assert (organ.value if organ is not None else None) == expected["dominant_organ"]
    if "primary_tone" in expected:
        tone = decision.primary_tone
        assert (tone.value if tone is not None else None) == expected["primary_tone"]
    if "decision_reason_code" in expected:
        assert decision.decision_reason_code == expected["decision_reason_code"]
    if "normalized_margin" in expected:
        assert decision.dominance.normalized_margin == expected["normalized_margin"]
    if "raw_ratio" in expected:
        assert decision.dominance.raw_ratio == expected["raw_ratio"]
    if "margin_gate_state" in expected:
        assert decision.dominance.margin_gate_state == expected["margin_gate_state"]
    if "ratio_gate_state" in expected:
        assert decision.dominance.ratio_gate_state == expected["ratio_gate_state"]
    if "evidence_coverage" in expected:
        assert decision.coverage.evidence_coverage == expected["evidence_coverage"]
    if "coverage_gate_passed" in expected:
        assert decision.coverage.coverage_gate_passed is expected["coverage_gate_passed"]
    if "dominance_affecting_minor_conflict_ids" in expected:
        assert (
            list(decision.conflict.dominance_affecting_minor_conflict_ids)
            == expected["dominance_affecting_minor_conflict_ids"]
        )


# --------------------------------------------------------------------------- #
# fixture contract
# --------------------------------------------------------------------------- #


def test_phase_1b_fixture_identity_and_membership():
    fixture = _fixture()
    assert fixture["schema_id"] == "sprint6_phase1b_cases"
    assert fixture["schema_version"] == "1.0"
    assert fixture["phase"] == "Sprint 6 Phase 1B"
    assert list(fixture["cases"]) == EXPECTED_CASE_IDS
    assert [item["id"] for item in fixture["boundaries"]] == EXPECTED_BOUNDARY_IDS
    assert fixture["organ_tone_map"] == {
        "liver": "jiao",
        "heart": "zhi",
        "spleen": "gong",
        "lung": "shang",
        "kidney": "yu",
    }


def test_phase_1b_fixture_is_synthetic_and_keeps_phase_0_frozen():
    fixture = _fixture()
    assert fixture["frozen_phase_0_fixture"] == "tests/fixtures/sprint6_acceptance_cases.json"
    phase_0 = json.loads(PHASE_0_FIXTURE.read_text(encoding="utf-8"))
    raw = json.dumps(phase_0, ensure_ascii=False)
    # the frozen Phase 0 fixture still pins exactly A-H
    for case_id in ("A", "B", "C", "D", "E", "F", "G", "H"):
        assert f'"{case_id}"' in raw
    assert '"I"' not in raw and '"J"' not in raw and '"K"' not in raw
    # Phase 1B data is synthetic: no user text / provider payload fields at all
    phase_1b = json.dumps(fixture, ensure_ascii=False).lower()
    for forbidden in ("prompt", "embedding", "provider_payload", "raw_text", "api_key"):
        assert forbidden not in phase_1b


def test_every_fixture_entry_declares_its_expectation():
    fixture = _fixture()
    for case_id, entry in fixture["cases"].items():
        assert entry["expected"], case_id
        assert entry["title"]
        assert entry["organ_support"]
    for boundary in fixture["boundaries"]:
        assert boundary["expected"], boundary["id"]
        assert boundary["title"]


# --------------------------------------------------------------------------- #
# A-K: Phase 0 A-H (frozen) + Phase 1B I/J/K through the real service
# --------------------------------------------------------------------------- #


def test_phase_1b_cases_I_J_K():
    for case_id, entry in _fixture()["cases"].items():
        decision = _decision_for(entry)
        _assert_expected(decision, entry["expected"])
        assert decision.coverage.coverage_gate_passed is True, case_id


def test_phase_0_cases_A_to_H_still_route_as_frozen():
    """The frozen A-H expectations are reached through the Phase 1B service."""

    liver = decision_from_organ_support({"liver": 1.85, "spleen": 1.1125})
    assert (liver.regulation_mode, liver.primary_tone.value) == (
        "personalized_five_tone",
        "jiao",
    )
    spleen = decision_from_organ_support({"spleen": 1.85, "liver": 1.1125})
    assert (spleen.regulation_mode, spleen.primary_tone.value) == (
        "personalized_five_tone",
        "gong",
    )
    heart = decision_from_organ_support({"heart": 1.85, "spleen": 1.1125})
    assert (heart.regulation_mode, heart.primary_tone.value) == (
        "personalized_five_tone",
        "zhi",
    )

    # D / H: near-uniform legal candidates stay integrated with no tone
    uniform = {
        "liver": 1.0,
        "heart": 1.0,
        "spleen": 1.0,
        "lung": 1.0,
        "kidney": 1.0,
    }
    for _repeat in range(2):
        balanced = decision_from_organ_support(uniform)
        assert balanced.regulation_mode == "integrated_regulation"
        assert balanced.primary_tone is None
        assert balanced.decision_reason_code == "INTEGRATED_EXACT_TOP_TIE"

    # E: insufficient evidence is basic_wellness, never Gong
    insufficient = decision_from_organ_support({"liver": 1.0}, coverage_count=2)
    assert insufficient.regulation_mode == "basic_wellness"
    assert insufficient.primary_tone is None
    assert insufficient.decision_reason_code == (
        "BASIC_EVIDENCE_COVERAGE_BELOW_THRESHOLD"
    )

    # G: RAG_EMPTY abstain is basic_wellness with the preserved reason
    rag_empty = decision_from_organ_support(
        {"liver": 1.0}, upstream_abstain_reason="RAG_EMPTY"
    )
    assert (rag_empty.regulation_mode, rag_empty.decision_reason_code) == (
        "basic_wellness",
        "BASIC_RAG_EMPTY",
    )


# --------------------------------------------------------------------------- #
# boundaries
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "boundary",
    _fixture()["boundaries"],
    ids=[item["id"] for item in _fixture()["boundaries"]],
)
def test_phase_1b_boundary_table(boundary):
    decision = _decision_for(boundary)
    _assert_expected(decision, boundary["expected"])


def test_boundary_table_executes_the_real_service():
    """Every boundary decision is checksum-protected and repeatable."""

    from backend.app.services.v3.organ_dominance_service import (
        decision_snapshot_checksum,
    )

    for boundary in _fixture()["boundaries"]:
        decision = _decision_for(boundary)
        assert decision.decision_snapshot_checksum == decision_snapshot_checksum(
            decision
        )
        again = _decision_for(boundary)
        assert again.decision_snapshot_checksum == decision.decision_snapshot_checksum


def test_reason_matrix_codes_are_all_reachable():
    """The frozen reason vocabulary is exercised by the fixture set."""

    fixture = _fixture()
    seen = {entry["expected"].get("decision_reason_code") for entry in fixture["cases"].values()}
    seen |= {
        boundary["expected"].get("decision_reason_code")
        for boundary in fixture["boundaries"]
    }
    seen.discard(None)
    assert seen == {
        "PERSONALIZED_DOMINANCE_THRESHOLDS_MET",
        "PERSONALIZED_SINGLE_LEGAL_CANDIDATE",
        "INTEGRATED_EXACT_TOP_TIE",
        "INTEGRATED_DOMINANCE_CONFLICT",
        "INTEGRATED_MARGIN_BELOW_THRESHOLD",
        "INTEGRATED_RATIO_BELOW_THRESHOLD",
        "BASIC_NO_LEGAL_ORGAN_CANDIDATE",
        "BASIC_EVIDENCE_COVERAGE_BELOW_THRESHOLD",
        "BASIC_UNRESOLVED_MAJOR_CONFLICT",
    }
