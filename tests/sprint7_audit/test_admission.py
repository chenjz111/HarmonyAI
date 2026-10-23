"""R1/R2 audit -- stage S1 ``evidence_admission.admit_projection``.

The admission contract is *pragmatic and narrow*: literal source presence and
span bounds, not semantic entailment. The docstring says so explicitly:

    "Source presence and span bounds are eligibility checks, not semantic
    entailment. Only narrowly recognizable contradictions are blocked here."

Key observation for the medical audit: ``subject`` is read here, but only as a
single literal pattern -- "母亲/父亲/家属 + label" -- and it only ever *blocks*
a fact whose subject is ``self``. ``other`` and ``unknown`` subjects are never
interrogated, so a fact about a family member can pass admission as long as it
was not mislabelled ``self``. Downstream, ``FactEvidence`` still drops the field.
"""

from __future__ import annotations

import json

import pytest

from backend.app.services.v3.evidence_admission import (
    AdmissionFailure,
    admit_projection,
)


def _fact(**overrides) -> dict:
    fact = {
        "fact_id": "f_1",
        "display_name": "胸胁胀闷",
        "negated": False,
        "subject": "self",
        "time_window": "past_7_days",
        "value": {"type": "frequency_0_4", "value": 3},
        "confirmation_status": "unconfirmed",
        "source_refs": [
            {
                "source_id": "src_1",
                "source_type": "document",
                "span_ref": json.dumps({"start": 0, "end": 5}),
            }
        ],
    }
    fact.update(overrides)
    return fact


def _sources(text="胸胁胀闷。", kind="document", time_window="past_7_days") -> dict:
    return {"src_1": {"kind": kind, "time_window": time_window, "text": text}}


# --------------------------------------------------------------------------- #
# subject handling (the one place S1 reads the dimension)
# --------------------------------------------------------------------------- #


def test_subject_family_claim_mislabelled_self_is_blocked() -> None:
    """Observed: "父亲胸胁胀闷" + subject=self -> EXPLICIT_SUBJECT_MISMATCH."""

    with pytest.raises(AdmissionFailure) as exc:
        admit_projection(
            [_fact(subject="self")],
            sources=_sources(text="父亲胸胁胀闷。"),
            summary="",
        )
    assert str(exc.value) == "EXPLICIT_SUBJECT_MISMATCH"


@pytest.mark.parametrize("subject", ["other", "unknown"])
def test_subject_family_claim_with_other_or_unknown_is_admitted(subject: str) -> None:
    """Observed: the same family clause passes when subject is not self."""

    admitted, candidates = admit_projection(
        [_fact(subject=subject)],
        sources=_sources(text="父亲胸胁胀闷。"),
        summary="",
    )
    assert admitted
    assert candidates and candidates[0]["disposition"] == "admitted"


# --------------------------------------------------------------------------- #
# negation handling
# --------------------------------------------------------------------------- #


def test_literal_negation_reversal_is_blocked() -> None:
    """Observed: "否认胸胁胀闷" with negated=False -> EXPLICIT_NEGATION_REVERSAL."""

    with pytest.raises(AdmissionFailure) as exc:
        admit_projection(
            [_fact(negated=False)],
            sources=_sources(text="否认胸胁胀闷。"),
            summary="",
        )
    assert str(exc.value) == "EXPLICIT_NEGATION_REVERSAL"


def test_literal_negation_consistent_with_negated_flag_is_admitted() -> None:
    """Observed: the negated fact matches its literal source and passes."""

    admitted, candidates = admit_projection(
        [_fact(negated=True)],
        sources=_sources(text="否认胸胁胀闷。"),
        summary="",
    )
    assert admitted
    assert "literal_negation" in candidates[0]["checks_performed"]


# --------------------------------------------------------------------------- #
# source / span / time / severity eligibility
# --------------------------------------------------------------------------- #


def test_missing_source_is_blocked() -> None:
    with pytest.raises(AdmissionFailure) as exc:
        admit_projection([_fact(source_refs=[])], sources={}, summary="")
    assert str(exc.value) == "SOURCE_REQUIRED"


def test_source_kind_mismatch_is_blocked() -> None:
    with pytest.raises(AdmissionFailure) as exc:
        admit_projection(
            [_fact()], sources=_sources(kind="questionnaire"), summary=""
        )
    assert str(exc.value) == "SOURCE_MISMATCH"


def test_time_window_mismatch_is_blocked() -> None:
    with pytest.raises(AdmissionFailure) as exc:
        admit_projection(
            [_fact(time_window="past_30_days")],
            sources=_sources(time_window="past_7_days"),
            summary="",
        )
    assert str(exc.value) == "TIME_CONTEXT_MISMATCH"


def test_span_out_of_bounds_is_blocked() -> None:
    out_of_bounds = {
        "source_id": "src_1",
        "source_type": "document",
        "span_ref": json.dumps({"start": 0, "end": 999}),
    }
    with pytest.raises(AdmissionFailure) as exc:
        admit_projection(
            [_fact(source_refs=[out_of_bounds])],
            sources=_sources(text="胸胁胀闷。"),
            summary="",
        )
    assert str(exc.value) == "SOURCE_SPAN_REQUIRED"


def test_severity_mismatch_is_blocked() -> None:
    """Observed: "轻度胸胁胀闷" but value is not "mild" -> EXPLICIT_VALUE_MISMATCH."""

    with pytest.raises(AdmissionFailure) as exc:
        admit_projection(
            [_fact(value={"type": "coded_text", "value": "moderate"})],
            sources=_sources(text="轻度胸胁胀闷。"),
            summary="",
        )
    assert str(exc.value) == "EXPLICIT_VALUE_MISMATCH"


def test_clean_fact_is_confirmed_and_recorded() -> None:
    """Observed: an eligible fact flips to confirmed and gains an admission record."""

    admitted, candidates = admit_projection(
        [_fact()], sources=_sources(text="胸胁胀闷。"), summary=""
    )

    assert admitted[0]["confirmation_status"] == "confirmed"
    assert candidates[0]["admission_basis"] == "pragmatic_ai_evidence_contract_v1"
    assert candidates[0]["disposition"] == "admitted"
    assert "AI_SEMANTIC_INTERPRETATION_NOT_FULLY_VERIFIED" in candidates[0]["uncertainty_flags"]


def test_empty_projection_is_blocked() -> None:
    """Observed: an all-rejected population raises instead of returning []. """

    with pytest.raises(AdmissionFailure) as exc:
        admit_projection(
            [_fact(confirmation_status="rejected")],
            sources=_sources(),
            summary="",
        )
    assert str(exc.value) == "EMPTY_ADMITTED_PROJECTION"


def test_rejected_fact_is_kept_but_never_becomes_a_candidate() -> None:
    """Observed: rejected rows are carried through untouched, outside the projection."""

    admitted, candidates = admit_projection(
        [
            _fact(fact_id="f_ok", confirmation_status="unconfirmed"),
            _fact(fact_id="f_rej", confirmation_status="rejected"),
        ],
        sources=_sources(),
        summary="",
    )
    ids = [f["fact_id"] for f in admitted]
    assert ids == ["f_ok", "f_rej"]
    assert [c["fact_id"] for c in candidates] == ["f_ok"]
