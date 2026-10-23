"""R1/R2 audit -- the V2.1 normal-mode routing in ``resolve_organ_dominance``.

The team baseline (``ff879f70``) changed the routing contract relative to the
Sprint 6 Phase 1B asset. The module docstring is explicit:

    Coverage, normalized margin and raw ratio remain persisted audit metrics;
    they have no V2.1 normal-mode routing authority. This normal producer never
    emits ``integrated_regulation``; legacy consumers still accept it.

These tests record the *executed* behaviour against the published baseline.
They do not assert the behaviour is medically correct -- that is the sign-off
question the audit report raises (see D-6..D-8).

Frozen reason precedence observed in ``resolve_organ_dominance``:

    1. upstream legal abstain            -> basic_wellness
    2. zero legal candidate              -> basic_wellness (NO_LEGAL_ORGAN_CANDIDATE)
    3. >=2 candidates, raw tie           -> basic_wellness (EXACT_AUTHORITY_TIE)
    4. blocking direct contradiction     -> basic_wellness (UNRESOLVED_DIRECT_CONTRADICTION)
    5. exactly one legal candidate       -> personalized (SINGLE_LEGAL_CANDIDATE)
    6. >=2 candidates, distinct top1     -> personalized (UNIQUE_AUTHORITY_TOP1)
"""

from __future__ import annotations

from pathlib import Path

from backend.app.services.v3 import organ_dominance_service as ods

from tests.sprint7_audit.harness import decide_with_population, synthetic_population


def test_asset_still_declares_thresholds_but_code_demotes_them(
    dominance_rule: dict,
) -> None:
    """Observed drift: the asset still promises thresholds the code no longer routes on.

    ``evidence_gate.minimum_coverage`` and ``dominance_gate.normalized_margin_threshold``
    / ``raw_ratio_threshold`` remain in the frozen JSON, but ``resolve_organ_dominance``
    only persists them as audit fields. This split is exactly what an audit must
    surface: the asset text and the executable behaviour have diverged.
    """

    assert dominance_rule["evidence_gate"]["minimum_coverage"] == 0.50
    gate = dominance_rule["dominance_gate"]
    assert gate["normalized_margin_threshold"] == 0.08
    assert gate["raw_ratio_threshold"] == 1.20

    # the code still reads them, but only to write the audit record
    source = Path(ods.__file__).read_text(encoding="utf-8")
    assert "no V2.1 normal-mode routing authority" in source
    assert "integrated_regulation" in source  # only referenced as a legacy remnant


def test_exact_raw_tie_routes_to_basic_authority_tie(assets) -> None:
    """Observed: two candidates with equal raw support -> basic, not integrated."""

    facts, links = synthetic_population({"liver": 1.00, "heart": 1.00})
    decision = decide_with_population(facts, links, assets, coverage=1.0)

    assert set(decision.organ.legal_candidate_organs) == {"liver", "heart"}
    assert decision.regulation_mode == "basic_wellness"
    assert decision.decision_reason_code == "BASIC_EXACT_AUTHORITY_TIE"
    assert decision.dominant_organ is None
    assert decision.primary_tone is None


def test_distinct_top1_routes_to_personalized_directly(assets) -> None:
    """Observed: any distinct top1 -> personalized, no margin/ratio gate.

    liver 1.00 vs heart 0.90 is a near-tie; under the Phase 1B asset this would
    have needed margin >= 0.08 AND ratio >= 1.20. The baseline ignores both.
    """

    facts, links = synthetic_population({"liver": 1.00, "heart": 0.90})
    decision = decide_with_population(facts, links, assets, coverage=1.0)

    assert decision.regulation_mode == "personalized_five_tone"
    assert decision.dominant_organ == "liver"
    assert decision.primary_tone == "jiao"
    assert decision.decision_reason_code == "PERSONALIZED_UNIQUE_AUTHORITY_TOP1"


def test_ratio_below_threshold_still_personalized(assets) -> None:
    """Observed: raw ratio 1.19 (below 1.20) does not block the decision.

    The gate is recorded as failed but has no routing authority.
    """

    facts, links = synthetic_population({"liver": 1.00, "heart": 0.84})
    decision = decide_with_population(facts, links, assets, coverage=1.0)

    assert decision.regulation_mode == "personalized_five_tone"
    assert decision.dominance.raw_ratio < 1.20
    assert decision.dominance.ratio_gate_state == "failed"


def test_margin_below_threshold_still_personalized(assets) -> None:
    """Observed: a 3-candidate margin of 0.0625 (< 0.08) still selects top1."""

    facts, links = synthetic_population({"liver": 1.20, "heart": 1.00, "spleen": 1.00})
    decision = decide_with_population(facts, links, assets, coverage=1.0)

    assert decision.regulation_mode == "personalized_five_tone"
    assert decision.dominant_organ == "liver"
    assert decision.dominance.margin_gate_state == "failed"
    assert decision.decision_reason_code == "PERSONALIZED_UNIQUE_AUTHORITY_TOP1"


def test_single_candidate_routes_to_personalized(assets) -> None:
    """Observed: a lone legal candidate -> personalized, null margin/ratio."""

    facts, links = synthetic_population({"liver": 1.20})
    decision = decide_with_population(facts, links, assets, coverage=1.0)

    assert decision.regulation_mode == "personalized_five_tone"
    assert decision.dominant_organ == "liver"
    assert decision.decision_reason_code == "PERSONALIZED_SINGLE_LEGAL_CANDIDATE"
    assert decision.dominance.normalized_margin is None
    assert decision.dominance.raw_ratio is None
    assert decision.dominance.margin_gate_state == "not_applicable_single_candidate"


def test_normal_producer_never_emits_integrated(assets) -> None:
    """Observed: the multi-candidate near-tie no longer yields integrated_regulation.

    Every distinct-top1 multi-candidate case lands on personalized; the only
    non-personalized outcomes are basic_wellness. ``integrated_regulation`` is
    unreachable from this producer.
    """

    import pytest

    cases = [
        {"liver": 1.00, "heart": 0.90},
        {"liver": 1.00, "heart": 0.84},
        {"liver": 1.20, "heart": 1.00, "spleen": 1.00},
        {"liver": 1.00, "heart": 0.80},
    ]
    for spec in cases:
        facts, links = synthetic_population(spec)
        decision = decide_with_population(facts, links, assets, coverage=1.0)
        assert decision.regulation_mode != "integrated_regulation", spec


def test_upstream_abstain_short_circuits_everything(assets) -> None:
    """Observed: an upstream legal abstain maps straight to basic_wellness."""

    facts, links = synthetic_population({"liver": 1.20})
    from tests.sprint7_audit.harness import decide

    decision = decide(
        facts,
        assets,
        coverage=1.0,
        upstream_abstain_reason="ELEMENT_EVIDENCE_INSUFFICIENT",
    )

    assert decision.regulation_mode == "basic_wellness"
    assert decision.decision_reason_code == "BASIC_ELEMENT_EVIDENCE_INSUFFICIENT"
    assert decision.dominant_organ is None
    assert decision.primary_tone is None
